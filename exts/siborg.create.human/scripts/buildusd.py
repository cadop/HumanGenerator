# Build the human USD file outside of Omniverse

import os
from pxr import Usd, Sdf, UsdSkel, Tf, UsdGeom, Gf
import numpy as np
import warnings
from dataclasses import dataclass
from typing import List
import json

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
    

    # Load the base mesh from a file
    ext_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base_mesh_file = os.path.join(ext_path, "data", "3dobjs", "base.obj")
    meshes = load_obj(base_mesh_file)
    for m in meshes:
        create_geom(stage, rootPath.AppendChild(m.name), m)

    rig = load_skel_json(os.path.join(ext_path, "data","rigs","standard","default"))
    skeleton = create_skeleton(stage, skel_root, rig)

    # # Traverse the MakeHuman targets directory
    # targets_dir = os.path.join(ext_path, "data", "targets")
    # for dirpath, _, filenames in os.walk(targets_dir):
    #     for filename in filenames:
    #         # Skip non-target files
    #         if not filename.endswith(".target"):
    #             continue
    #         print(f"Importing {filename}")
    #         mhtarget_to_blendshapes(stage, prim, os.path.join(dirpath, filename))

    # # Traverse all meshes and create a list of the blendshape target names
    # target_names = []
    # for mesh in [m for m in prim.GetChildren() if m.IsA(UsdGeom.Mesh)]:
    #     meshBinding = UsdSkel.BindingAPI.Apply(mesh.GetPrim())
    #     blendshapes = meshBinding.GetBlendShapesAttr().Get()
    #     if blendshapes:
    #         print(f"Mesh {mesh.GetPath()} has blendshapes {blendshapes}\n")
    #         target_names.extend(blendshapes)

    # # Define an Animation (with blend shape weight time-samples).
    # animation = UsdSkel.Animation.Define(stage, skeleton.GetPrim().GetPath().AppendChild("animation"))
    # animation.CreateBlendShapesAttr().Set(target_names)
    # weightsAttr = animation.CreateBlendShapeWeightsAttr()
    # weightsAttr.Set(np.zeros(len(target_names)), 0)

    # # Bind Skeleton to animation.
    # skeletonBinding = UsdSkel.BindingAPI.Apply(skeleton.GetPrim())
    # anim_path=animation.GetPrim().GetPath()
    # skeletonBinding.CreateAnimationSourceRel().AddTarget(anim_path)

    # Save the stage to a file
    save_path = os.path.join(ext_path, "data", "human_base.usd")
    print(f"Saving to {save_path}")
    stage.Export(save_path)


def create_skeleton(stage, skel_root, rig):
    # Define a Skeleton, and associate with root.
    rootPath = skel_root.GetPath()
    skeleton = UsdSkel.Skeleton.Define(stage, rootPath.AppendChild("skeleton"))
    rootBinding = UsdSkel.BindingAPI.Apply(skel_root.GetPrim())
    rootBinding.CreateSkeletonRel().AddTarget(skeleton.GetPrim().GetPath())

    # Determine the root, which has no parent. If there are multiple roots, use the last one.
    root = [name for name, item in rig.items() if item["parent"] == ""][-1]

    visited = []  # List to keep track of visited bones.
    queue = [[root, rig[root]]]  # Initialize a queue
    path_queue = [root]  # Keep track of paths in a parallel queue
    joint_paths = [root]  # Keep track of joint paths
    joint_names = [root]  # Keep track of joint names
    bind_xforms = [Gf.Matrix4d(np.eye(4))]  # Bind xforms are in world space
    rest_xforms = [Gf.Matrix4d(np.eye(4))]  # Rest xforms are in local space

    # Traverse skeleton (breadth-first) and store joint data
    while queue:
        v = queue.pop(0)
        path = path_queue.pop(0)
        for neighbor in v[1]["children"].items():
            if neighbor[0] not in visited:
                visited.append(neighbor[0])
                queue.append(neighbor)
                child_path = path+"/"+Tf.MakeValidIdentifier(neighbor[0])
                path_queue.append(child_path)
                joint_paths.append(child_path)
                joint_names.append(neighbor[0])
                head = neighbor[1]["head"]["default_position"]
                tail = neighbor[1]["tail"]["default_position"]
                roll = neighbor[1]["roll"]
                parent_idx = joint_names.index(v[0])
                parent_head = v[1]["head"]["default_position"]
                rest_xform, bind_xform = compute_transforms(head, tail, roll, parent_head)
                rest_xforms.append(Gf.Matrix4d(rest_xform))
                bind_xforms.append(Gf.Matrix4d(bind_xform))


    skeleton.CreateJointNamesAttr(joint_names)
    skeleton.CreateJointsAttr(joint_paths)
    skeleton.CreateBindTransformsAttr(bind_xforms)
    skeleton.CreateRestTransformsAttr(rest_xforms)
    return skeleton



def compute_transforms(head, tail, roll, parent_head=None):
    # Bind transform is in world space
    bind_transform = np.eye(4)
    bind_transform[:3, 3] = np.array(head)

    # If a parent head is provided, adjust the head to be in local space.
    if parent_head is not None:
        local_head = np.array(head) - np.array(parent_head)
    else:
        local_head = np.array(head)
    rest_transform = np.eye(4)
    rest_transform[:3, 3] = local_head

    # Compute the primary axis direction (bone's y-axis)
    y_axis = np.array(tail) - np.array(head)
    # y_axis = np.array(tail) - np.array(head)
    y_axis = y_axis / np.linalg.norm(y_axis)

    # 2. Determine a temporary Z-axis.
    world_side = np.array([1, 0, 0])
    z_axis = np.cross(y_axis, world_side)

    # Check if vectors' magnitudes are too small
    if np.linalg.norm(z_axis) < 1e-8:
        # If the y-axis is almost aligned with world_side, use a different world vector
        world_side = np.array([0, 0, 1])
        z_axis = np.cross(y_axis, world_side)

    # Compute x-axis using cross product
    x_axis = np.cross(y_axis, z_axis)

    # Normalize axes
    x_axis = x_axis / np.linalg.norm(x_axis)
    z_axis = z_axis / np.linalg.norm(z_axis)

    # Apply roll
    cos_roll = np.cos(roll)
    sin_roll = np.sin(roll)
    x_axis_new = cos_roll * x_axis - sin_roll * z_axis
    z_axis_new = sin_roll * x_axis + cos_roll * z_axis
    x_axis, z_axis = x_axis_new, z_axis_new

    # Construct the 3x3 rotation matrix
    rotation_matrix = np.array([x_axis, y_axis, z_axis])

    rest_transform[:3, :3] = rotation_matrix
    bind_transform[:3, :3] = rotation_matrix

    return rest_transform.T, bind_transform


def mhtarget_to_blendshapes(stage, prim, path : str) -> [Sdf.Path]:
    """Import a blendshape from a MakeHuman target file.

    Parameters
    ----------
    stage : Usd.Stage
        The stage to import the blendshape onto.
    prim : Usd.Prim
        The prim to import the blendshape onto. Contains multiple meshes.
    path : str
        Path to the target file.
    """

    # The original ranges for the indices of the mesh vertices
    # See http://www.makehumancommunity.org/wiki/Documentation:Basemesh
    # index_ranges = {
    #     'body': (0, 13379),
    #     'helper_tongue': (13380, 13605),
    #     'joints': (13606, 14597),
    #     'helper_x_eye': (14598, 14741),
    #     'helper_x_eyelashes-y': (14742, 14991),
    #     'helper_lower_teeth': (14992, 15059),
    #     'helper_upper_teeth': (15060, 15127),
    #     'helper_genital': (15128, 15327),
    #     'helper_tights': (15328, 18001),
    #     'helper_skirt': (18002, 18721),
    #     'helper_hair': (18722, 19149),
    #     'ground': (19150, 19157)
    # }

    path_components = path.split(os.path.sep)[path.split(os.path.sep).index("targets")+1:-1]
    group_name = Tf.MakeValidIdentifier(path_components[0])
    target_basename = os.path.splitext(os.path.basename(path))[0]
    prefix = "_".join(path_components[1:]) or ""
    target_name = f"{prefix}_{target_basename}" if prefix else target_basename
    target_name = Tf.MakeValidIdentifier(target_name)
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
    
    meshes = [prim for prim in prim.GetChildren() if prim.IsA(UsdGeom.Mesh)]

    for mesh in meshes:
        vert_idxs = mesh.GetAttribute("faceVertexIndices").Get()
        index_start = np.min(vert_idxs)
        index_end = np.max(vert_idxs) + 1
        if np.any(np.logical_and(changed_indices >= index_start, changed_indices < index_end)):
            print(f"{target_name} targets mesh {mesh.GetPath()}")
            # This mesh is affected by the target, so create a blendshape for it
            group = stage.DefinePrim(mesh.GetPath().AppendChild(group_name))
            blendshape = UsdSkel.BlendShape.Define(stage, group.GetPath().AppendChild(target_name))
            indices = np.array(changed_indices)
            offsets = changed_offsets[np.isin(changed_indices, indices)]
            blendshape.CreateOffsetsAttr().Set(offsets)
            blendshape.CreatePointIndicesAttr().Set(indices)
            # Bind mesh to blend shapes.
            meshBinding = UsdSkel.BindingAPI.Apply(mesh.GetPrim())
            meshBinding.CreateBlendShapeTargetsRel().AddTarget(blendshape.GetPath())
            # Get the existing blendshapes for this mesh
            existing_blendshapes = meshBinding.GetBlendShapesAttr().Get()
            bound_blendshapes = [b.name for b in meshBinding.GetBlendShapeTargetsRel().GetTargets()]
            # Add the new blendshape
            if existing_blendshapes:
                if target_name in existing_blendshapes:
                    print(f"Blendshape {target_name} already exists on {mesh.GetPath()}")
                    continue
                existing_blendshapes = list(existing_blendshapes)
                existing_blendshapes.append(target_name)
            else:
                existing_blendshapes = [target_name]
            if len(existing_blendshapes) != len(bound_blendshapes):
                bound_set = set(bound_blendshapes)
                existing_set = set(existing_blendshapes)
                unbound = existing_set.difference(bound_set)
                mismatched = bound_set.difference(existing_set)
                print(f"Blendshapes {unbound} exist but are not bound")
                print(f"Blendshapes {mismatched} are bound but do not exist")
            # Set the updated blendshapes for this mesh.
            meshBinding.GetBlendShapesAttr().Set(existing_blendshapes)

@dataclass
class MeshData:
    name: str
    vertices: list
    uvs: list
    normals: list
    faces: list
    vert_indices: list
    uv_indices: list
    normal_indices: list
    nface_verts: list


def create_geom(stage, path: str, mesh_data: MeshData):
    """Create a UsdGeom.Mesh prim from vertices and faces.

    Parameters
    ----------
    stage : Usd.Stage
        The stage to create the mesh on.
    path : str
        The path at which to create the mesh prim
    mesh_data : MeshData
        The mesh data to use to create the mesh prim. Contains vertices, faces, and normals.
    """
    meshGeom = UsdGeom.Mesh.Define(stage, path)

    # Set vertices. This is a list of tuples for ALL vertices in an unassociated
    # cloud. Faces are built based on indices of this list.
    #   Example: 3 explicitly defined vertices:
    #   meshGeom.CreatePointsAttr([(-10, 0, -10), (-10, 0, 10), (10, 0, 10)]
    meshGeom.CreatePointsAttr(mesh_data.vertices)

    # Set face vertex count. This is an array where each element is the number
    # of consecutive vertex indices to include in each face definition, as
    # indices are given as a single flat list. The length of this list is the
    # same as the number of faces
    #   Example: 4 faces with 4 vertices each
    #   meshGeom.CreateFaceVertexCountsAttr([4, 4, 4, 4])
    # 
    #   Example: 4 faces with varying number of vertices
    #   meshGeom.CreateFaceVertexCountsAttr([3, 4, 5, 6])

    meshGeom.CreateFaceVertexCountsAttr(mesh_data.nface_verts)

    # Set face vertex indices.
    #   Example: one face with 4 vertices defined by 4 indices.
    #   meshGeom.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    meshGeom.CreateFaceVertexIndicesAttr(mesh_data.vert_indices)

    # Set vertex normals. Normals are represented as a list of tuples each of
    # which is a vector indicating the direction a point is facing. This is later
    # Used to calculate face normals
    #   Example: Normals for 3 vertices
    # meshGeom.CreateNormalsAttr([(0, 1, 0), (0, 1, 0), (0, 1, 0), (0, 1,
    # 0)])

    # meshGeom.CreateNormalsAttr(mesh.getNormals())
    # meshGeom.SetNormalsInterpolation("vertex")

    # Set vertex uvs. UVs are represented as a list of tuples, each of which is a 2D
    # coordinate. UV's are used to map textures to the surface of 3D geometry
    #   Example: texture coordinates for 3 vertices
    #   texCoords.Set([(0, 1), (0, 0), (1, 0)])

    # texCoords = meshGeom.CreatePrimvar(
    #     "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying
    # )
    # texCoords.Set(mesh_data.uvs)

    # # Subdivision is set to catmullClark for smooth surfaces
    meshGeom.CreateSubdivisionSchemeAttr().Set("catmullClark")

    return meshGeom.GetPrim()

def load_obj(filename, nPerFace=None):

    with open(filename, 'r') as infile:
        lines = infile.readlines()

    # Remove comments
    newdata = [x.rstrip('\n').split() for x in lines if '#' not in x]

    vertices = []
    uvs = []
    mesh_data = []
    group = ""
    faces = []
    vert_indices = []
    uv_indices = []
    normal_indices = []
    nface_verts = []

    for i, ln in enumerate(newdata):
        if ln[0] == 'v':
            vertices.append(tuple(ln[1:]))
        elif ln[0] == 'vt':
            uvs.append(ln[1:])
        elif ln[0] == 'f':
            if nPerFace:
                if nPerFace > len(ln[1:]):
                    raise ValueError(f'Face has less than {nPerFace} vertices')
                faces.append(ln[1:nPerFace+1])  # Only consider the first nPerFace vertices
                nface_verts.append(nPerFace)
            else:
                faces.append(ln[1:]) # Consider all vertices
                nface_verts.append(len(ln[1:]))
        elif ln[0] == 'g':
            # Record the accumulated data and start a new group
                # Flat lists of face vertex indices
            if group:
                for face in faces:
                    for i in range(len(face)):
                        vert_indices.append(int(face[i].split('/')[0]) - 1)
                        uv_indices.append(int(face[i].split('/')[1]) - 1)

                mesh_data.append(MeshData(group, None, None, None, faces, vert_indices, uv_indices, normal_indices, nface_verts))
            faces = []
            vert_indices = []
            uv_indices = []
            normal_indices = []
            nface_verts = []
            group = Tf.MakeValidIdentifier(ln[1])
            print(f"Group {group}")

    # convert to Gf.Vec3f
    vertices = [Gf.Vec3f(*map(float, v)) for v in vertices]
    uvs = [Gf.Vec2f(*map(float, uv)) for uv in uvs]

    # Add all vertices and UVs to each mesh
    for mesh in mesh_data:
        mesh.vertices = vertices
        mesh.uvs = uvs

    return mesh_data

def load_skel_json(json_path_base: str, stage: Usd.Stage = None, usd_path: Sdf.Path = None) -> None:
    """Load a skeleton from JSON files

    Parameters
    ----------
    json_path_base : str
        Basename of the skeleton json file. The rig will be "{/path/to/}rig.{json_path_base}.json" and the weights will be
        "{/path/to/}weights.{json_path_base}.json"
    """

    dirname = os.path.dirname(json_path_base)
    basename = os.path.basename(json_path_base)
    rig_json = os.path.join(dirname, f"rig.{basename}.json")
    weights_json = os.path.join(dirname, f"weights.{basename}.json")

    with open(rig_json, 'r') as f:
        skel_data = json.load(f)
    with open(weights_json, 'r') as f:
        weights_data = json.load(f)
        weights_data = weights_data["weights"]

    return build_tree("", skel_data, weights_data)

def build_tree(node_name, skel_data, weight_data):
    """Recursively build the tree structure and integrate vertex weights."""
    children = {name: item for name, item in skel_data.items() if item["parent"] == node_name}
    subtree = {}
    for child_name in children:
        subtree[child_name] = children[child_name]
        subtree[child_name]["children"] = build_tree(child_name, skel_data, weight_data)
        subtree[child_name]["vertex_weights"] = weight_data.get(child_name, [])  # Get vertex weights if available, else an empty list
    return subtree
# def load_obj(filename)
#     # Read the file
#     with open(filename, 'r') as f: data = f.readlines()

#     # Remove comments
#     newdata = [x.rstrip('\n').split() for x in data if '#' not in x]
#     verts = np.asarray([x[1:] for x in newdata if x[0]=='v'], float)
#     idx = np.arange(len(verts))
#     uv = np.asarray([x[1:] for x in newdata if x[0]=='vt'], float)
#     face = np.asarray([x[1:] for x in newdata if x[0]=='f']) # This should fail if it creates a ragged array
#     face = np.apply_along_axis(lambda x: [y.split('/') for y in x], 0, face)
#     # Get the face number without vertex coordinate
#     face = np.asarray(face[:,0,:], int)

#     obj_types = [x[0] for x in newdata]
#     nptype = np.asarray(obj_types)

#     print(nptype)

#     idx = np.where(nptype == 'g', 1, 0)
#     idx = np.asarray(idx, dtype=int)
#     idx = np.nonzero(idx)

#     print(idx)

#     1/0

#     group_data = []
#     active_group = False

#     # Go through the file and find the group ranges
#     for i, ln in enumerate(newdata):
#         if ln[0] =='g':
#             # record the body name and index
#             if not active_group:
#                 group_data.append([ln[1], i])
#                 active_group = True
#             # Set the end index
#             elif active_group: 
#                 group_data[-1].extend([i])
#                 active_group = False
#     print(group_data)

if __name__ == "__main__":
    make_human()
