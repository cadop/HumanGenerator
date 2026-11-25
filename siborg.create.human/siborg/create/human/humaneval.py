"""Evaluate a human's HumanModifier values into blendshape weights and joint translations.

Implements the evaluation described in schema/schema.usda:

    labelWeight(m, label)  = piecewise-linear interpolation of m.value over m.knots
    weight(blendShape)     = product over i of  labelWeight(drivers[i], labels[i])               (ModifierTargetAPI)
    jointTranslations      = restTranslations + sum over b of  weight(b) * translationOffsets_b  (SkelTargetAPI)

Modifier values are the authored state; HumanRig.apply() writes the derived weights and translations to the human's
SkelAnimation. Only pxr and numpy are used (no Kit), so the build scripts and tests can use this module too. Prims and
properties are found by type and attribute name rather than through schema classes, so this works whether or not the
humanGenerator schema plugin is registered.
"""

import hashlib
import os
import re
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
from pxr import Ar, Sdf, Usd, UsdSkel, Vt

MODIFIER_TYPE = "HumanModifier"
GROUP_TYPE = "HumanModifierGroup"
HUMAN_KEY = "human"  # customData key marking a human's SkelRoot
# assetInfo key of AssetPreviewsAPI's default thumbnail (UsdMedia), the modifier's preview image. Read directly rather
# than through UsdMedia.AssetPreviewsAPI, whose getter returns nothing unless the API is applied (it is built into
# HumanModifier only when the humanGenerator schema is registered)
PREVIEW_KEY = "previews:thumbnails:default:defaultImage"


def label_weights(knots, labels, value: float) -> Dict[str, float]:
    """Weight of each label for a modifier value (see HumanModifier in schema.usda). Neutral (empty) labels and zero
    weights are left out."""
    n = len(knots)
    if n == 0:
        return {}
    if n == 1:
        return {labels[0]: 1.0} if labels[0] else {}
    v = min(max(float(value), knots[0]), knots[-1])
    i, t = n - 2, 1.0
    for j in range(n - 1):
        k0, k1 = knots[j], knots[j + 1]
        if v <= k1 and k1 > k0:  # First non-degenerate segment containing v
            i, t = j, (v - k0) / (k1 - k0)
            break
    out: Dict[str, float] = {}
    for label, w in ((labels[i], 1.0 - t), (labels[i + 1], t)):
        if label and w > 0.0:
            out[label] = out.get(label, 0.0) + w
    return out


def is_human(prim: Optional[Usd.Prim]) -> bool:
    return bool(prim) and prim.GetTypeName() == "SkelRoot" and bool(prim.GetCustomDataByKey(HUMAN_KEY))


def find_human(prim: Optional[Usd.Prim], search_depth: int = 3) -> Optional[Usd.Prim]:
    """The human SkelRoot containing prim (prim itself or an ancestor), else the first one beneath prim within
    search_depth levels, so selecting the Xform a human was added under also finds it."""
    p = prim
    while p and not p.IsPseudoRoot():
        if is_human(p):
            return p
        p = p.GetParent()
    if not prim:
        return None
    level = [prim]
    for _ in range(search_depth):
        level = [c for p in level for c in p.GetChildren()]
        for c in level:
            if is_human(c):
                return c
    return None


def local_image(resolved_path: str, cache_dir: str) -> str:
    """A plain file path for the image at resolved_path, for image widgets that can't read inside a .usdz package.

    Files outside packages are returned as they are. Package-relative paths are extracted through Ar into cache_dir,
    once per version of the package. Returns "" when there's no image or it can't be read.
    """
    if not resolved_path:
        return ""
    if not Ar.IsPackageRelativePath(resolved_path):
        return resolved_path if os.path.isfile(resolved_path) else ""
    outer, inner = Ar.SplitPackageRelativePathOuter(resolved_path)
    stamp = os.path.getmtime(outer) if os.path.isfile(outer) else 0
    key = hashlib.sha1(f"{outer}|{stamp}".encode()).hexdigest()[:12]  # A rebuilt package gets fresh copies
    target = os.path.join(cache_dir, key, *[p for p in re.split(r"[\[\]/\\]", inner) if p])
    if not os.path.isfile(target):
        asset = Ar.GetResolver().OpenAsset(Ar.ResolvedPath(resolved_path))
        if asset is None:
            return ""
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as f:
            f.write(bytes(asset.GetBuffer()))
    return target


class Modifier:
    """Static description of one HumanModifier prim."""

    def __init__(self, prim: Usd.Prim):
        self.prim = prim
        self.path = prim.GetPath()
        self.value_attr = prim.GetAttribute("value")
        self.knots = [float(k) for k in (prim.GetAttribute("knots").Get() or [])]
        self.labels = [str(l) for l in (prim.GetAttribute("labels").Get() or [])]
        self.default = float(prim.GetAttribute("defaultValue").Get() or 0.0)
        self.label = prim.GetAttribute("label").Get() or prim.GetName()
        self.normalization_group = str(prim.GetAttribute("normalizationGroup").Get() or "")
        image = prim.GetAssetInfoByKey(PREVIEW_KEY)
        # Resolved path of the preview image; inside a .usdz it is package-relative ("human.usdz[targets/...png]")
        self.image = image.resolvedPath if isinstance(image, Sdf.AssetPath) else ""
        self.min = self.knots[0] if self.knots else 0.0
        self.max = self.knots[-1] if self.knots else 1.0
        self.shape_count = 0  # Number of blendshapes this modifier drives; set by HumanRig


class HumanRig:
    """Evaluator and writer for one human (a SkelRoot with customData human = true).

    Build once per human and reuse; rebuild if the human's prims are resynced."""

    def __init__(self, skel_root: Usd.Prim):
        if not is_human(skel_root):
            raise ValueError(f"{skel_root.GetPath()} is not a human SkelRoot")
        self.root = skel_root
        self.path = skel_root.GetPath()
        self.stage = skel_root.GetStage()

        # Modifiers, in traversal order
        self.modifiers: List[Modifier] = [Modifier(p) for p in Usd.PrimRange(skel_root)
                                          if p.GetTypeName() == MODIFIER_TYPE]
        self.index: Dict[Sdf.Path, int] = {m.path: i for i, m in enumerate(self.modifiers)}
        self.normalization_groups: Dict[str, List[int]] = {}
        for i, m in enumerate(self.modifiers):
            if m.normalization_group:
                self.normalization_groups.setdefault(m.normalization_group, []).append(i)

        # Skeleton and the animation the weights and translations are written to
        skel_targets = UsdSkel.BindingAPI(skel_root).GetSkeletonRel().GetTargets()
        if not skel_targets:
            raise ValueError(f"{skel_root.GetPath()} has no skel:skeleton")
        self.skeleton = UsdSkel.Skeleton(self.stage.GetPrimAtPath(skel_targets[0]))
        anim_targets = UsdSkel.BindingAPI(self.skeleton.GetPrim()).GetAnimationSourceRel().GetTargets()
        if not anim_targets:
            raise ValueError(f"{self.skeleton.GetPath()} has no skel:animationSource")
        self.animation = UsdSkel.Animation(self.stage.GetPrimAtPath(anim_targets[0]))
        self.shape_names = [str(s) for s in (self.animation.GetBlendShapesAttr().Get() or [])]

        # Blendshape tokens -> BlendShape prims, from the bindings of the meshes under the human
        shape_paths: Dict[str, Sdf.Path] = {}
        for p in Usd.PrimRange(skel_root):
            if p.GetTypeName() != "Mesh":
                continue
            binding = UsdSkel.BindingAPI(p)
            tokens = binding.GetBlendShapesAttr().Get() or []
            for token, path in zip(tokens, binding.GetBlendShapeTargetsRel().GetTargets()):
                shape_paths.setdefault(str(token), path)

        # Drivers of each shape as (modifier index, label), and its joint offsets
        joints = [str(j) for j in (self.skeleton.GetJointsAttr().Get() or [])]
        joint_index = {j: i for i, j in enumerate(joints)}
        self.drivers: List[List[Tuple[int, str]]] = []
        self.offsets = np.zeros((len(self.shape_names), len(joints), 3), dtype=np.float64)
        for s, name in enumerate(self.shape_names):
            shape = self.stage.GetPrimAtPath(shape_paths[name]) if name in shape_paths else None
            drivers: List[Tuple[int, str]] = []
            if shape:
                targets = shape.GetRelationship("modifierTarget:drivers").GetTargets()
                labels = shape.GetAttribute("modifierTarget:labels").Get() or []
                if len(targets) == len(labels):
                    drivers = [(self.index[t], str(l)) for t, l in zip(targets, labels) if t in self.index]
                    if len(drivers) != len(targets):  # A driver outside this human: leave the shape alone
                        drivers = []
                st_joints = shape.GetAttribute("skelTarget:joints").Get() or []
                st_offsets = shape.GetAttribute("skelTarget:translationOffsets").Get() or []
                for j, o in zip(st_joints, st_offsets):
                    if str(j) in joint_index:
                        self.offsets[s, joint_index[str(j)]] = o
            self.drivers.append(drivers)
            for m, _ in drivers:
                self.modifiers[m].shape_count += 1

        # Rest pose, decomposed, so the animation can author complete joint transforms
        rest = self.skeleton.GetRestTransformsAttr().Get()
        if rest is None or len(rest) != len(joints):
            raise ValueError(f"{self.skeleton.GetPath()} needs restTransforms for every joint")
        self.joints = joints
        self.rest_translations, self.rest_rotations, self.rest_scales = UsdSkel.DecomposeTransforms(rest)
        self._rest_t = np.array(self.rest_translations, dtype=np.float64)

    # Values ------------------------------------------------------------------------------------------------------

    def read_values(self, time=Usd.TimeCode.Default()) -> np.ndarray:
        values = []
        for m in self.modifiers:
            v = m.value_attr.Get(time) if m.value_attr else None
            values.append(m.default if v is None else v)
        return np.array(values, dtype=np.float64)

    def default_values(self) -> np.ndarray:
        return np.array([m.default for m in self.modifiers], dtype=np.float64)

    def write_values(self, values: Dict[int, float], time=Usd.TimeCode.Default()) -> None:
        """Author modifier values (modifier index -> value) on the current edit target. Attributes that are already
        animated get a time sample at `time` instead of a default."""
        for i, v in values.items():
            attr = self.modifiers[i].value_attr
            attr.Set(float(v), time if attr.GetNumTimeSamples() else Usd.TimeCode.Default())

    def normalized(self, i: int, value: float, current: np.ndarray) -> Dict[int, float]:
        """Values to author when modifier i is set to value: just {i: value}, or, for a modifier in a normalization
        group, also the other members, rescaled so the group keeps summing to 1 (MakeHuman's ethnic sliders)."""
        m = self.modifiers[i]
        value = min(max(float(value), m.min), m.max)
        group = self.normalization_groups.get(m.normalization_group) if m.normalization_group else None
        if not group or len(group) < 2:
            return {i: value}
        others = [j for j in group if j != i]
        remaining = max(1.0 - value, 0.0)
        total = float(sum(current[j] for j in others))
        updates = {i: value}
        for j in others:
            updates[j] = current[j] * remaining / total if total > 1e-9 else remaining / len(others)
        return updates

    # Evaluation --------------------------------------------------------------------------------------------------

    def evaluate(self, values: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Blendshape weights (animation blendShapes order) and joint translations (skeleton joint order)."""
        lw = [label_weights(m.knots, m.labels, values[i]) for i, m in enumerate(self.modifiers)]
        weights = np.zeros(len(self.shape_names), dtype=np.float64)
        for s, drivers in enumerate(self.drivers):
            if not drivers:
                continue
            w = 1.0
            for m, label in drivers:
                w *= lw[m].get(label, 0.0)
                if w == 0.0:
                    break
            weights[s] = w
        translations = self._rest_t + np.einsum("s,sjk->jk", weights, self.offsets)
        return weights, translations

    def apply(self, values: Optional[np.ndarray] = None, time=Usd.TimeCode.Default()) -> Tuple[np.ndarray, np.ndarray]:
        """Evaluate values (read from the stage if None) and write the blendshape weights and joint transforms to the
        animation, on the current edit target."""
        if values is None:
            values = self.read_values(time)
        weights, translations = self.evaluate(values)
        anim = self.animation
        # UsdSkel only uses an animation's joint transforms when translations, rotations and scales are all present
        if not anim.GetJointsAttr().HasAuthoredValue():
            anim.CreateJointsAttr().Set(Vt.TokenArray(self.joints))
        if not anim.GetRotationsAttr().HasAuthoredValue():
            anim.CreateRotationsAttr().Set(self.rest_rotations)
        if not anim.GetScalesAttr().HasAuthoredValue():
            anim.CreateScalesAttr().Set(self.rest_scales)
        anim.CreateTranslationsAttr().Set(Vt.Vec3fArray.FromNumpy(translations.astype(np.float32)), time)
        anim.CreateBlendShapeWeightsAttr().Set(Vt.FloatArray.FromNumpy(weights.astype(np.float32)), time)
        return weights, translations

    # Queries -----------------------------------------------------------------------------------------------------

    def groups(self) -> Iterable[Tuple[Usd.Prim, int]]:
        """HumanModifierGroup prims with their nesting depth (1 = top level), in traversal (UI) order."""
        base = self.path.pathElementCount
        for p in Usd.PrimRange(self.root):
            if p.GetTypeName() == GROUP_TYPE:
                yield p, p.GetPath().pathElementCount - base - 1
