from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Sdf, Gf, Tf
import omni.usd
import carb
import numpy as np
import io, os


def add_to_scene(meshes):
    if not isinstance(meshes, list):
        meshes = [meshes]

    # Filter out vertices we aren't meant to see
    meshes = [m.clone(filterMaskedVerts=True) for m in meshes]

    mesh = meshes[0]
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

    # Get stage.
    stage = omni.usd.get_context().get_stage()

    # Get default prim.
    defaultPrim = stage.GetDefaultPrim()

    # Get root path.
    rootPath = "/"
    if defaultPrim.IsValid():
        rootPath = defaultPrim.GetPath().pathString
    carb.log_info(rootPath)

    # Create mesh.
    meshGeom = UsdGeom.Mesh.Define(stage, rootPath + "/mesh")

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
    # UsdGeom.XformCommonAPI(meshGeom).SetTranslate((0.0, 0.0, 0.0))

    # # # Set rotation.
    # UsdGeom.XformCommonAPI(meshGeom).SetRotate((0.0, 0.0, 0.0), UsdGeom.XformCommonAPI.RotationOrderXYZ)

    # # # Set scale.
    # UsdGeom.XformCommonAPI(meshGeom).SetScale((1.0, 1.0, 1.0))
