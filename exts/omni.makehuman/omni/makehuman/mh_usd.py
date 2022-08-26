from typing import List, TypeVar
from numpy.random.tests import data
from omni.kit.commands.command import create
from omni.makehuman.mhcaller import MHCaller
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Sdf, Gf, Tf, UsdSkel, Vt
import omni.usd
import carb
import numpy as np
import io
import os
import re
import skeleton as mhskeleton
from .shared import data_path


def add_to_scene(mh_call: MHCaller):
    """Import Makehuman objects into the current USD stage

    Parameters
    ----------
    mh_call : MHCaller
        Wrapper object for calling Makehuman functions and accessing Makehuman data.
        This includes humans as well as proxies (clothes, hair, etc). In the case
        that a human has a skeleton applied, the skeleton is included and used to
        apply mesh weights. As meshweights on proxies reference the human
        meshweights, the human must either already be in the scene or be the
        first item in the list
    """
    objects = mh_call.objects
    name = mh_call.name

    scale = 10
    human = objects[0]

    # Offset human from the ground
    offset = -1 * human.getJointPosition("ground") * scale

    mh_meshes = [o.mesh for o in objects]

    if not isinstance(mh_meshes, list):
        mh_meshes = [mh_meshes]

    # Filter out vertices we aren't meant to see and scale up the meshes
    mh_meshes = [m.clone(scale, filterMaskedVerts=True) for m in mh_meshes]

    mhskel = human.getSkeleton()

    # Scale our skeleton to match our human
    if mhskel:
        mhskel = mhskel.scaled(scale)

    # Apply weights to the meshes (internal makehuman objects) Do we need to do
    # this if we're applying deformation through imported skeletons? Can we sync
    # it back to the human model Generate bone weights for all meshes up front
    # so they can be reused for all
    if mhskel:
        rawWeights = human.getVertexWeights(
            human.getSkeleton()
        )  # Basemesh weights
        for mesh in mh_meshes:
            if mesh.object.proxy:
                # Transfer weights to proxy
                parentWeights = mesh.object.proxy.getVertexWeights(
                    rawWeights, human.getSkeleton()
                )
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

    # Bones are returned breadth-first (parents-first). This is convenient, as
    # USD requires it bones = skel.getBones()

    # Get stage from open file
    stage = omni.usd.get_context().get_stage()

    # Get stage root path.
    rootPath = "/"

    # Get default prim.
    defaultPrim = stage.GetDefaultPrim()
    if defaultPrim.IsValid():
        # Set the rootpath under the stage's default prim
        rootPath = defaultPrim.GetPath().pathString

    # Rename our human if the mhcaller has been reset
    if mh_call.is_reset:
        mh_call.is_reset = False
        rootPath = omni.usd.get_stage_next_free_path(
            stage, rootPath + "/" + name, False
        )
        # Save the new name if a human with the old name already exists
        mh_call.name = rootPath.split("/")[-1]
    else:
        rootPath = rootPath + "/" + name

    UsdGeom.Xform.Define(stage, rootPath)

    if mhskel:
        # Create the USD skeleton in our stage using the mhskel data
        (usdSkel, rootPath, joint_names) = setup_skeleton(
            rootPath, stage, mhskel, offset
        )

        # Add the meshes to the USD stage under skelRoot
        usd_mesh_paths = setup_meshes(mh_meshes, stage, rootPath, offset)

        # Create bindings between meshes and the skeleton. Returns a list of
        # bindings the length of the number of meshes
        bindings = setup_bindings(usd_mesh_paths, stage, usdSkel)

        # Setup weights for corresponding mh_meshes (which hold the data) and
        # bindings (which link USD_meshes to the skeleton)
        setup_weights(mh_meshes, bindings, joint_names)
    else:
        rootPath = rootPath + "/human"
        skelRoot = UsdSkel.Root.Define(stage, rootPath)
        # Add the meshes to the USD stage under otherwise empty skelroot
        usd_mesh_paths = setup_meshes(mh_meshes, stage, rootPath, offset)

    # Import materials for proxies
    setup_materials(mh_meshes, usd_mesh_paths, rootPath, stage)

    # Explicitly setup material for human skin
    texture_path = data_path("textures/skin.png")
    skin = create_material(texture_path, "Skin", rootPath, stage)
    # Bind the skin material to the first prim in the list (the human)
    bind_material(usd_mesh_paths[0], skin, stage)

    return name


Object3D = TypeVar("Object3D")


def setup_weights(mh_meshes: List[Object3D], bindings: List[UsdSkel.BindingAPI], joint_names: List[str]):
    """Apply weights to USD meshes using data from makehuman. USD meshes,
    bindings and skeleton must already be in the active scene

    Parameters
    ----------
    mh_meshes : list of `Object3D`
        Makehuman meshes which store weight data
    bindings : list of `UsdSkel.BindingAPI`
        USD bindings between meshes and skeleton
    joint_names : list of str
        Unique, plaintext names of all joints in the skeleton in USD
        (breadth-first) order.
    """

    # Iterate through corresponding meshes and bindings
    for mh_mesh, binding in zip(mh_meshes, bindings):

        # Calculate vertex weights
        indices, weights = calculate_influences(mh_mesh, joint_names)
        # Type conversion to native ints and floats from numpy
        indices = list(map(int, indices))
        weights = list(map(float, weights))
        # Type conversion to USD
        indices = Vt.IntArray(indices)
        weights = Vt.FloatArray(weights)

        # The number of weights to apply to each vertex, taken directly from
        # MakeHuman data
        elementSize = int(mh_mesh.vertexWeights._nWeights)
        # weight_data = list(mh_mesh.vertexWeights.data) TODO remove

        # We might not need to normalize. Makehuman weights are automatically
        # normalized when loaded, see:
        # http://www.makehumancommunity.org/wiki/Technical_notes_on_MakeHuman
        # TODO Determine if this can be removed
        UsdSkel.NormalizeWeights(weights, elementSize)
        UsdSkel.SortInfluences(indices, weights, elementSize)

        # Assign indices to binding
        indices_attribute = binding.CreateJointIndicesPrimvar(
            constant=False, elementSize=elementSize
        )
        indices_attribute.Set(indices)

        # Assign weights to binding
        weights_attribute = binding.CreateJointWeightsPrimvar(
            constant=False, elementSize=elementSize
        )
        weights_attribute.Set(weights)


def calculate_influences(mh_mesh: Object3D, joint_names: List[str]):
    """Build arrays of joint indices and corresponding weights for each vertex.
    Joints are in USD (breadth-first) order.

    Parameters
    ----------
    mh_mesh : Object3D
        Makehuman-format mesh. Contains weight and vertex data.
    joint_names : list of str
        Unique, plaintext names of all joints in the skeleton in USD
        (breadth-first) order.

    Returns
    -------
    indices : list of int
        Flat list of joint indices for each vertex
    weights : list of float
        Flat list of weights corresponding to joint indices
    """
    # The maximum number of weights a vertex might have
    max_influences = mh_mesh.vertexWeights._nWeights

    # Named joints corresponding to vertices and weights ie.
    # {"joint",([indices],[weights])}
    influence_joints = mh_mesh.vertexWeights.data

    num_verts = mh_mesh.getVertexCount(excludeMaskedVerts=True)

    # all skeleton joints in USD order
    binding_joints = joint_names

    # Corresponding arrays of joint indices and weights of length num_verts.
    # Allots the maximum number of weights for every vertex, and pads any
    # remaining weights with 0's, per USD spec, see:
    # https://graphics.pixar.com/usd/dev/api/_usd_skel__schemas.html#UsdSkel_BindingAPI
    # "If a point has fewer influences than are needed for other points, the
    # unused array elements of that point should be filled with 0, both for
    # joint indices and for weights."

    indices = np.zeros((num_verts, max_influences))
    weights = np.zeros((num_verts, max_influences))

    # Keep track of the number of joint influences on each vertex
    influence_counts = np.zeros(num_verts, dtype=int)

    for joint, joint_data in influence_joints.items():
        # get the index of the joint in our USD-ordered list of all joints
        joint_index = binding_joints.index(joint)
        for vert_index, weight in zip(*joint_data):

            # Use influence_count to keep from overwriting existing influences
            influence_count = influence_counts[vert_index]

            # Add the joint index to our vertex array
            indices[vert_index][influence_count] = joint_index
            # Add the weight to the same vertex
            weights[vert_index][influence_count] = weight

            # Add to the influence count for this vertex
            influence_counts[vert_index] += 1

    # Check for any unweighted verts (this is a test routine)
    # for i, d in enumerate(indices): if np.all((d == 0)): print(i)

    # Flatten arrays to one dimensional lists
    indices = indices.flatten()
    weights = weights.flatten()

    return indices, weights


def setup_bindings(paths: List[Sdf.Path], stage: Usd.Stage, skeleton: UsdSkel.Skeleton):
    """Setup bindings between meshes in the USD scene and the skeleton

    Parameters
    ----------
    paths : List of Sdf.Path
        USD Sdf paths to each mesh prim
    stage : Usd.Stage
        The USD stage where the prims can be found
    skeleton : UsdSkel.Skeleton
        The USD skeleton to apply bindings to

    Returns
    -------
    array of: UsdSkel.BindingAPI
        Array of bindings between each mesh and the skeleton, in "path" order
    """
    bindings = []

    # TODO rename "mesh" to "path"
    for mesh in paths:
        # Get the prim in the stage
        prim = stage.GetPrimAtPath(mesh)

        # Create a binding applied to the prim
        binding = UsdSkel.BindingAPI.Apply(prim)

        # Create a relationship between the binding and the skeleton
        binding.CreateSkeletonRel().SetTargets([skeleton.GetPath()])

        # Add the binding to the list to return
        bindings.append(binding)

    return bindings


def setup_meshes(meshes: List[Object3D], stage: Usd.Stage, rootPath: str, offset: List[float] = [0, 0, 0]):
    """Import mesh data and build mesh prims in the USD stage

    Parameters
    ----------
    meshes : list of: `Object3D`
        Makehuman meshes
    stage : Usd.Stage
        The stage to which to add the mesh geometry
    rootPath : str
        The path under which to place imported mesh prims
    offset : list of float, optional
        A vector [x,y,z] to shift the created geometry relative to the prim origin. By default [0,0,0]
    Returns
    -------
    paths : array of: Sdf.Path
        Usd Sdf paths to geometry prims in the scene
    """

    usd_mesh_paths = []

    for mesh in meshes:
        # Number of vertices per face
        nPerFace = mesh.vertsPerFaceForExport
        # Lists to hold pruned lists of vertex and UV indices
        newvertindices = []
        newuvindices = []

        # Array of coordinates organized [[x1,y1,z1],[x2,y2,z2]...]
        # Adding the given offset moves the mesh relative to the prim origin
        coords = mesh.getCoords() + offset
        for fn, fv in enumerate(mesh.fvert):
            if not mesh.face_mask[fn]:
                continue
            # only include <nPerFace> verts for each face, and order them
            # consecutively
            newvertindices += [(fv[n]) for n in range(nPerFace)]
            fuv = mesh.fuvs[fn]
            # build an array of (u,v)s for each face
            newuvindices += [(fuv[n]) for n in range(nPerFace)]

        # Type conversion
        newvertindices = np.array(newvertindices)

        # Create mesh prim at appropriate path. Does not yet hold any data
        name = sanitize(mesh.name)
        usd_mesh_path = rootPath + "/" + name
        usd_mesh_paths.append(usd_mesh_path)
        # Check to see if the mesh prim already exists
        prim = stage.GetPrimAtPath(usd_mesh_path)
        if prim.IsValid():
            omni.kit.commands.execute("DeletePrims", paths=[usd_mesh_path])
            # prim.RemoveProperty("points")
            # prim.RemoveProperty("faceVertexCounts")
            # prim.RemoveProperty("faceVertexIndices")            
            # prim.RemoveProperty("normals")
            # meshGeom = UsdGeom.Mesh(prim)
        meshGeom = UsdGeom.Mesh.Define(stage, usd_mesh_path)

        # Set vertices. This is a list of tuples for ALL vertices in an unassociated
        # cloud. Faces are built based on indices of this list.
        #   Example: 3 explicitly defined vertices:
        #   meshGeom.CreatePointsAttr([(-10, 0, -10), (-10, 0, 10), (10, 0, 10)]
        meshGeom.CreatePointsAttr(coords)

        # Set face vertex count. This is an array where each element is the number
        # of consecutive vertex indices to include in each face definition, as
        # indices are given as a single flat list. The length of this list is the
        # same as the number of faces
        #   Example: 4 faces with 4 vertices each
        #   meshGeom.CreateFaceVertexCountsAttr([4, 4, 4, 4])
        nface = [nPerFace] * int(len(newvertindices) / nPerFace)
        meshGeom.CreateFaceVertexCountsAttr(nface)

        # Set face vertex indices.
        #   Example: one face with 4 vertices defined by 4 indices.
        #   meshGeom.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
        meshGeom.CreateFaceVertexIndicesAttr(newvertindices)

        # Set vertex normals. Normals are represented as a list of tuples each of
        # which is a vector indicating the direction a point is facing. This is later
        # Used to calculate face normals
        #   Example: Normals for 3 vertices
        # meshGeom.CreateNormalsAttr([(0, 1, 0), (0, 1, 0), (0, 1, 0), (0, 1,
        # 0)])
        meshGeom.CreateNormalsAttr(mesh.getNormals())
        meshGeom.SetNormalsInterpolation("vertex")

        # Set vertex uvs. UVs are represented as a list of tuples, each of which is a 2D
        # coordinate. UV's are used to map textures to the surface of 3D geometry
        #   Example: texture coordinates for 3 vertices
        #   texCoords.Set([(0, 1), (0, 0), (1, 0)])
        texCoords = meshGeom.CreatePrimvar(
            "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying
        )
        texCoords.Set(mesh.getUVs(newuvindices))

        # Subdivision is set to none. The mesh is as imported and not further refined
        meshGeom.CreateSubdivisionSchemeAttr().Set("none")

    # ConvertPath strings to USD Sdf paths. TODO change to map() for performance
    paths = [Sdf.Path(mesh_path) for mesh_path in usd_mesh_paths]
    return paths


def inspect_meshes(meshes: List[Object3D]):
    """Testing routine to ensure that all vertices are used. Prints out the difference
    between the set of all vertices and the vertices which have been used in the mesh
    (prints any vertices which have not been used)

    Parameters
    ----------
    meshes : list of `Object3D`
        Makehuman meshes
    """
    # For inspecting mesh topology while debugging broken meshes
    for mesh in meshes:
        # A set of vertex indices where each item cannot appear more than once
        all_vert_indices = set()
        nPerFace = mesh.vertsPerFaceForExport
        coords = mesh.getCoords()
        for fn, fv in enumerate(mesh.fvert):
            if not mesh.face_mask[fn]:
                continue
            # only include <nPerFace> verts for each face, and order them consecutively
            all_vert_indices.update([(fv[n]) for n in range(nPerFace)])

        # Sort the set of indices so they are in order
        sorted_indices = sorted(all_vert_indices)
        # A sequence of numbers from zero to the length of the coordinates. If all
        # vertices are used, rng and sorted_indices should be identical
        rng = range(len(coords))
        dif = sorted_indices.symmetric_difference(rng)
        # Return the set of unused vertices
        print("Difference: {}".format(dif))


Skeleton = TypeVar("Skeleton")


def setup_skeleton(rootPath: str, stage: Usd.Stage, skeleton: Skeleton, offset: List[float] = [0, 0, 0]):
    """Get the skeleton data from makehuman and place it in the stage. Also adds
    a new parent to the root node, so the root can have an identity transform at
    the origin. This helps keep the character above ground, and follows the
    guidelines outlined by Lina Halper for the Animation Retargeting extension
    See: docs.omniverse.nvidia.com/prod_extensions/prod_extensions/ext_animation-retargeting.html

    Parameters
    ----------
    rootPath : str
        Path to the root prim of the stage
    stage : Usd.Stage.Open
        The USD stage in which to set up the skeleton
    skeleton : makehuman.skeleton.Skeleton
        The makehuman skeleton object
    offset : list of float, optional
        Offset vector for placement in scene, by default [0,0,0]

    Returns
    -------
    usdSkel : UsdSkel.Skeleton
        The USD formatted skeleton with parameters applied
    skel_root_path : str
        The path to the UsdSkel.Root. This is important because skinned meshes
        should be under the same root as the skeleton. This is not the root
        joint of the skeleton, nor the skeleton itself; rather it is a container
        prim that holds the skeleton and skinned meshes in the stage hierarchy.
    joint_names : list of: str
        List of joint names in USD (breadth-first traversal) order. It is
        important that joints be ordered this way so that their indices can be
        used for skinning / weighting.
    """
    joint_paths = []
    joint_names = []
    rel_transforms = []
    global_transforms = []
    bind_transforms = []

    # Process each node individually
    def process_node(node, path):
        """Get the name, path, relative transform, global transform, and bind
        transform of each joint and add them to the list of stored values

        Parameters
        ----------
        node : skeleton.Bone
            Makehuman joint node
        path : str
            Path to the relative root of the usd skeleton
        """

        # sanitize the name for USD paths
        name = sanitize(node.name)
        path += name
        joint_paths.append(path)

        # store original name for later joint weighting
        joint_names.append(node.name)

        # Get matrix for joint transform relative to its parent. Move to offset
        # to match mesh transform in scene
        relxform = node.getRelativeMatrix(offsetVect=offset)
        # Transpose the matrix as USD stores transforms in row-major format
        relxform = relxform.transpose()
        # Convert type for USD and store
        relative_transform = Gf.Matrix4d(relxform.tolist())
        rel_transforms.append(relative_transform)

        # Get matrix for joint transform at rest in global coordinate space. Move
        # to offset to match mesh transform in scene
        gxform = node.getRestMatrix(offsetVect=offset)
        # Transpose the matrix as USD stores transforms in row-major format
        gxform = gxform.transpose()
        # Convert type for USD and store
        global_transform = Gf.Matrix4d(gxform.tolist())
        global_transforms.append(global_transform)

        # Get matrix which represents a joints transform in its binding position
        # for binding to a mesh. Move to offset to match mesh transform.
        bxform = node.getBindMatrix(offsetVect=offset)
        # getBindMatrix returns bindmat and bindinv - we want the uninverted
        # matrix, however USD uses row first while mh uses column first, so we
        # use the provided inverse
        bxform = bxform[1]
        # Convert type for USD and store
        bind_transform = Gf.Matrix4d(bxform.tolist())
        # bind_transform = Gf.Matrix4d().SetIdentity() TODO remove
        bind_transforms.append(bind_transform)

    # TODO Move below super-root code
    visited = []  # List to keep track of visited nodes.
    queue = []  # Initialize a queue
    path_queue = []  # Keep track of paths in a parallel queue

    # make a "super-root" node, parent to the root, with identity transforms so
    # we can abide by Lina Halper's animation retargeting guidelines:
    # https://docs.omniverse.nvidia.com/prod_extensions/prod_extensions/ext_animation-retargeting.html
    # TODO encapsulate in scope for clarity
    originalRoot = skeleton.roots[0]
    newRoot = skeleton.addBone(
        "RootJoint", None, "newRoot_head", originalRoot.tailJoint
    )
    originalRoot.parent = newRoot
    newRoot.headPos -= offset
    newRoot.build()
    newRoot.children.append(originalRoot)

    # Setup a breadth-first search of our skeleton as a tree
    # TODO encapsulate in scope for clarity
    # Use the new root of the mh skeleton as the root node of our tree
    node = skeleton.roots[-1]

    visited.append(node)
    queue.append(node)
    name = sanitize(node.name)
    path_queue.append(name + "/")

    # joints are relative to the root, so we don't prepend a path for the root
    process_node(node, "")

    # Traverse skeleton (breadth-first) and store joint data
    while queue:
        v = queue.pop(0)
        path = path_queue.pop(0)

        for neighbor in v.children:
            if neighbor not in visited:
                visited.append(neighbor)
                queue.append(neighbor)
                name = sanitize(neighbor.name)
                path_queue.append(path + name + "/")

                process_node(neighbor, path)

    skel_root_path = rootPath + "/human"
    skeleton_path = skel_root_path + "/Skeleton"

    skelRoot = UsdSkel.Root.Define(stage, skel_root_path)
    usdSkel = UsdSkel.Skeleton.Define(stage, skeleton_path)

    # add joints to skeleton by path
    attribute = usdSkel.GetJointsAttr()
    # exclude root
    attribute.Set(joint_paths)

    # Add bind transforms to skeleton
    usdSkel.CreateBindTransformsAttr(bind_transforms)

    # setup rest transforms in joint-local space
    usdSkel.CreateRestTransformsAttr(rel_transforms)

    return usdSkel, skel_root_path, joint_names


def setup_materials(mh_meshes: List[Object3D], meshes: List[Sdf.Path], root: str, stage: Usd.Stage):
    """Fetches materials from Makehuman meshes and applies them to their corresponding
    Usd mesh prims in the stage.

    Parameters
    ----------
    mh_meshes : List[Object3D]
        Makehuman meshes. Contain references to textures on disk.
    meshes : List[Sdf.Path]
        Paths to Usd meshes in the stage
    root : str
        The root path under which to create new prims
    stage : Usd.Stage
        Usd stage in which to create materials, and which contains the meshes
        to which to apply materials
    """
    for mh_mesh, mesh in zip(mh_meshes, meshes):
        # Get a texture path and name from the makehuman mesh
        texture, name = get_mesh_texture(mh_mesh)
        if texture:
            # If we can get a texture from the makehuman mesh, create a material
            # from it and bind it to the corresponding USD mesh in the stage
            material = create_material(texture, name, root, stage)
            bind_material(mesh, material, stage)


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


def sanitize(s: str):
    """Sanitize strings for use a prim names. Strips and replaces illegal
    characters.

    Parameters
    ----------
    s : str
        Input string

    Returns
    -------
    s : str
        Primpath-safe output string
    """
    # List of illegal characters
    # TODO create more comprehensive list
    # TODO switch from blacklisting illegal characters to whitelisting valid ones
    illegal = (".", "-")
    for c in illegal:
        # Replace illegal characters with underscores
        s = s.replace(c, "_")
    return s
