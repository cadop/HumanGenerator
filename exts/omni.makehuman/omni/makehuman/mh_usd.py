from numpy.random.tests import data
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Sdf, Gf, Tf, UsdSkel, Vt
import omni.usd
import carb
import numpy as np
import io, os
import re
import skeleton as mhskeleton


def add_to_scene(objects):

    scale = 10
    human = objects[0]

    mhskel = human.getSkeleton()

    mh_meshes = [o.mesh for o in objects]

    if not isinstance(mh_meshes, list):
        mh_meshes = [mh_meshes]

    # Filter out vertices we aren't meant to see and scale up the meshes
    mh_meshes = [m.clone(scale, filterMaskedVerts=True) for m in mh_meshes]

    # Scale our skeleton to match our human
    if mhskel:
        mhskel = mhskel.scaled(scale)

    # Apply weights to the meshes (internal makehuman objects)
    # Do we need to do this if we're applying deformation through imported skeletons?
    # Can we sync it back to the human model
    # Generate bone weights for all meshes up front so they can be reused for all
    if mhskel:
        rawWeights = human.getVertexWeights(human.getSkeleton())  # Basemesh weights
        for mesh in mh_meshes:
            if mesh.object.proxy:
                # Transfer weights to proxy
                parentWeights = mesh.object.proxy.getVertexWeights(rawWeights, human.getSkeleton())
            else:
                parentWeights = rawWeights
            # Transfer weights to face/vert masked and/or subdivided mesh
            weights = mesh.getVertexWeights(parentWeights)

            # Attach these vertexWeights to the mesh to pass them around the
            # exporter easier, the cloned mesh is discarded afterwards, anyway
            mesh.vertexWeights = weights
    else:
        # Attach trivial weights to the meshes
        for mesh in mh_meshes:
            mesh.vertexWeights = None

    # Bones are returned breadth-first (parents-first). This is convenient, as USD
    # requires it
    # bones = skel.getBones()

    # Get stage from open file
    stage = omni.usd.get_context().get_stage()

    # Get stage root path.
    rootPath = "/"

    # Get default prim.
    defaultPrim = stage.GetDefaultPrim()
    if defaultPrim.IsValid():
        # Set the rootpath under the stage's default prim
        rootPath = defaultPrim.GetPath().pathString

    # Create the USD skeleton in our stage using the mhskel data
    skel_data, usdSkel, skel_root_path = setup_skeleton(rootPath, stage, mhskel)

    # Add the meshes to the USD stage under skelRoot
    usd_mesh_paths = setup_meshes(mh_meshes, stage, skel_root_path)

    # Create bindings between meshes and the skeleton. Returns a list of bindings
    # the length of the number of meshes
    bindings = setup_bindings(usd_mesh_paths, stage, usdSkel)

    # Setup weights for corresponding mh_meshes (which hold the data) and bindings
    # (which link USD_meshes to the skeleton)
    setup_weights(mh_meshes, bindings, skel_data)


def setup_weights(mh_meshes, bindings, skel_data):
    # Iterate through corresponding meshes and bindings
    for mh_mesh, binding in zip(mh_meshes, bindings):

        indices, weights = calculate_influences(mh_mesh, skel_data)

        indices = list(map(int, indices))
        weights = list(map(float, weights))

        indices = Vt.IntArray(indices)
        weights = Vt.FloatArray(weights)

        elementSize = int(mh_mesh.vertexWeights._nWeights)
        weight_data = list(mh_mesh.vertexWeights.data)

        UsdSkel.NormalizeWeights(weights, len(weight_data))
        UsdSkel.SortInfluences(indices, weights, elementSize)

        indices_attribute = binding.CreateJointIndicesPrimvar(constant=False, elementSize=elementSize)
        indices_attribute.Set(indices)

        weights_attribute = binding.CreateJointWeightsPrimvar(constant=False, elementSize=elementSize)
        weights_attribute.Set(weights)

        # indices_attribute = binding.CreateJointIndicesPrimvar(
        #     constant=False, elementSize=maximum_influences
        # )
        # indices_attribute.Set(indices)

        # weights_attribute = binding.CreateJointWeightsPrimvar(
        #     constant=False, elementSize=maximum_influences
        # )
        # weights_attribute.Set(weights)


def calculate_influences(mh_mesh, skel_data):

    # Vertex indices
    vertices = [i for i in range(len(mh_mesh.getCoords()))]

    max_influences = mh_mesh.vertexWeights._nWeights

    # Named joints corresponding to vertices and weights
    # ie. {"joint",([indices],[weights])}
    all_influence_joints = mh_mesh.vertexWeights.data

    # joints in USD order
    binding_joints = skel_data["joint_names"]

    indices = []
    weights = []

    for vertex in vertices:
        # Keep track of how many influences act on the vertex
        influences = 0
        # Find out which joints have weights on this vertex
        for joint, weight_data in all_influence_joints.items():

            # if the vertex is weighted by the joint:
            if vertex in weight_data[0]:
                # Add the index of the joint from the USD-ordered list
                indices.append(binding_joints.index(joint))
                # Add the weight corresponding to the data index where the
                # vertex index can be found
                vert_index_index = list(weight_data[0]).index(vertex)
                weights.append(weight_data[1][vert_index_index])
                influences += 1
        # Pad any extra indices and weights with 0's, see:
        # https://graphics.pixar.com/usd/dev/api/_usd_skel__schemas.html#UsdSkel_BindingAPI
        # "If a point has fewer influences than are needed for other points, the
        # unused array elements of that point should be filled with 0, both for joint
        # indices and for weights."
        if influences < max_influences:
            leftover = max_influences - influences
            indices += [0] * leftover
            weights += [0] * leftover

    return indices, weights


def setup_bindings(paths, stage, skeleton):
    bindings = []

    for mesh in paths:
        # `usd_path` is referenced under the UsdSkelRoot so we need to add
        # its name to the path
        #
        prim = stage.GetPrimAtPath(mesh)
        binding = UsdSkel.BindingAPI.Apply(prim)
        # matrix = Gf.Matrix4d()
        # matrix.SetIdentity()
        binding.CreateSkeletonRel().SetTargets([skeleton.GetPath()])
        # binding.CreateGeomBindTransformAttr().Set(matrix)
        bindings.append(binding)
    return bindings


def setup_meshes(meshes, stage, rootPath):

    usd_mesh_paths = []
    for mesh in meshes:
        nPerFace = mesh.vertsPerFaceForExport
        newvertindices = []
        newuvindices = []

        coords = mesh.getCoords()
        for fn, fv in enumerate(mesh.fvert):
            if not mesh.face_mask[fn]:
                continue
            # only include <nPerFace> verts for each face, and order them consecutively
            newvertindices += [(fv[n]) for n in range(nPerFace)]
            fuv = mesh.fuvs[fn]
            # build an array of (u,v)s for each face
            newuvindices += [(fuv[n]) for n in range(nPerFace)]

        newvertindices = np.array(newvertindices)

        # Create mesh.
        name = sanitize(mesh.name)
        usd_mesh_path = rootPath + "/" + name
        usd_mesh_paths.append(usd_mesh_path)
        meshGeom = UsdGeom.Mesh.Define(stage, usd_mesh_path)

        # Set vertices.
        meshGeom.CreatePointsAttr(coords)
        # meshGeom.CreatePointsAttr([(-10, 0, -10), (-10, 0, 10), (10, 0, 10), (10, 0, -10)])

        # Set normals.
        meshGeom.CreateNormalsAttr(mesh.getNormals())
        # meshGeom.CreateNormalsAttr([(0, 1, 0), (0, 1, 0), (0, 1, 0), (0, 1, 0)])
        meshGeom.SetNormalsInterpolation("vertex")

        # Set face vertex count.
        nface = [mesh.vertsPerFaceForExport] * len(mesh.nfaces)
        meshGeom.CreateFaceVertexCountsAttr(nface)
        # meshGeom.CreateFaceVertexCountsAttr([4])

        # Set face vertex indices.
        meshGeom.CreateFaceVertexIndicesAttr(newvertindices)
        # # meshGeom.CreateFaceVertexIndicesAttr([0, 1, 2, 3])

        # # Set uvs.
        texCoords = meshGeom.CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying)
        texCoords.Set(mesh.getUVs(newuvindices))
        # texCoords.Set([(0, 1), (0, 0), (1, 0), (1, 1)])

        # # Subdivision is set to none.
        meshGeom.CreateSubdivisionSchemeAttr().Set("none")

    return [Sdf.Path(mesh_path) for mesh_path in usd_mesh_paths]


def setup_skeleton(rootPath, stage, skeleton):
    def add_joints_to_skel(joints, skeleton):
        attribute = skeleton.GetJointsAttr()
        attribute.Set(joints)

    def get_joint_data(path=None, node=None, skel_data=None, skeleton: mhskeleton.Skeleton = None):
        """Recursively traverses skeleton (breadth-first) and encapsulates joint data in a convenient object for later reference.

        Parameters
        ----------
        path : _type_, optional
            _description_, by default None
        node : _type_, optional
            _description_, by default None
        skel_data : _type_, optional
            _description_, by default None
        skeleton : skeleton.Skeleton, optional
            _description_, by default None

        Returns
        -------
        dict
            skel_data = {
                "joint_paths": [],
                "joint_names": [],
                "rel_transforms": [],
                "global_transforms": [],
                "bind_transforms": [],
            }
        """

        if skeleton:
            skel_data = {
                "joint_paths": [],
                "joint_names": [],
                "rel_transforms": [],
                "global_transforms": [],
                "bind_transforms": [],
            }
            get_joint_data("", skeleton.roots[0], skel_data)
            return skel_data
        else:
            s = skel_data

            # sanitize the name for USD paths
            name = sanitize(node.name)
            path += name
            s["joint_paths"].append(path)

            # store original name for later joint weighting
            s["joint_names"].append(node.name)

            relxform = node.matRestRelative
            relxform = relxform.transpose()
            relative_transform = Gf.Matrix4d(relxform.tolist())
            s["rel_transforms"].append(relative_transform)

            gxform = node.matRestGlobal
            gxform = gxform.transpose()
            global_transform = Gf.Matrix4d(gxform.tolist())
            s["global_transforms"].append(global_transform)

            bxform = node.getBindMatrix()
            # getBindMatrix returns bindmat and bindinv - we want the uninverted matrix,
            # however USD uses row first while mh uses column first, so we use the
            # transpose/inverse
            bxform = bxform[1]
            bind_transform = Gf.Matrix4d(bxform.tolist())
            # bind_transform = Gf.Matrix4d().SetIdentity()
            s["bind_transforms"].append(bind_transform)

            for child in node.children:
                get_joint_data(path + "/", child, skel_data)

    skel_data = get_joint_data(skeleton=skeleton)
    # root_node = skel_data["joint_paths"][0]
    skel_root_path = rootPath + "/human"
    skeleton_path = skel_root_path + "/Skeleton"

    skelRoot = UsdSkel.Root.Define(stage, skel_root_path)
    usdSkel = UsdSkel.Skeleton.Define(stage, skeleton_path)

    # add joints to skeleton by path
    add_joints_to_skel(skel_data["joint_paths"], usdSkel)

    # Add bind transforms to skeleton
    usdSkel.CreateBindTransformsAttr(skel_data["bind_transforms"])

    # setup rest transforms in joint-local space
    usdSkel.CreateRestTransformsAttr(skel_data["rel_transforms"])

    return skel_data, usdSkel, skel_root_path


def sanitize(s: str):
    illegal = (".", "-")
    for c in illegal:
        s = s.replace(c, "_")
    return s

    # usd_skel = None
    # Import skeleton to USD


#     if skel:
#         skel_root_path = rootPath + "/human"
#         skel_prim_path = skel_root_path + "/skeleton"

#         # Put meshes in our skeleton root, if we have one
#         rootPath = skel_root_path

#         skelRoot = UsdSkel.Root.Define(stage, skel_root_path)
#         usd_skel = UsdSkel.Skeleton.Define(stage, skel_prim_path)


#         add_joints("", skel.roots[0], skel_data)
#         # add_joints(stage, skel_prim_path + "/", skel.roots[0], skel_data)

#         usd_skel.CreateJointsAttr(skel_data["joint_paths"])
#         usd_skel.CreateJointNamesAttr([key for key in skel_data["joint_to_path"]])
#         usd_skel.CreateBindTransformsAttr(skel_data["bind_transforms"])
#         usd_skel.CreateRestTransformsAttr(skel_data["rest_transforms"])


#     # root = skelRoot.GetPrim()
#     bindings = _create_mesh_bindings(sdf_mesh_paths, stage, usd_skel.GetPrim(), skel_data)

#     mesh = meshes[0]
#     binding = bindings[0]

#     maximum_influences = 3
#     indices = [i for i in range(maximum_influences)]
#     weights = [1.0 / maximum_influences] * maximum_influences
#     # weights = [1] * len(indices)

#     indices = Vt.IntArray(indices)
#     weights = Vt.FloatArray(weights)

#     # Reference: https://graphics.pixar.com/usd/docs/api/_usd_skel__schemas.html#UsdSkel_BindingAPI_StoringInfluences
#     # Keep weights sorted and normalized for best performance
#     #
#     # UsdSkel.NormalizeWeights(weights, 1)
#     # UsdSkel.SortInfluences(indices, weights, maximum_influences)

#     indices_attribute = binding.CreateJointIndicesPrimvar(constant=False, elementSize=maximum_influences)
#     indices_attribute.Set(indices)

#     weights_attribute = binding.CreateJointWeightsPrimvar(constant=False, elementSize=maximum_influences)
#     weights_attribute.Set(weights)
#     print()


# # Modified from:
# # https://github.com/ColinKennedy/USD-Cookbook/tree/master/tools/export_usdskel_from_scratch
# # def _setup_meshes(meshes, skeleton):
# #     """Export `meshes` and then bind their USD Prims to a skeleton.

# #     Args:
# #         meshes (iter[str]):
# #             The paths to each Maya mesh that must be written to-disk.
# #             e.g. ["|some|pSphere1|pSphereShape1"].
# #         skeleton (`pxr.UsdSkel.Skeleton`):
# #             The USD Skeleton that the exported meshes will be paired with.

# #     Raises:
# #         RuntimeError: If `skeleton` has no ancestor UsdSkelRoot Prim.

# #     Returns:
# #         list[tuple[str, `pxr.UsdSkel.BindingAPI`]]:
# #             The Maya mesh which represents some USD mesh and the binding
# #             schema that is used to bind that mesh to the skeleton. We
# #             return these two values as pairs so that they don't have any
# #             chance of getting mixed up when other functions use them.

# #     """


#     return bindings
