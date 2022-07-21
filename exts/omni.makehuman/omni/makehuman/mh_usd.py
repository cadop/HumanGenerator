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
            "joint_to_path": {},
        }

        add_joints("", skel.roots[0], skel_data)
        # add_joints(stage, skel_prim_path + "/", skel.roots[0], skel_data)

        usd_skel.CreateJointsAttr(skel_data["joint_paths"])
        usd_skel.CreateJointNamesAttr([key for key in skel_data["joint_to_path"]])

        # joints_rel =

        # for joint in skel_data["joint_paths"]:
        #     joints_rel.AppendTarget(joint)

        usd_skel.CreateRestTransformsAttr(skel_data["rest_transforms"])

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
        meshGeom = UsdGeom.Mesh.Define(stage, rootPath + "/" + name)

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


def add_joints(path, node, skel_data):

    s = skel_data
    name = sanitize(node.name)

    path += name
    s["joint_paths"].append(path)

    s["joint_to_path"][name] = path

    xform = node.matRestRelative
    rest_transform = Gf.Matrix4d(xform.tolist())

    s["rest_transforms"].append(rest_transform)

    for child in node.children:
        add_joints(path + "/", child, skel_data)


def sanitize(s: str):
    illegal = (".", "-")
    for c in illegal:
        s = s.replace(c, "_")
    return s
