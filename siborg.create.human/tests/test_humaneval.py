"""Tests for siborg/create/human/humaneval.py. Needs only pxr and numpy, not Kit:

    <python with pxr and numpy> tests/test_humaneval.py

Runs against data/human_base_separated.usd (built by scripts/build_human.py).
"""

import importlib.util
import os
import tempfile
import unittest

import numpy as np
from pxr import Ar, Sdf, Usd, UsdSkel

EXT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HUMAN_USD = os.path.join(EXT_ROOT, "data", "human_base_separated.usd")
HUMAN_USDZ = os.path.join(EXT_ROOT, "data", "human.usdz")
PNG_SIGNATURE = bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A])

# Load humaneval by path: importing the siborg.create.human package would pull in Kit
_spec = importlib.util.spec_from_file_location(
    "humaneval", os.path.join(EXT_ROOT, "siborg", "create", "human", "humaneval.py"))
humaneval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(humaneval)


class LabelWeightTest(unittest.TestCase):
    def test_paired(self):
        knots, labels = [-1, 0, 1], ["decr", "", "incr"]
        self.assertEqual(humaneval.label_weights(knots, labels, 0), {})
        self.assertEqual(humaneval.label_weights(knots, labels, 0.25), {"incr": 0.25})
        self.assertEqual(humaneval.label_weights(knots, labels, -0.5), {"decr": 0.5})
        self.assertEqual(humaneval.label_weights(knots, labels, 5), {"incr": 1.0})  # Clamped

    def test_age(self):
        knots, labels = [0, 0.1875, 0.5, 1], ["baby", "child", "young", "old"]
        self.assertEqual(humaneval.label_weights(knots, labels, 0.5), {"young": 1.0})
        w = humaneval.label_weights(knots, labels, 0.75)
        self.assertAlmostEqual(w["young"], 0.5)
        self.assertAlmostEqual(w["old"], 0.5)
        self.assertEqual(humaneval.label_weights(knots, labels, 0), {"baby": 1.0})

    def test_degenerate_segment(self):
        self.assertEqual(humaneval.label_weights([0, 0, 1], ["a", "b", "c"], 0), {"b": 1.0})


@unittest.skipUnless(os.path.isfile(HUMAN_USD), "run scripts/build_human.py first")
class HumanRigTest(unittest.TestCase):
    def setUp(self):
        self.stage = Usd.Stage.Open(HUMAN_USD)
        self.stage.SetEditTarget(self.stage.GetSessionLayer())
        root = humaneval.find_human(self.stage.GetDefaultPrim())
        self.assertIsNotNone(root, "selecting the default prim finds the human below it")
        self.rig = humaneval.HumanRig(root)

    def mod(self, name):
        return next(i for i, m in enumerate(self.rig.modifiers) if m.path.name == name)

    def weight(self, weights, shape):
        return weights[self.rig.shape_names.index(shape)]

    def test_find_human_from_descendant(self):
        body = self.rig.root.GetChild("body")
        self.assertEqual(humaneval.find_human(body).GetPath(), self.rig.path)

    def test_drivers(self):
        # Every modifier drives some shape when all targets are installed (data/targets is mostly gitignored)
        if all(m.shape_count for m in self.rig.modifiers):
            self.assertEqual(len(self.rig.modifiers), 249)
        macro = {m.path.name for m in self.rig.modifiers if m.shape_count and m.path.GetParentPath().name == "macrodetails"}
        self.assertEqual(macro, {"gender", "age", "muscle", "weight", "height", "bodyproportions",
                                 "african", "asian", "caucasian"})
        # Shapes no modifier drives (target files modeling_modifiers.json doesn't use) stay at weight 0
        weights, _ = self.rig.evaluate(self.rig.default_values())
        undriven = [s for s, d in enumerate(self.rig.drivers) if not d]
        self.assertTrue(all(weights[s] == 0 for s in undriven))
        self.assertTrue(all(name.startswith(("l_", "r_", "chin_")) for name in
                            (self.rig.shape_names[s] for s in undriven)), "only MakeHuman's unused targets")

    def test_default_weights(self):
        values = self.rig.default_values()
        weights, _ = self.rig.evaluate(values)
        # gender 0.5, age 0.5 (young), muscle 0.5 and weight 0.5 (average: the base mesh, which has no target),
        # height 0.5 (neutral), race 1/3 each
        self.assertAlmostEqual(self.weight(weights, "african_male_young"), 0.5 / 3, places=6)
        self.assertEqual(self.weight(weights, "african_male_old"), 0.0)
        self.assertEqual(self.weight(weights, "universal_female_young_averagemuscle_maxweight"), 0.0)
        race = [i for i, n in enumerate(self.rig.shape_names) if not n.startswith("universal")
                and n.split("_")[0] in ("african", "asian", "caucasian")]
        self.assertAlmostEqual(weights[race].sum(), 1.0, places=5)
        values[self.mod("weight")] = 1.0
        weights, _ = self.rig.evaluate(values)
        self.assertAlmostEqual(self.weight(weights, "universal_female_young_averagemuscle_maxweight"), 0.5)

    def test_normalization(self):
        values = self.rig.default_values()
        african, asian, caucasian = self.mod("african"), self.mod("asian"), self.mod("caucasian")
        updates = self.rig.normalized(african, 0.6, values)
        self.assertAlmostEqual(updates[african] + updates[asian] + updates[caucasian], 1.0)
        self.assertAlmostEqual(updates[asian], 0.2)
        self.assertEqual(self.rig.normalized(self.mod("gender"), 2.0, values), {self.mod("gender"): 1.0})

    def test_apply_matches_usdskel(self):
        values = self.rig.default_values()
        values[self.mod("height")] = 1.0
        values[self.mod("age")] = 0.8
        weights, translations = self.rig.apply(values)
        anim = self.rig.animation
        np.testing.assert_allclose(np.array(anim.GetBlendShapeWeightsAttr().Get()), weights, atol=1e-6)
        # UsdSkel must now use the authored translations for the skeleton pose
        query = UsdSkel.Cache().GetSkelQuery(self.rig.skeleton)
        local = np.array(query.ComputeJointLocalTransforms(Usd.TimeCode.Default()))
        np.testing.assert_allclose(local[:, 3, :3], translations, atol=1e-4)
        self.assertGreater(np.abs(translations - self.rig._rest_t).max(), 1e-3, "maxheight moves joints")

    def test_values_round_trip(self):
        self.rig.write_values({self.mod("gender"): 0.9})
        self.assertAlmostEqual(self.rig.read_values()[self.mod("gender")], 0.9, places=6)

    def test_preview_images(self):
        with_image = [m for m in self.rig.modifiers if m.image]
        self.assertGreater(len(with_image), 200, "MakeHuman ships a slider image for most target modifiers")
        for m in with_image:
            self.assertTrue(os.path.isfile(m.image), m.image)
        foot = self.rig.modifiers[self.mod("l_foot_scale_decr_incr")]
        self.assertTrue(foot.image.replace("\\", "/").endswith("targets/armslegs/images/l-foot-scale-decr-incr.png"))
        self.assertEqual(humaneval.local_image(foot.image, "unused"), foot.image, "loose files need no extraction")


@unittest.skipUnless(os.path.isfile(HUMAN_USDZ), "run scripts/build_human.py first")
class PackageTest(unittest.TestCase):
    def test_package_is_self_contained(self):
        stage = Usd.Stage.Open(HUMAN_USDZ)
        root = humaneval.find_human(stage.GetDefaultPrim())
        rig = humaneval.HumanRig(root)
        self.assertEqual(len(rig.modifiers), 249)
        images = [m.image for m in rig.modifiers if m.image]
        self.assertGreater(len(images), 200)
        with tempfile.TemporaryDirectory() as cache:
            for image in images:
                self.assertTrue(Ar.IsPackageRelativePath(image), image)
                self.assertTrue(Ar.SplitPackageRelativePathOuter(image)[0].endswith("human.usdz"))
                extracted = humaneval.local_image(image, cache)
                with open(extracted, "rb") as f:
                    self.assertEqual(f.read(8), PNG_SIGNATURE, image)
            first = humaneval.local_image(images[0], cache)
            stamp = os.path.getmtime(first)
            self.assertEqual(humaneval.local_image(images[0], cache), first)
            self.assertEqual(os.path.getmtime(first), stamp, "extracted once, then reused")
        weights, _ = rig.evaluate(rig.default_values())
        np.testing.assert_allclose(np.array(rig.animation.GetBlendShapeWeightsAttr().Get()), weights, atol=1e-6)


if __name__ == "__main__":
    unittest.main()
