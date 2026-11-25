"""Author MakeHuman modifiers as HumanModifierGroup / HumanModifier prims, and map blendshapes to them with
ModifierTargetAPI (see schema/schema.usda).

A modifier maps its value onto labels through knots (piecewise-linear). A blendshape's weight is the product of one
label weight per driving modifier: ordinary targets have one driver, macro targets one per macro variable.
"""

import json
import os
from typing import Dict, List, Tuple

from pxr import Sdf, Tf, Usd, UsdMedia, UsdSkel

import humanschema

RACES = ("african", "asian", "caucasian")
# Neighbouring knots closer than this with the same label are one knot (macro.json pads ranges by tiny amounts)
_KNOT_MERGE = 1e-3


class ModifierIndex:
    """What bind_modifier_targets needs to map blendshape names to (modifier prim, label) drivers."""

    def __init__(self):
        self.targets: Dict[str, Tuple[Sdf.Path, str]] = {}  # blendshape name -> (target modifier, label)
        self.macrovars: Dict[str, Sdf.Path] = {}  # macro variable (e.g. "age", "race:african") -> modifier
        self.labels: Dict[str, set] = {}  # macro variable -> its non-empty labels
        self.combinations: Dict[str, List[str]] = {}  # combination name -> ordered macro variables


def knots_from_parts(parts: List[dict]) -> Tuple[List[float], List[str]]:
    """Convert macro.json "parts" (low/high labels over [lowest, highest] ranges) to knots and labels."""
    knots, labels = [], []
    for part in parts:
        for pos, label in ((max(part["lowest"], 0.0), part["low"]), (min(part["highest"], 1.0), part["high"])):
            pos = round(pos, 4)
            if labels and labels[-1] == label and abs(knots[-1] - pos) < _KNOT_MERGE:
                continue
            knots.append(pos)
            labels.append(label)
    return knots, labels


def _target_label(group: str, target: str) -> str:
    """Display label for a target modifier, e.g. "l-foot-scale" -> "L Foot Scale" (group prefix dropped)."""
    words = target.split("-")
    if len(words) > 1 and words[0] == group:
        words = words[1:]
    return " ".join(w.capitalize() for w in words)


def _image(ext_data: str, group: str, filename: str):
    """Relative asset path to a MakeHuman preview image, if it exists. Relative to data/, where the stage is saved."""
    rel = f"targets/{group}/images/{filename}"
    return Sdf.AssetPath(f"./{rel}") if os.path.isfile(os.path.join(ext_data, rel)) else None


def import_modifiers(stage: Usd.Stage, human: Usd.Prim, modifiers_path: str) -> ModifierIndex:
    """Define a HumanModifierGroup per MakeHuman group under <human>/modifiers, with a HumanModifier per modifier.

    Hyphenated groups ("macrodetails-height") are merged into their base group ("macrodetails"), as MakeHuman shows
    them. Returns the index used by bind_modifier_targets.
    """
    data_dir = os.path.dirname(os.path.dirname(modifiers_path))
    with open(os.path.join(os.path.dirname(modifiers_path), "macro.json")) as f:
        macro = json.load(f)
    with open(modifiers_path) as f:
        groups = json.load(f)

    index = ModifierIndex()
    index.combinations = {
        name: [{"proportions": "bodyproportions"}.get(v, v) for v in variables]
        for name, variables in macro["combinations"].items()
    }
    root = human.GetPath().AppendChild("modifiers")
    stage.DefinePrim(root, "Scope")

    for group in groups:
        base = group["group"].split("-")[0]
        group_prim = stage.GetPrimAtPath(root.AppendChild(Tf.MakeValidIdentifier(base)))
        if not group_prim:
            group_prim = humanschema.define(stage, root.AppendChild(Tf.MakeValidIdentifier(base)), "HumanModifierGroup")
            humanschema.set_attr(group_prim, "HumanModifierGroup", "label", base.capitalize())

        for data in group["modifiers"]:
            normalization = ""
            image = None
            if "target" in data:
                target = data["target"]
                name = Tf.MakeValidIdentifier(target)
                label = _target_label(base, target)
                if "min" in data and "max" in data:
                    # A target can have several direction pairs (r-foot-trans in/out and backward/forward), so the
                    # pair is part of the modifier's identity, as in MakeHuman ("r-foot-trans-in|out")
                    name = Tf.MakeValidIdentifier(f"{target}-{data['min']}-{data['max']}")
                    label = f"{label} {data['min'].capitalize()}/{data['max'].capitalize()}"
                    knots, labels = [-1.0, 0.0, 1.0], [data["min"], "", data["max"]]
                    shapes = {data["min"]: f"{target}-{data['min']}", data["max"]: f"{target}-{data['max']}"}
                    image = _image(data_dir, base, f"{target}-{data['min']}-{data['max']}.png")
                else:
                    knots, labels = [0.0, 1.0], ["", "incr"]
                    shapes = {"incr": target}
                    image = _image(data_dir, base, f"{target}.png")
                default = 0.0
            else:
                var = data["macrovar"].lower()
                name = var
                if data.get("modifierType") == "EthnicModifier":
                    knots, labels = [0.0, 1.0], ["", var]
                    label = data["macrovar"].capitalize()
                    default = 1.0 / len(RACES)
                    normalization = "race"
                else:
                    knots, labels = knots_from_parts(macro["macrotargets"][var]["parts"])
                    label = macro["macrotargets"][var]["label"]
                    default = (knots[0] + knots[-1]) / 2
                shapes = {}

            prim = humanschema.define(stage, group_prim.GetPath().AppendChild(name), "HumanModifier")
            humanschema.set_attr(prim, "HumanModifier", "label", label)
            humanschema.set_attr(prim, "HumanModifier", "knots", knots)
            humanschema.set_attr(prim, "HumanModifier", "labels", labels)
            humanschema.set_attr(prim, "HumanModifier", "defaultValue", default)
            humanschema.set_attr(prim, "HumanModifier", "value", default)
            if normalization:
                humanschema.set_attr(prim, "HumanModifier", "normalizationGroup", normalization)
            if image:
                # The slider's preview image: the default thumbnail of AssetPreviewsAPI, built into HumanModifier.
                # Stored in assetInfo, so it's written the same whether or not the schema is registered
                thumbnails = UsdMedia.AssetPreviewsAPI.Thumbnails()
                thumbnails.defaultImage = image
                UsdMedia.AssetPreviewsAPI(prim).SetDefaultThumbnails(thumbnails)

            # Index for mapping blendshapes back to this modifier. targets.py names a blendshape after its target file
            # (e.g. l-foot-scale-decr.target -> l_foot_scale_decr)
            for slot, shape in shapes.items():
                index.targets[Tf.MakeValidIdentifier(shape)] = (prim.GetPath(), slot)
            if "macrovar" in data:
                key = f"race:{name}" if normalization == "race" else name
                index.macrovars[key] = prim.GetPath()
                index.labels[key] = {l for l in labels if l}
    return index


def _macro_drivers(index: ModifierIndex, tokens: List[str]):
    """Match label tokens (e.g. ["female", "young", ...]) to a macro combination. Returns [(modifier, label)] or None."""
    for variables in index.combinations.values():
        if len(variables) != len(tokens):
            continue
        drivers = []
        for var, token in zip(variables, tokens):
            key = f"race:{token}" if var == "race" else var
            if key not in index.macrovars or token not in index.labels[key]:
                break
            drivers.append((index.macrovars[key], token))
        else:
            return drivers
    return None


def bind_modifier_targets(stage: Usd.Stage, human: Usd.Prim, index: ModifierIndex) -> List[str]:
    """Apply ModifierTargetAPI to every BlendShape under <human>/targets, pointing at the modifiers that drive it.

    Target blendshapes are matched by name to the modifier that created them. Macro blendshapes ("universal_female_
    young_...", "height_male_old_...", "african_female_baby") are matched label by label against macro.json's
    combinations, ignoring a leading folder prefix. Returns the names of blendshapes no modifier drives.
    """
    unmapped = []
    for prim in Usd.PrimRange(human.GetChild("targets")):
        if not prim.IsA(UsdSkel.BlendShape):
            continue
        name = prim.GetName()
        if name in index.targets:
            drivers = [index.targets[name]]
        else:
            tokens = name.split("_")
            drivers = _macro_drivers(index, tokens) or _macro_drivers(index, tokens[1:])
        if not drivers:
            unmapped.append(name)
            continue
        humanschema.apply_api(prim, "ModifierTargetAPI")
        humanschema.set_targets(prim, "ModifierTargetAPI", "modifierTarget:drivers", [path for path, _ in drivers])
        humanschema.set_attr(prim, "ModifierTargetAPI", "modifierTarget:labels", [label for _, label in drivers])
    if unmapped:
        print(f"No modifier drives {len(unmapped)} blendshapes, e.g. {unmapped[:3]}")
    return unmapped
