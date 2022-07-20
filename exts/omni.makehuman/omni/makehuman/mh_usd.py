from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Sdf, Gf, Tf, UsdSkel
import omni.usd
import carb
import numpy as np
import io, os
import re


def add_to_scene(objects):

    scale = 100
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

    human_primpath = rootPath + "/human"

    # Import skeleton to USD
    if skel:
        skelPrim = UsdSkel.Skeleton.Define(stage, human_primpath)
        # add_joints(stage, human_primpath + "/", scene.rootnode)
        # usd_skel = UsdSkel.Skeleton(skelPrim)
        # joints_rel = usd_skel.GetJointsRel()
        # for joint in joint_paths:
        #     joints_rel.AppendTarget(joint)

        # usd_skel.CreateRestTransformsAttr(rest_transforms)

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

        # # # Set position.
        UsdGeom.XformCommonAPI(meshGeom).SetTranslate((0.0, 0.0, 0.0))

        # # # Set rotation.
        UsdGeom.XformCommonAPI(meshGeom).SetRotate((0.0, 0.0, 0.0), UsdGeom.XformCommonAPI.RotationOrderXYZ)

        # # # Set scale.
        UsdGeom.XformCommonAPI(meshGeom).SetScale((1.0, 1.0, 1.0))


def sanitize(s: str):
    illegal = (".", "-")
    for c in illegal:
        s = s.replace(c, "_")
    return s
