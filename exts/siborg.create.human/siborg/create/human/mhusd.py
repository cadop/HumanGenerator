from pxr import Sdf, Usd, UsdGeom, UsdSkel, Tf
import carb
import omni
import omni.usd
import numpy as np
import os
import warnings
from dataclasses import dataclass
from pxr import Gf


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


def make_human():

    # Get the extension path
    manager = omni.kit.app.get_app().get_extension_manager()
    ext_id = manager.get_enabled_extension_id("siborg.create.human")
    ext_path = manager.get_extension_path(ext_id)

    # Get USD context and stage
    usd_context = omni.usd.get_context()
    stage = usd_context.get_stage()

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



    # import the mesh
    mesh_data = load_obj(os.path.join(ext_path, "data", "3dobjs", "base.obj"))

    # Create a mesh prim
    mesh = create_geom(stage, rootPath.AppendChild("mesh"), mesh_data)

    # Get the mesh itself
    mesh = get_first_child_mesh_df(mesh)
    
    target_names = []
    target_paths = []


    # Traverse the MakeHuman targets directory
    targets_dir = os.path.join(ext_path, "data", "targets")
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


def create_geom(stage, path:str, mesh_data: MeshData):
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


def load_obj(filename, nPerFace=None):

    with open(filename, 'r') as infile:
        lines = infile.readlines()

    vertices = []
    uvs = []
    normals = []
    faces = []
    nface_verts = []

    for line in lines:
        parts = line.strip().split()
        if parts[0] == 'v':
            vertices.append(tuple(parts[1:]))
        elif parts[0] == 'vt':
            uvs.append(parts[1:])
        elif parts[0] == 'vn':
            normals.append(parts[1:])
        elif parts[0] == 'f':
            if nPerFace:
                if nPerFace > len(parts[1:]):
                    raise ValueError(f'Face has less than {nPerFace} vertices')
                faces.append(parts[1:nPerFace+1])  # Only consider the first nPerFace vertices
                nface_verts.append(nPerFace)
            else:
                faces.append(parts[1:]) # Consider all vertices
                nface_verts.append(len(parts[1:]))

    # Flat lists of face vertex indices
    vert_indices = []
    uv_indices = []
    normal_indices = []

    for face in faces:
        for i in range(len(face)):
            vert_indices.append(int(face[i].split('/')[0]) - 1)
            if uvs:
                uv_indices.append(int(face[i].split('/')[1]) - 1)
            if normals:
                normal_indices.append(int(face[i].split('/')[2]) - 1)

    # convert to Gf.Vec3f
    vertices = [Gf.Vec3f(*map(float, v)) for v in vertices]
    uvs = [Gf.Vec2f(*map(float, uv)) for uv in uvs]

    return MeshData(vertices, uvs, normals, faces, vert_indices, uv_indices, normal_indices, nface_verts)