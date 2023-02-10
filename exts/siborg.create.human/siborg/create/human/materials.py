from typing import List
from module3d import Object3D
from pxr import Usd, UsdGeom, UsdShade, Sdf


def get_mesh_texture(mh_mesh: Object3D):
    """Gets mesh diffuse texture from a Makehuman mesh object

    Parameters
    ----------
    mh_mesh : Object3D
        A Makehuman mesh object. Contains path to bound material/textures

    Returns
    -------
    Tuple (str,str)
        Returns the path to a texture on disk, and a name for the texture
        Returns (None, None) if no texture exists
    """
    # TODO return additional maps (AO, roughness, normals, etc)
    material = mh_mesh.material
    texture = material.diffuseTexture
    name = material.name
    if texture:
        return texture, name
    else:
        return (None, None)


def create_material(diffuse_image_path: str, name: str, root_path: str, stage: Usd.Stage):
    """Create OmniPBR Material with specified diffuse texture

    Parameters
    ----------
    diffuse_image_path : str
        Path to diffuse texture on disk
    name : str
        Material name
    root_path : str
        Root path under which to place material scope
    stage : Usd.Stage
        USD stage into which to add the material

    Returns
    -------
    UsdShade.Material
        Material with diffuse texture applied
    """

    materialScopePath = root_path + "/Materials"

    # Check for a scope in which to keep materials. If it doesn't exist, make
    # one
    scopePrim = stage.GetPrimAtPath(materialScopePath)
    if scopePrim.IsValid() is False:
        UsdGeom.Scope.Define(stage, materialScopePath)

    # Create material (omniPBR).
    materialPath = materialScopePath + "/" + name
    material = UsdShade.Material.Define(stage, materialPath)

    # Store shaders inside their respective material path
    shaderPath = materialPath + "/Shader"
    # Create shader
    shader = UsdShade.Shader.Define(stage, shaderPath)
    # Use OmniPBR as a source to define our shader
    shader.SetSourceAsset("OmniPBR.mdl", "mdl")
    shader.GetPrim().CreateAttribute(
        "info:mdl:sourceAsset:subIdentifier",
        Sdf.ValueTypeNames.Token,
        False,
        Sdf.VariabilityUniform,
    ).Set("OmniPBR")

    # Set Diffuse texture.
    diffTexIn = shader.CreateInput("diffuse_texture", Sdf.ValueTypeNames.Asset)
    diffTexIn.Set(diffuse_image_path)
    diffTexIn.GetAttr().SetColorSpace("sRGB")

    # Set Diffuse value. TODO make default color NVIDIA Green
    # diffTintIn = shader.CreateInput("diffuse_tint", Sdf.ValueTypeNames.Color3f)
    # diffTintIn.Set((0.9, 0.9, 0.9))

    # Connect Material to Shader.
    mdlOutput = material.CreateSurfaceOutput("mdl")
    mdlOutput.ConnectToSource(shader, "out")

    return material


def bind_material(mesh_path: Sdf.Path, material: UsdShade.Material, stage: Usd.Stage):
    """Bind a material to a mesh

    Parameters
    ----------
    mesh_path : Sdf.Path
        The USD formatted path to a mesh prim
    material : UsdShade.Material
        USD material object
    stage : Usd.Stage
        Stage in which to find mesh prim
    """
    # Get the mesh prim
    meshPrim = stage.GetPrimAtPath(mesh_path)
    # Bind the mesh
    UsdShade.MaterialBindingAPI(meshPrim).Bind(material)