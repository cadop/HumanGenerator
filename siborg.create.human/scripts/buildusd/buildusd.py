# Build the human USD file outside of Omniverse

import json
import os

from animation import build_anim
from meshes import load_basemesh
from pxr import Sdf, Usd, UsdGeom, UsdSkel
from skeletons import build_skeleton
from targets import import_targets
from modifiers import bind_modifier_targets, import_modifiers
import materials


def target_groups(modifiers_path: str):
    """Target folders (under data/targets) that the modifiers in modifiers_path drive, so only targets a slider can
    reach become blendshapes. A modifier group "macrodetails-height" uses the folder "macrodetails"."""
    with open(modifiers_path) as f:
        return sorted({entry["group"].split("-")[0] for entry in json.load(f)})


def make_human(save_path: str = None):
    # Create a stage
    stage = Usd.Stage.CreateInMemory()

    # Stage must have a valid start time code for animation to work
    stage.SetStartTimeCode(1)

    # Set the up axis
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

    # Set the units/scale
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    # Create a root prim
    root = stage.DefinePrim("/Human", "Xform")
    stage.SetDefaultPrim(root)

    # Define a SkelRoot.
    rootPath = Sdf.Path(f"{root.GetPath()}/skel_root")
    skel_root = UsdSkel.Root.Define(stage, rootPath)
    # Add custom data to the prim by key, designating the prim is a human
    skel_root.GetPrim().SetCustomDataByKey("human", True)

    # Get the extension path
    ext_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Load the base mesh from a file
    base_mesh_file = os.path.join(ext_path, "data", "3dobjs", "base.obj")
    meshes = load_basemesh(stage, rootPath, base_mesh_file)

    # Create a material
    mtl = materials.create_preview_surface_material(stage)

    # Bind the material to the meshes
    for mesh in meshes:
        materials.bind_material(mesh, mtl)

    # Create the skeleton
    skeleton = build_skeleton(stage, skel_root, ext_path)

    prim = skel_root.GetPrim()
    # Define the modifiers (HumanModifierGroup / HumanModifier prims)
    modifiers_path = os.path.join(ext_path, "data", "modifiers", "modeling_modifiers.json")
    modifier_index = import_modifiers(stage, prim, modifiers_path)

    # Import the targets
    for group in target_groups(modifiers_path):
        targets_path = os.path.join(ext_path, "data", "targets", group)
        if not os.path.isdir(targets_path):
            print(f"Skipping missing target folder {targets_path}")
            continue
        import_targets(stage, prim, targets_path)

    # Map each blendshape to the modifiers that drive it (ModifierTargetAPI)
    bind_modifier_targets(stage, prim, modifier_index)

    # Create and bind animation for blendshapes
    build_anim(stage, skeleton, blendshapes=True)

    # Save the stage to a file
    save_path = save_path or os.path.join(ext_path, "data", "human_base.usd")
    print(f"Saving to {save_path}")
    stage.Export(save_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build the human USD stage outside of Omniverse.")
    parser.add_argument("--out", help="output path (default: data/human_base.usd)")
    make_human(parser.parse_args().out)
