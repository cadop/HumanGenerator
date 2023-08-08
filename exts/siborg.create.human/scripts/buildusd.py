# Build the human USD file outside of Omniverse

import os
from pxr import Usd, Sdf, UsdSkel, Tf, UsdGeom, Gf
import numpy as np
import warnings
from dataclasses import dataclass

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
    targets_dir = os.path.join(ext_path, "data", "targets","armslegs")
    for dirpath, _, filenames in os.walk(targets_dir):
        for filename in filenames:
            # Skip non-target files
            if not filename.endswith(".target"):
                continue
            print(f"Importing {filename}")
            if targets := mhtarget_to_blendshapes(stage, prim, os.path.join(dirpath, filename)):
                target_names.extend(targets)


    # Define an Animation (with blend shape weight time-samples).
    animation = UsdSkel.Animation.Define(stage, skeleton.GetPrim().GetPath().AppendChild("animation"))
    animation.CreateBlendShapesAttr().Set(target_names)
    weightsAttr = animation.CreateBlendShapeWeightsAttr(np.zeros(len(target_names)))
    weightsAttr.Set(np.zeros(len(target_names)), 0)

    # Bind Skeleton to animation.
    skeletonBinding = UsdSkel.BindingAPI.Apply(skeleton.GetPrim())
    anim_path=animation.GetPrim().GetPath()
    skeletonBinding.CreateAnimationSourceRel().AddTarget(anim_path)

    # Save the stage to a file
    stage.Export(os.path.join(ext_path,"data","human_base.usda"))


def mhtarget_to_blendshapes(stage, prim, path : str) -> [Sdf.Path]:
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

    # The original ranges for the indices of the mesh vertices
    # See http://www.makehumancommunity.org/wiki/Documentation:Basemesh
    index_ranges = {
        'body': (0, 13379),
        'helper_tongue': (13380, 13605),
        'joints': (13606, 14597),
        'helper_x_eye': (14598, 14741),
        'helper_x_eyelashes-y': (14742, 14991),
        'helper_lower_teeth': (14992, 15059),
        'helper_upper_teeth': (15060, 15127),
        'helper_genital': (15128, 15327),
        'helper_tights': (15328, 18001),
        'helper_skirt': (18002, 18721),
        'helper_hair': (18722, 19149),
        'ground': (19150, 19157)
    }

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
    num_blendshapes = 0
    index_start = 0
    for mesh in meshes:
        # The next index offset is the current offset plus the number of vertices in the current mesh
        verts = len(mesh.GetAttribute("points").Get())
        index_end = index_start + verts

        mesh_name = mesh.GetName()
        original_range = index_ranges.get((mesh_name), None)

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
            num_blendshapes += 1
        # Update the index offset
        index_start = index_end
    print(f"Counted {index_start} vertices")
    return [target_name] * num_blendshapes

@dataclass
class MeshData:
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
    vertices : np.ndarray
        An N x 3 array of vertex positions
    nPerFace : np.ndarray
        An array of length N where each element is the number of vertices in each face
    faces : np.ndarray
        An N x max(nPerFace) array of vertex indices
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

    texCoords = meshGeom.CreatePrimvar(
        "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying
    )
    texCoords.Set(mesh_data.uvs)

    # # Subdivision is set to catmullClark for smooth surfaces
    meshGeom.CreateSubdivisionSchemeAttr().Set("catmullClark")

    return meshGeom.GetPrim()

# def load_obj(filename, nPerFace=None):

#     with open(filename, 'r') as infile:
#         lines = infile.readlines()

#     vertices = []
#     uvs = []
#     normals = []
#     faces = []
#     nface_verts = []

#     for line in lines:
#         parts = line.strip().split()
#         if parts[0] == 'v':
#             vertices.append(tuple(parts[1:]))
#         elif parts[0] == 'vt':
#             uvs.append(parts[1:])
#         elif parts[0] == 'vn':
#             normals.append(parts[1:])
#         elif parts[0] == 'f':
#             if nPerFace:
#                 if nPerFace > len(parts[1:]):
#                     raise ValueError(f'Face has less than {nPerFace} vertices')
#                 faces.append(parts[1:nPerFace+1])  # Only consider the first nPerFace vertices
#                 nface_verts.append(nPerFace)
#             else:
#                 faces.append(parts[1:]) # Consider all vertices
#                 nface_verts.append(len(parts[1:]))

#     # Flat lists of face vertex indices
#     vert_indices = []
#     uv_indices = []
#     normal_indices = []

#     for face in faces:
#         for i in range(len(face)):
#             vert_indices.append(int(face[i].split('/')[0]) - 1)
#             if uvs:
#                 uv_indices.append(int(face[i].split('/')[1]) - 1)
#             if normals:
#                 normal_indices.append(int(face[i].split('/')[2]) - 1)

#     # convert to Gf.Vec3f
#     vertices = [Gf.Vec3f(*map(float, v)) for v in vertices]
#     uvs = [Gf.Vec2f(*map(float, uv)) for uv in uvs]

#     return MeshData(vertices, uvs, normals, faces, vert_indices, uv_indices, normal_indices, nface_verts)


def load_obj(filename)
    # Read the file
    with open(filename, 'r') as f: data = f.readlines()

    # Remove comments
    newdata = [x.rstrip('\n').split() for x in data if '#' not in x]
    verts = np.asarray([x[1:] for x in newdata if x[0]=='v'], float)
    idx = np.arange(len(verts))
    uv = np.asarray([x[1:] for x in newdata if x[0]=='vt'], float)
    face = np.asarray([x[1:] for x in newdata if x[0]=='f']) # This should fail if it creates a ragged array
    face = np.apply_along_axis(lambda x: [y.split('/') for y in x], 0, face)
    # Get the face number without vertex coordinate
    face = np.asarray(face[:,0,:], int)

    obj_types = [x[0] for x in newdata]
    nptype = np.asarray(obj_types)

    print(nptype)

    idx = np.where(nptype == 'g', 1, 0)
    idx = np.asarray(idx, dtype=int)
    idx = np.nonzero(idx)

    print(idx)

    1/0

    group_data = []
    active_group = False

    # Go through the file and find the group ranges
    for i, ln in enumerate(newdata):
        if ln[0] =='g':
            # record the body name and index
            if not active_group:
                group_data.append([ln[1], i])
                active_group = True
            # Set the end index
            elif active_group: 
                group_data[-1].extend([i])
                active_group = False
    print(group_data)

if __name__ == "__main__":
    make_human()