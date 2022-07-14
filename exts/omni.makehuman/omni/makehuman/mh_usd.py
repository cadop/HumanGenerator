from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Sdf, Gf, Tf
import omni.usd
import carb
import numpy as np


def add_to_scene(object3d):
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
    meshGeom.CreatePointsAttr(object3d.getCoords())
    # meshGeom.CreatePointsAttr([(-10, 0, -10), (-10, 0, 10), (10, 0, 10), (10, 0, -10)])

    # Set normals.
    # meshGeom.CreateNormalsAttr(object3d.getNormals())
    # meshGeom.CreateNormalsAttr([(0, 1, 0), (0, 1, 0), (0, 1, 0), (0, 1, 0)])
    # meshGeom.SetNormalsInterpolation("vertex")

    # Set face vertex count.
    meshGeom.CreateFaceVertexCountsAttr(object3d.nfaces)
    # meshGeom.CreateFaceVertexCountsAttr([4])

    # Set face vertex indices.
    # indices = list([i + 1 for i in object3d.index])
    meshGeom.CreateFaceVertexIndicesAttr(object3d.fvert)
    # # meshGeom.CreateFaceVertexIndicesAttr([0, 1, 2, 3])

    # # Set uvs.
    # texCoords = meshGeom.CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex)
    # texCoords.Set([(0, 1), (0, 0), (1, 0), (1, 1)])

    # # Subdivision is set to none.
    # meshGeom.CreateSubdivisionSchemeAttr().Set("none")

    # # Set position.
    # UsdGeom.XformCommonAPI(meshGeom).SetTranslate((0.0, 0.0, 0.0))

    # # Set rotation.
    # UsdGeom.XformCommonAPI(meshGeom).SetRotate((0.0, 0.0, 0.0), UsdGeom.XformCommonAPI.RotationOrderXYZ)

    # # Set scale.
    # UsdGeom.XformCommonAPI(meshGeom).SetScale((1.0, 1.0, 1.0))
