# Build the human USD file outside of Omniverse

import os
from pxr import Usd, Sdf, UsdSkel, Tf
import numpy as np
import warnings

def make_human():

    # Create a stage
    stage = Usd.Stage.CreateInMemory()

    # Stage must have a valid start time code for animation to work
    stage.SetStartTimeCode(1)

    # Create a root prim
    root = stage.DefinePrim("/Human", "Xform")
    stage.SetDefaultPrim(root)

    # Define a SkelRoot.
    rootPath = Sdf.Path(f"{root.GetPath()}/skel_root")
    skel_root = UsdSkel.Root.Define(stage, rootPath)
    # Add custom data to the prim by key, designating the prim is a human
    skel_root.GetPrim().SetCustomDataByKey("human", True)
    # Define a Skeleton, and associate with root.
    skeleton = UsdSkel.Skeleton.Define(stage, rootPath.AppendChild("skeleton"))
    rootBinding = UsdSkel.BindingAPI.Apply(skel_root.GetPrim())
    rootBinding.CreateSkeletonRel().AddTarget(skeleton.GetPrim().GetPath())

    # Load the base mesh from a file
    ext_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base_mesh_file = os.path.join(ext_path, "data", "basemesh.geo.usda")
    skel_root.GetPrim().GetReferences().AddReference(base_mesh_file, "/Root")

    prim = stage.GetPrimAtPath("/Human/skel_root/base")

    target_names = []

    # Traverse the MakeHuman targets directory
    targets_dir = os.path.join(ext_path, "data", "targets")
    for dirpath, _, filenames in os.walk(targets_dir):
        for filename in filenames:
            # Skip non-target files
            if not filename.endswith(".target"):
                continue
            print(f"Importing {filename}")
            target = mhtarget_to_blendshapes(stage, prim, os.path.join(dirpath, filename))
            target_names.append(target)


    # Define an Animation (with blend shape weight time-samples).
    animation = UsdSkel.Animation.Define(stage, skeleton.GetPrim().GetPath().AppendChild("animation"))
    animation.CreateBlendShapesAttr().Set(target_names)
    weightsAttr = animation.CreateBlendShapeWeightsAttr(np.zeros(len(target_names)))
    weightsAttr.Set(np.zeros(len(target_names)), 0)
    weightsAttr.Set(np.ones(len(target_names)), 10)

    # Bind Skeleton to animation.
    skeletonBinding = UsdSkel.BindingAPI.Apply(skeleton.GetPrim())
    anim_path=animation.GetPrim().GetPath()
    skeletonBinding.CreateAnimationSourceRel().AddTarget(anim_path)

    # Save the stage to a file
    stage.Export(os.path.join(ext_path,"data","human_base.usda"))


def mhtarget_to_blendshapes(stage, prim, path : str) -> Sdf.Path:
    """Import a blendshape from a MakeHuman target file.

    Parameters
    ----------
    stage : Usd.Stage
        The stage to import the blendshape onto.
    prim : Usd.Prim
        The prim to import the blendshape onto. Contains multiple meshes. Indices are not shared between meshes,
        so we need to create a separate blendshape for each mesh and keep track of any index offsets.
    path : str
        Path to the target file.
    """

    # Get the group directory
    group_dir = os.path.dirname(path)
    target_name = Tf.MakeValidIdentifier(os.path.splitext(os.path.basename(path))[0])
    # group_name = Tf.MakeValidIdentifier(os.path.basename(group_dir))
    
    # group = stage.DefinePrim(prim.GetPath().AppendChild(group_name))
    # blendshape = UsdSkel.BlendShape.Define(stage, group.GetPath().AppendChild(target_name))

        # Load the target file
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            raw = np.loadtxt(path, dtype=np.float32)
            # The first column is the vertex index, the rest are the offsets.
    except Warning as e:
        print(f"Warning: {e}")
        # Some of the files are empty, so just skip them
        return

    # The first column is the vertex index, the rest are the offsets.
    changed_indices = raw[:, 0].astype(np.int32)
    changed_offsets = raw[:, 1:]

    # Get all the meshes. We need to determine which meshes are affected by this target
    
    meshes = prim.GetChildren()

    # The meshes' indices are not shared, so we need to keep track of the starting index for each mesh
    index_start = 0
    for mesh in meshes:
        # The next index offset is the current offset plus the number of vertices in the current mesh
        verts = len(mesh.GetAttribute("points").Get())
        index_end = index_start + verts

        if np.any(np.logical_and(changed_indices >= index_start, changed_indices < index_end)):
            print(f"{target_name} targets mesh {mesh.GetPath()}")
            # This mesh is affected by the target, so create a blendshape for it
            blendshape = UsdSkel.BlendShape.Define(stage, mesh.GetPath().AppendChild(target_name))
            indices = np.arange(verts)
            offsets = np.zeros((verts, 3), dtype=np.float32)
            mask = np.logical_and(changed_indices >= index_start, changed_indices < index_end)
            target_indices = changed_indices[mask] - index_start
            target_offsets = changed_offsets[mask]
            offsets[target_indices] = target_offsets
            # Set the indices and offsets
            blendshape.CreateOffsetsAttr().Set(offsets)
            blendshape.CreatePointIndicesAttr().Set(indices)
            # Bind mesh to blend shapes.
            meshBinding = UsdSkel.BindingAPI.Apply(mesh.GetPrim())
            meshBinding.CreateBlendShapeTargetsRel().AddTarget(blendshape.GetPath())
            # Get the existing blendshapes for this mesh
            existing_blendshapes = meshBinding.GetBlendShapesAttr().Get()
            # Add the new blendshape
            if existing_blendshapes:
                existing_blendshapes = list(existing_blendshapes)
                existing_blendshapes.append(target_name)
            else:
                existing_blendshapes = [target_name]
            # Set the updated blendshapes for this mesh.
            meshBinding.GetBlendShapesAttr().Set(existing_blendshapes)
        # Update the index offset
        index_start = index_end

    return target_name

if __name__ == "__main__":
    make_human()