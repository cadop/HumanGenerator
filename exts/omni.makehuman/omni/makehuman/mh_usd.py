from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Sdf, Gf, Tf
import omni.usd
import carb
import numpy as np
import io, os


def add_to_scene(meshes):
    if not isinstance(meshes, list):
        meshes = [meshes]

    # Filter out polygons we aren't meant to see
    meshes = [m.clone(filterMaskedVerts=True) for m in meshes]

    mesh = meshes[0]
    nPerFace = mesh.vertsPerFaceForExport

    # only include a set number of vertices per face
    regularfvert = []
    for fv in mesh.fvert:
        regularfvert += [(fv[n]) for n in range(nPerFace)]

    regularfvert = np.array(regularfvert)
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
    meshGeom.CreatePointsAttr(mesh.getCoords())
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
    meshGeom.CreateFaceVertexIndicesAttr(regularfvert)
    # # meshGeom.CreateFaceVertexIndicesAttr([0, 1, 2, 3])

    # # Set uvs.
    texCoords = meshGeom.CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex)
    texCoords.Set(mesh.getUVs())

    # # Subdivision is set to none.
    meshGeom.CreateSubdivisionSchemeAttr().Set("none")

    # # Set position.
    UsdGeom.XformCommonAPI(meshGeom).SetTranslate((0.0, 0.0, 0.0))

    # # Set rotation.
    UsdGeom.XformCommonAPI(meshGeom).SetRotate((0.0, 0.0, 0.0), UsdGeom.XformCommonAPI.RotationOrderXYZ)

    # # Set scale.
    UsdGeom.XformCommonAPI(meshGeom).SetScale((1.0, 1.0, 1.0))


def writeObjFile(path, meshes, writeMTL=True, config=None, filterMaskedFaces=True):
    if not isinstance(meshes, list):
        meshes = [meshes]

    if isinstance(path, io.IOBase):
        fp = path
    else:
        fp = open(path, "w", encoding="utf-8")

    fp.write("# MakeHuman exported OBJ\n" + "# www.makehumancommunity.org\n\n")

    if writeMTL:
        mtlfile = path.replace(".obj", ".mtl")
        fp.write("mtllib %s\n" % os.path.basename(mtlfile))

    scale = config.scale if config is not None else 1.0

    # Scale and filter out masked faces and unused verts
    if filterMaskedFaces:
        meshes = [m.clone(scale=scale, filterMaskedVerts=True) for m in meshes]
    else:
        # Unfiltered
        meshes = [m.clone(scale=scale, filterMaskedVerts=False) for m in meshes]

    if config and config.feetOnGround:
        offset = config.offset
    else:
        offset = [0, 0, 0]

    # Vertices
    for mesh in meshes:
        fp.write("".join(["v %.4f %.4f %.4f\n" % tuple(co + offset) for co in mesh.coord]))

    # Vertex normals
    if config is None or config.useNormals:
        for mesh in meshes:
            fp.write("".join(["vn %.4f %.4f %.4f\n" % tuple(no) for no in mesh.vnorm]))

    # UV vertices
    for mesh in meshes:
        if mesh.has_uv:
            fp.write("".join(["vt %.6f %.6f\n" % tuple(uv) for uv in mesh.texco]))

    # Faces
    nVerts = 1
    nTexVerts = 1
    for mesh in meshes:
        nPerFace = mesh.vertsPerFaceForExport
        print("Export " + str(nPerFace) + "-faced mesh")
        fp.write("usemtl %s\n" % mesh.material.name)
        fp.write("g %s\n" % mesh.name)

        if config is None or config.useNormals:
            if mesh.has_uv:
                for fn, fv in enumerate(mesh.fvert):
                    if not mesh.face_mask[fn]:
                        continue
                    fuv = mesh.fuvs[fn]
                    line = [" %d/%d/%d" % (fv[n] + nVerts, fuv[n] + nTexVerts, fv[n] + nVerts) for n in range(nPerFace)]
                    fp.write("f" + "".join(line) + "\n")
            else:
                for fn, fv in enumerate(mesh.fvert):
                    if not mesh.face_mask[fn]:
                        continue
                    line = [" %d//%d" % (fv[n] + nVerts, fv[n] + nVerts) for n in range(nPerFace)]
                    fp.write("f" + "".join(line) + "\n")
        else:
            if mesh.has_uv:
                for fn, fv in enumerate(mesh.fvert):
                    if not mesh.face_mask[fn]:
                        continue
                    fuv = mesh.fuvs[fn]
                    line = [" %d/%d" % (fv[n] + nVerts, fuv[n] + nTexVerts) for n in range(nPerFace)]
                    fp.write("f" + "".join(line) + "\n")
            else:
                for fn, fv in enumerate(mesh.fvert):
                    if not mesh.face_mask[fn]:
                        continue
                    line = [" %d" % (fv[n] + nVerts) for n in range(nPerFace)]
                    fp.write("f" + "".join(line) + "\n")

        nVerts += len(mesh.coord)
        nTexVerts += len(mesh.texco)

    fp.close()

    if writeMTL:
        with open(mtlfile, "w", encoding="utf-8") as fp:
            fp.write("# MakeHuman exported MTL\n" + "# www.makehumancommunity.org\n\n")
            for mesh in meshes:
                writeMaterial(fp, mesh.material, config)


#
#   writeMaterial(fp, mat, config):
#


def writeMaterial(fp, mat, texPathConf=None):
    fp.write("\nnewmtl %s\n" % mat.name)
    diff = mat.diffuseColor
    spec = mat.specularColor
    # alpha=0 is necessary for correct transparency in Blender.
    # But may lead to problems with other apps.
    if mat.diffuseTexture:
        alpha = 0
    else:
        alpha = mat.opacity
    fp.write(
        "Kd %.4g %.4g %.4g\n" % (diff.r, diff.g, diff.b)
        + "Ks %.4g %.4g %.4g\n" % (spec.r, spec.g, spec.b)
        + "d %.4g\n" % alpha
    )

    writeTexture(fp, "map_Kd", mat.diffuseTexture, texPathConf)
    writeTexture(fp, "map_D", mat.diffuseTexture, texPathConf)
    writeTexture(fp, "map_Ks", mat.specularMapTexture, texPathConf)
    # writeTexture(fp, "map_Tr", mat.translucencyMapTexture, texPathConf)
    # Disabled because Blender interprets map_Disp as map_D
    if mat.normalMapTexture:
        texPathConf.copyTextureToNewLocation(mat.normalMapTexture)
    # writeTexture(fp, "map_Disp", mat.specularMapTexture, texPathConf)
    # writeTexture(fp, "map_Disp", mat.displacementMapTexture, texPathConf)

    # writeTexture(fp, "map_Kd", os.path.join(getpath.getSysDataPath("textures"), "texture.png"), texPathConf)


def writeTexture(fp, key, filepath, pathConfig=None):
    if not filepath:
        return

    if pathConfig:
        newpath = pathConfig.copyTextureToNewLocation(filepath)  # TODO use shared code for exporting texture files
        fp.write("%s %s\n" % (key, newpath))
    else:
        fp.write("%s %s\n" % (key, filepath))
