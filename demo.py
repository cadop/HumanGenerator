from pxr import Sdf, Usd, UsdGeom, UsdSkel, Tf
import carb
import omni
import omni.usd
import numpy as np
import os
import warnings

SCRIPT_ROOT = r"C:\users\josh\documents\github\ov_makehuman\exts\siborg.create.human"

def make_blendshapes():
    # Get USD context and stage
    usd_context = omni.usd.get_context()
    stage = usd_context.get_stage()

    stage.SetStartTimeCode(1)
    stage.SetEndTimeCode(100)

    # Get the default root prim
    root = stage.GetDefaultPrim()

    # Define a SkelRoot.
    rootPath = Sdf.Path(f"{root.GetPath()}/skel_root")
    skel_root = UsdSkel.Root.Define(stage, rootPath)
    # stage.SetDefaultPrim(skel_root.GetPrim())

    # Define a Skeleton, and associate with root.
    skeleton = UsdSkel.Skeleton.Define(stage, rootPath.AppendChild("skeleton"))
    rootBinding = UsdSkel.BindingAPI.Apply(skel_root.GetPrim())
    rootBinding.CreateSkeletonRel().AddTarget(skeleton.GetPrim().GetPath())

    # Get the human prim reference
    mesh = stage.GetPrimAtPath(f"{root.GetPath()}/base")

    # Get the mesh itself
    mesh = get_first_child_mesh_df(mesh)
    
    target_names = []
    target_paths = []


    # Traverse the MakeHuman targets directory
    targets_dir = os.path.join(SCRIPT_ROOT, "data","targets")
    for target_group in os.listdir(targets_dir):
        target_group_dir = os.path.join(targets_dir, target_group)

        for target in os.listdir(target_group_dir):
            if not target.endswith(".target"):
                continue
            target_filepath = os.path.join(target_group_dir, target)
            print(f"Importing {target_filepath}")
            target = mhtarget_to_blendshape(stage, mesh.GetPrim(), target_group_dir, target_filepath)
            target_names.append(target.GetPrim().GetName())
            target_paths.append(target.GetPrim().GetPath())

    # Bind mesh to blend shapes.
    meshBinding = UsdSkel.BindingAPI.Apply(mesh.GetPrim())
    meshBinding.CreateBlendShapesAttr().Set(target_names)
    meshBinding.CreateBlendShapeTargetsRel().SetTargets(target_paths)

    # Define an Animation (with blend shape weight time-samples).
    animation = UsdSkel.Animation.Define(stage, skeleton.GetPrim().GetPath().AppendChild("animation"))
    # animation.CreateBlendShapesAttr().Set(["nose"])
    # weightsAttr = animation.CreateBlendShapeWeightsAttr()
    # weightsAttr.Set([0], 1)
    # weightsAttr.Set([1], 50)
    # weightsAttr.Set([0], 100)

    # Bind Skeleton to animation.
    skeletonBinding = UsdSkel.BindingAPI.Apply(skeleton.GetPrim())
    skeletonBinding.CreateAnimationSourceRel().AddTarget(animation.GetPrim().GetPath())


def get_first_child_mesh_df(parent_prim: Usd.Prim) -> Usd.Prim:
    # Depth-first search for the first mesh prim
    for child_prim in parent_prim.GetChildren():
        if UsdGeom.Mesh(child_prim):
            return child_prim
        else:
            return get_first_child_mesh_df(child_prim)


def mhtarget_to_blendshape(stage, prim, group_dir, path : str):
    """Import a blendshape from a MakeHuman target file.

    Parameters
    ----------
    stage : Usd.Stage
        The stage to import the blendshape onto.
    prim : Usd.Prim
        The prim to import the blendshape onto.
    group_dir : str
        Path to the directory containing the target file.
    path : str
        Path to the target file.
    """

    target_name = Tf.MakeValidIdentifier(os.path.splitext(os.path.basename(path))[0])
    group_name = Tf.MakeValidIdentifier(os.path.basename(group_dir))
    group = stage.DefinePrim(prim.GetPath().AppendChild(group_name))
    blendshape = UsdSkel.BlendShape.Define(stage, group.GetPath().AppendChild(target_name))

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            raw = np.loadtxt(path, dtype=np.float32)
            # The first column is the vertex index, the rest are the offsets.
    except Warning as e:
        print(f"Warning: {e}")
        # If the file is malformed, just create an empty blendshape.
        raw = np.zeros((0, 4), dtype=np.float32)

    indices = raw[:, 0].astype(np.int32)
    offsets = raw[:, 1:]
    blendshape.CreateOffsetsAttr().Set(offsets)
    blendshape.CreatePointIndicesAttr().Set(indices)

    return blendshape

def load_obj(filename):
    with open(filename, 'r') as infile:
        lines = infile.readlines()

    vertices = []
    texture_coords = []
    normals = []
    faces = []

    for line in lines:
        parts = line.strip().split()
        if parts[0] == 'v':
            vertices.append(parts[1:])
        elif parts[0] == 'vt':
            texture_coords.append(parts[1:])
        elif parts[0] == 'vn':
            normals.append(parts[1:])
        elif parts[0] == 'f':
            faces.append(parts[1:5])  # Only consider the first 4 vertices

    vertices = np.array(vertices, dtype=float)
    texture_coords = np.array(texture_coords, dtype=float) if texture_coords else None
    normals = np.array(normals, dtype=float) if normals else None
    faces = np.array([[list(map(int, vert.split('/'))) for vert in face] for face in faces])

    return vertices, texture_coords, normals, faces

make_blendshapes()
