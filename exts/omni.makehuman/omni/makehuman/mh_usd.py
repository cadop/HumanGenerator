from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Sdf, Gf, Tf, UsdSkel
import omni.usd
import carb
import numpy as np
import io, os
import re


def add_to_scene(objects):

    scale = 10
    human = objects[0]

    skel = human.getSkeleton()

    meshes = [o.mesh for o in objects]

    if not isinstance(meshes, list):
        meshes = [meshes]

    # Filter out vertices we aren't meant to see and scale up the meshes
    meshes = [m.clone(scale, filterMaskedVerts=True) for m in meshes]

    # Scale our skeleton to match our human
    if skel:
        skel = skel.scaled(scale)

    # Apply weights to the meshes (internal makehuman objects)
    # Do we need to do this if we're applying deformation through imported skeletons?
    # Can we sync it back to the human model
    # Generate bone weights for all meshes up front so they can be reused for all
    if skel:
        rawWeights = human.getVertexWeights(human.getSkeleton())  # Basemesh weights
        for mesh in meshes:
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
        for mesh in meshes:
            mesh.vertexWeights = None

    # Get stage.
    stage = omni.usd.get_context().get_stage()

    # Get default prim.
    defaultPrim = stage.GetDefaultPrim()

    # Get root path.
    rootPath = "/"
    if defaultPrim.IsValid():
        rootPath = defaultPrim.GetPath().pathString
    carb.log_info(rootPath)

    # usd_skel = None
    # Import skeleton to USD
    if skel:
        skel_root_path = rootPath + "/human"
        skel_prim_path = skel_root_path + "/skeleton"

        # Put meshes in our skeleton root, if we have one
        rootPath = skel_root_path

        skelRoot = UsdSkel.Root.Define(stage, skel_root_path)
        usd_skel = UsdSkel.Skeleton.Define(stage, skel_prim_path)

        skel_data = {
            "joint_paths": [],
            "rest_transforms": [],
            "bind_transforms": [],
            "joint_to_path": {},
        }

        add_joints("", skel.roots[0], skel_data)
        # add_joints(stage, skel_prim_path + "/", skel.roots[0], skel_data)

        usd_skel.CreateJointsAttr(skel_data["joint_paths"])
        usd_skel.CreateJointNamesAttr([key for key in skel_data["joint_to_path"]])
        usd_skel.CreateBindTransformsAttr(skel_data["bind_transforms"])
        usd_skel.CreateRestTransformsAttr(skel_data["rest_transforms"])

    usd_mesh_paths = []

    # import meshes to USD
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

        # # # # Set position.
        # UsdGeom.XformCommonAPI(meshGeom).SetTranslate((0.0, 0.0, 0.0))

        # # # # Set rotation.
        # UsdGeom.XformCommonAPI(meshGeom).SetRotate((0.0, 0.0, 0.0), UsdGeom.XformCommonAPI.RotationOrderXYZ)

        # # # # Set scale.
        # UsdGeom.XformCommonAPI(meshGeom).SetScale((1.0, 1.0, 1.0))

    sdf_mesh_paths = [Sdf.Path(mesh_path) for mesh_path in usd_mesh_paths]

    # root = skelRoot.GetPrim()
    _create_mesh_bindings(sdf_mesh_paths, stage, usd_skel.GetPrim())


def add_joints(path, node, skel_data):

    s = skel_data
    name = sanitize(node.name)

    path += name
    s["joint_paths"].append(path)

    s["joint_to_path"][name] = path

    rxform = node.getRelativeMatrix()
    rxform = rxform.transpose()
    rest_transform = Gf.Matrix4d(rxform.tolist())
    s["rest_transforms"].append(rest_transform)

    bxform = node.getBindMatrix()
    bxform = bxform[0].transpose()
    bind_transform = Gf.Matrix4d(bxform.tolist())
    s["bind_transforms"].append(bind_transform)

    for child in node.children:
        add_joints(path + "/", child, skel_data)


def sanitize(s: str):
    illegal = (".", "-")
    for c in illegal:
        s = s.replace(c, "_")
    return s


# Modified from:
# https://github.com/ColinKennedy/USD-Cookbook/tree/master/tools/export_usdskel_from_scratch
# def _setup_meshes(meshes, skeleton):
#     """Export `meshes` and then bind their USD Prims to a skeleton.

#     Args:
#         meshes (iter[str]):
#             The paths to each Maya mesh that must be written to-disk.
#             e.g. ["|some|pSphere1|pSphereShape1"].
#         skeleton (`pxr.UsdSkel.Skeleton`):
#             The USD Skeleton that the exported meshes will be paired with.

#     Raises:
#         RuntimeError: If `skeleton` has no ancestor UsdSkelRoot Prim.

#     Returns:
#         list[tuple[str, `pxr.UsdSkel.BindingAPI`]]:
#             The Maya mesh which represents some USD mesh and the binding
#             schema that is used to bind that mesh to the skeleton. We
#             return these two values as pairs so that they don't have any
#             chance of getting mixed up when other functions use them.

#     """


def _get_default_prim_path(path):
    """`pxr.Sdf.Path`: Get the path of the defaultPrim of some USD file."""
    stage = Usd.Stage.Open(path)
    prim = stage.GetDefaultPrim()

    return prim.GetPath()


def _add_mesh_group_reference(stage, path, root):
    """Add the meshes in some USD `path` file onto the given `stage` starting at `root`.

    Important:
        `default_added_to_root` must exist on stage before this function is called.

    """
    # Example:
    #     default = Sdf.Path("/group1")
    #     root = Sdf.Path("/Something/SkeletonRoot")
    #     default_added_to_root = Sdf.Path("/Something/SkeletonRoot/group1")
    #
    default = _get_default_prim_path(path)
    default_added_to_root = root.GetPath().AppendChild(str(default.MakeRelativePath("/")))
    stage.GetPrimAtPath(default_added_to_root).GetReferences().AddReference(
        os.path.relpath(path, os.path.dirname(stage.GetRootLayer().identifier))
    )


def _create_mesh_bindings(paths, stage, skeleton):
    bindings = []

    comment = "The values in this attribute were sorted by elementSize."

    for usd_path in paths:
        # `usd_path` is referenced under the UsdSkelRoot so we need to add
        # its name to the path
        #
        prim = stage.GetPrimAtPath(usd_path)
        binding = UsdSkel.BindingAPI.Apply(prim)
        binding.CreateSkeletonRel().SetTargets([skeleton.GetPath()])
        bindings.append(binding)

    return bindings


def _get_expected_mesh_paths(meshes, new_root):
    """Make each mesh path relative to the given `new_root` UsdSkelRoot Prim path."""
    relative_paths = [Sdf.Path(helper.convert_maya_path_to_usd(mesh).lstrip("/")) for mesh in meshes]

    return [path_.MakeAbsolutePath(new_root) for path_ in relative_paths]


# Note: This is a hacky trick but works well. We include
# `exportSkin="auto"` to make USD export export joint influences
# with our meshes. It also will try to link skinning to the mesh but
# we will override those connections later.
#
# Basically, we use `cmds.usdExport` just for the joint influence
# information and blow away the rest of the data it outputs in
# other, stronger layers.
#
# Reference: https://graphics.pixar.com/usd/docs/Maya-USD-Plugins.html
#
# cmds.usdExport(meshes, file=path, exportSkin="auto")

# root = UsdSkel.Root.Find(skeleton)

# if not root:
#     raise RuntimeError('Skeleton "{skeleton}" has no UsdSkelRoot.'.format(skeleton=skeleton.GetPath()))

# root = root.GetPrim()
# stage = root.GetStage()
# bindings = _create_mesh_bindings(_get_expected_mesh_paths(meshes, root.GetPath()))
# # Note: We add the mesh into an explicit `over` Prim instead of
# # adding it directly onto `root` as a reference. This is so that we
# # can have better control over what kind of meshes are loaded. e.g.
# # In the future, we can switch this part to use a variant set to
# # load different mesh LODs, for example.
# #
# _add_mesh_group_reference(stage, path, root)

# return list(zip(meshes, bindings))
