from numpy.random.tests import data
from omni.kit.commands.command import create
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Sdf, Gf, Tf, UsdSkel, Vt
import omni.usd
import carb
import numpy as np
import io, os
import re
import skeleton as mhskeleton
from .shared import data_path


def add_to_scene(objects):
    """Import a list of Makehuman objects to the current USD stage

    Parameters
    ----------
    objects : list of: guicommon.Object
        Any object that encapsulates a module3d.Object3D mesh. This includes
        makehuman humans as well as proxies (clothes, hair, etc). In the case of
        a human, the skeleton is included and used to apply mesh weights. As
        meshweights on proxies reference the human meshweights, the human must
        either already be in the scene or be the first item in the list
    """

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
        # Add the meshes to the USD stage under root
        usd_mesh_paths = setup_meshes(mh_meshes, stage, rootPath, offset)

    # Import materials for proxies
    setup_materials(mh_meshes, usd_mesh_paths, rootPath, stage)

    # Explicitly setup material for human skin
    texture_path = data_path("textures/skin.png")
    skin = create_material(texture_path, "Skin", rootPath, stage)

    bind_material(usd_mesh_paths[0], skin, stage)


def setup_weights(mh_meshes, bindings, joint_names):
    """Apply weights to USD meshes using data from makehuman. USD meshes,
    bindings and skeleton must already be in the active scene

    Parameters
    ----------
    mh_meshes : list of: `module3d.Object3D`
        Makehuman meshes which store weight data
    bindings : list of `UsdSkel.BindingAPI`
        USD bindings between meshes and skeleton
    joint_names : list of str
        Unique, plaintext names of all joints in the skeleton in USD
        (breadth-first) order.
    """
    # Iterate through corresponding meshes and bindings
    for mh_mesh, binding in zip(mh_meshes, bindings):

        indices, weights = calculate_influences(mh_mesh, joint_names)

        indices = list(map(int, indices))
        weights = list(map(float, weights))

        indices = Vt.IntArray(indices)
        weights = Vt.FloatArray(weights)

        elementSize = int(mh_mesh.vertexWeights._nWeights)
        # weight_data = list(mh_mesh.vertexWeights.data)

        # We might not need to normalize. Makehuman weights are automatically
        # normalized when loaded, see:
        # http://www.makehumancommunity.org/wiki/Technical_notes_on_MakeHuman
        UsdSkel.NormalizeWeights(weights, elementSize)
        UsdSkel.SortInfluences(indices, weights, elementSize)

        indices_attribute = binding.CreateJointIndicesPrimvar(
            constant=False, elementSize=elementSize
        )
        indices_attribute.Set(indices)

        weights_attribute = binding.CreateJointWeightsPrimvar(
            constant=False, elementSize=elementSize
        )
        weights_attribute.Set(weights)


def calculate_influences(mh_mesh, joint_names):
    """Build arrays of joint indices and corresponding weights for each vertex.
    Joints are in USD (breadth-first) order.

    Parameters
    ----------
    mh_mesh : module3d.Object3D
        Makehuman-format mesh. Contains weight and vertex data.
    joint_names : list of: str
        Unique, plaintext names of all joints in the skeleton in USD
        (breadth-first) order.

    Returns
    -------
    indices : list of int
        Flat list of joint indices for each vertex
    weights : list of float
        Flat list of weights corresponding to joint indices
    """
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

    # Check for any unweighted verts for i, d in enumerate(indices): if
    # np.all((d == 0)): print(i)

    indices = indices.flatten()
    weights = weights.flatten()

    return indices, weights


def setup_bindings(paths, stage, skeleton):
    """Setup bindings between meshes in the USD scene and the skeleton

    Parameters
    ----------
    paths : array of: Sdf.Path
        USD Sdf paths to each mesh prim
    stage : Usd.Stage.Open
        The USD stage where the prims can be found
    skeleton :UsdSkel.Skeleton
        The USD skeleton to apply bindings to

    Returns
    -------
    array of: UsdSkel.BindingAPI
        Array of bindings between each mesh and the skeleton, in "path" order
    """
    bindings = []

    for mesh in paths:
        prim = stage.GetPrimAtPath(mesh)
        binding = UsdSkel.BindingAPI.Apply(prim)
        binding.CreateSkeletonRel().SetTargets([skeleton.GetPath()])
        bindings.append(binding)
    return bindings


def setup_meshes(meshes, stage, rootPath, offset=[0, 0, 0]):
    """Import mesh data and build mesh prims in the USD stage

    Parameters
    ----------
    meshes : list of: `module3d.Object3D`
        Makehuman meshes
    stage : Usd.Stage.Open()
        The stage to which to add the mesh geometry
    rootPath : str
        The path under which to place imported mesh prims

    Returns
    -------
    paths : array of: Sdf.Path
        Usd Sdf paths to geometry prims in the scene
    """

    usd_mesh_paths = []

    for mesh in meshes:

        nPerFace = mesh.vertsPerFaceForExport
        newvertindices = []
        newuvindices = []

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

        newvertindices = np.array(newvertindices)

        # Create mesh.
        name = sanitize(mesh.name)
        usd_mesh_path = rootPath + "/" + name
        usd_mesh_paths.append(usd_mesh_path)
        meshGeom = UsdGeom.Mesh.Define(stage, usd_mesh_path)

        # Set vertices.
        meshGeom.CreatePointsAttr(coords)
        # meshGeom.CreatePointsAttr([(-10, 0, -10), (-10, 0, 10), (10, 0, 10),
        # (10, 0, -10)])

        # Set face vertex count.
        nface = [nPerFace] * int(len(newvertindices) / nPerFace)
        meshGeom.CreateFaceVertexCountsAttr(nface)

        # Set face vertex indices.
        meshGeom.CreateFaceVertexIndicesAttr(newvertindices)
        # # meshGeom.CreateFaceVertexIndicesAttr([0, 1, 2, 3])

        # Set normals.
        meshGeom.CreateNormalsAttr(mesh.getNormals())
        # meshGeom.CreateNormalsAttr([(0, 1, 0), (0, 1, 0), (0, 1, 0), (0, 1,
        # 0)])
        meshGeom.SetNormalsInterpolation("vertex")

        # Set uvs.
        texCoords = meshGeom.CreatePrimvar(
            "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying
        )
        texCoords.Set(mesh.getUVs(newuvindices))
        # texCoords.Set([(0, 1), (0, 0), (1, 0), (1, 1)])

        # # Subdivision is set to none.
        meshGeom.CreateSubdivisionSchemeAttr().Set("none")

    paths = [Sdf.Path(mesh_path) for mesh_path in usd_mesh_paths]
    return paths


def inspect_meshes(meshes):
    """Testing routine to ensure that all vertices are used

    Parameters
    ----------
    meshes : list of: `module3d.Object3D`
        Makehuman meshes
    """
    # For inspecting mesh topology while debugging broken meshes
    for mesh in meshes:
        all_vert_indices = set()
        nPerFace = mesh.vertsPerFaceForExport
        coords = mesh.getCoords()
        for fn, fv in enumerate(mesh.fvert):
            if not mesh.face_mask[fn]:
                continue
            # only include <nPerFace> verts for each face, and order them
            # consecutively
            all_vert_indices.update([(fv[n]) for n in range(nPerFace)])

        sorted_indices = sorted(all_vert_indices)
        rng = range(len(coords))
        dif = sorted_indices.symmetric_difference(rng)
        print("Difference: {}".format(dif))


def setup_skeleton(rootPath, stage, skeleton, offset=[0, 0, 0]):
    """Get the skeleton data from makehuman and place it in the stage. Also adds
    a new parent to the root node, so the root can have an identity transform at
    the origin. This helps keep the character above ground, and Omniverse likes
    it for some reason.

    Parameters
    ----------
    rootPath : str
        Path to the root prim of the stage
    stage : Usd.Stage.Open
        The USD stage in which to set up the skeleton
    skeleton : makehuman.skeleton.Skeleton
        The makehuman skeleton object
    offset : list, optional
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

    # Traverses skeleton (breadth-first) and stores joint data
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

        relxform = node.getRelativeMatrix(offsetVect=offset)
        relxform = relxform.transpose()
        relative_transform = Gf.Matrix4d(relxform.tolist())
        rel_transforms.append(relative_transform)

        gxform = node.getRestMatrix(offsetVect=offset)
        gxform = gxform.transpose()
        global_transform = Gf.Matrix4d(gxform.tolist())
        global_transforms.append(global_transform)

        bxform = node.getBindMatrix(offsetVect=offset)
        # getBindMatrix returns bindmat and bindinv - we want the uninverted
        # matrix, however USD uses row first while mh uses column first, so we
        # use the transpose/inverse
        bxform = bxform[1]
        bind_transform = Gf.Matrix4d(bxform.tolist())
        # bind_transform = Gf.Matrix4d().SetIdentity()
        bind_transforms.append(bind_transform)

    visited = []  # List to keep track of visited nodes.
    queue = []  # Initialize a queue
    path_queue = []  # Keep track of paths in a parallel queue

    # make a "super-root" node, parent to the root, with identity transforms so
    # we can abide by Lina Halper's animation retargeting guidelines:
    # https://docs.omniverse.nvidia.com/prod_extensions/prod_extensions/ext_animation-retargeting.html

    originalRoot = skeleton.roots[0]
    newRoot = skeleton.addBone(
        "RootJoint", None, "newRoot_head", originalRoot.tailJoint
    )
    originalRoot.parent = newRoot
    newRoot.headPos -= offset
    newRoot.build()
    newRoot.children.append(originalRoot)

    # Use the new root of the mh skeleton as the root node of our tree
    node = skeleton.roots[-1]

    visited.append(node)
    queue.append(node)
    name = sanitize(node.name)
    path_queue.append(name + "/")

    # joints are relative to the root, so we don't prepend a path for the root
    process_node(node, "")

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


def setup_materials(mh_meshes, meshes, root, stage):
    for mh_mesh, mesh in zip(mh_meshes, meshes):
        texture, name = get_mesh_texture(mh_mesh)
        if texture:
            material = create_material(texture, name, root, stage)
            bind_material(mesh, material, stage)


def get_mesh_texture(mh_mesh):
    material = mh_mesh.material
    texture = material.diffuseTexture
    name = material.name
    if texture:
        return texture, name
    else:
        return (None, None)


def create_material(diffuse_image_path, name, root_path, stage):
    """Create OmniPBR Material with specified diffuse texture

    Parameters
    ----------
    diffuse_image_path : str
        Path to diffuse texture on disk
    name : str
        Material name
    root_path : str
        Root path under which to place material scope
    stage : Usd.Stage.Open()
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

    shaderPath = materialPath + "/Shader"
    shader = UsdShade.Shader.Define(stage, shaderPath)
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

    # Set Diffuse value.
    # diffTintIn = shader.CreateInput("diffuse_tint", Sdf.ValueTypeNames.Color3f)
    # diffTintIn.Set((0.9, 0.9, 0.9))

    # Connecting Material to Shader.
    mdlOutput = material.CreateSurfaceOutput("mdl")
    mdlOutput.ConnectToSource(shader, "out")

    return material


def bind_material(mesh_path, material, stage):
    """Bind a material to a mesh

    Parameters
    ----------
    mesh_path : Sdf.Path
        _description_
    material : UsdShade.Material
        _description_
    stage : Usd.Stage.Open
        _description_
    """
    meshPrim = stage.GetPrimAtPath(mesh_path)
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
        Prim-safe output string
    """
    illegal = (".", "-")
    for c in illegal:
        s = s.replace(c, "_")
    return s
