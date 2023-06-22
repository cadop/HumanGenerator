from typing import Tuple, List
from .mhcaller import MHCaller
import numpy as np
import omni.kit
import omni.usd
from pxr import Sdf, Usd, UsdGeom, UsdSkel
from .shared import sanitize, data_path
from .skeleton import Skeleton
from module3d import Object3D
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Sdf, Gf, Tf, UsdSkel, Vt
import carb
import os

from .materials import get_mesh_texture, create_material, bind_material
class Human:
    def __init__(self, name='human', **kwargs):
        """Constructs an instance of Human.

        Parameters
        ----------
        name : str
            Name of the human. Defaults to 'human'
        """

        self.name = name
        
        # Reference to the usd prim for the skelroot representing the human in the stage
        self.prim = None

        # Provide a scale factor (Omniverse provided humans are 10 times larger than makehuman)
        self.scale = 10

        # Create a skeleton object for the human
        self.skeleton = Skeleton(self.scale)

        # Set the human in makehuman to default values
        MHCaller.reset_human()

    def reset(self):
        """Resets the human in makehuman and adds a new skeleton to the human"""

        # Reset the human in makehuman
        MHCaller.reset_human()
        # Re-add the skeleton to the human
        self.skeleton = Skeleton(self.scale)

    def delete_proxies(self):
        """Deletes the prims corresponding to proxies attached to the human"""
        # Delete any child prims corresponding to proxies
        if self.prim:
            # Get the children of the human prim and delete them all at once
            proxy_prims = [child.GetPath() for child in self.prim.GetChildren() if child.GetCustomDataByKey("Proxy_path:")]
            omni.kit.commands.execute("DeletePrims", paths=proxy_prims)

    @property
    def prim_path(self):
        """Path to the human prim"""
        if self.prim:
            return self.prim.GetPath().pathString
        else:
            return None

    @property
    def objects(self):
        """List of objects attached to the human. Fetched from the makehuman app"""
        return MHCaller.objects

    @property
    def mh_meshes(self):
        """List of meshes attached to the human. Fetched from the makehuman app"""
        return MHCaller.meshes

    def add_to_scene(self):
        """Adds the human to the scene. Creates a prim for the human with custom attributes
        to hold modifiers and proxies. Also creates a prim for each proxy and attaches it to
        the human prim.

        Returns
        -------
        str
            Path to the human prim"""

        # Get the current stage
        stage = omni.usd.get_context().get_stage()

        root_path = "/"

        # Get default prim.
        default_prim = stage.GetDefaultPrim()
        if default_prim.IsValid():
            # Set the rootpath under the stage's default prim, if the default prim is valid
            root_path = default_prim.GetPath().pathString

        # Create a path for the next available prim
        prim_path = omni.usd.get_stage_next_free_path(stage, root_path + "/" + self.name, False)

        # Create a prim for the human
        # Prim should be a SkelRoot so we can rig the human with a skeleton later
        self.prim = UsdSkel.Root.Define(stage, prim_path)

        # Write the properties of the human to the prim
        self.write_properties(prim_path, stage)

        # Get the objects of the human from mhcaller
        objects = MHCaller.objects

        # Get the human object from the list of objects
        human = objects[0]

        # Determine the offset for the human from the ground
        offset = -1 * human.getJointPosition("ground")

        # Import makehuman objects into the scene
        mesh_paths = self.import_meshes(prim_path, stage, offset = offset)

        # Add the skeleton to the scene
        self.usd_skel= self.skeleton.add_to_stage(stage, prim_path, offset = offset)

        # Create bindings between meshes and the skeleton. Returns a list of
        # bindings the length of the number of meshes
        bindings = self.setup_bindings(mesh_paths, stage, self.usd_skel)

        # Setup weights for corresponding mh_meshes (which hold the data) and
        # bindings (which link USD_meshes to the skeleton)
        self.setup_weights(self.mh_meshes, bindings, self.skeleton.joint_names, self.skeleton.joint_paths)

        self.setup_materials(self.mh_meshes, mesh_paths, root_path, stage)

        # Explicitly setup material for human skin
        texture_path = data_path("skins/textures/skin.png")
        skin = create_material(texture_path, "Skin", root_path, stage)
        # Bind the skin material to the first prim in the list (the human)
        bind_material(mesh_paths[0], skin, stage)

        Human._set_scale(self.prim.GetPrim(), self.scale)

        return self.prim

    def update_in_scene(self, prim_path: str):
        """Updates the human in the scene. Writes the properties of the human to the
        human prim and imports the human and proxy meshes. This is called when the
        human is updated
        
        Parameters
        ----------
        prim_path : str
            Path to the human prim (prim type is SkelRoot)
        """

        usd_context = omni.usd.get_context()
        selection = usd_context.get_selection()
        selected_prim_paths = selection.get_selected_prim_paths()
        stage = usd_context.get_stage()

        if selected_prim_paths and stage:
            # Get the path of the selected prim
            if len(selected_prim_paths) == 1:
                path = selected_prim_paths[0]
                print(path)
                prim = stage.GetPrimAtPath(path)
                prim_kind = prim.GetTypeName()
                # Check if the prim is a SkelRoot and a human
                if prim_kind == "SkelRoot" and prim.GetCustomDataByKey("human"):
                    # Get default prim.
                    default_prim = stage.GetDefaultPrim()
                    if default_prim.IsValid():
                        # Set the rootpath under the stage's default prim, if the default prim is valid
                        root_path = default_prim.GetPath().pathString
                        
                    # Write the properties of the human to the prim
                    self.write_properties(prim_path, stage)

                    # Get the objects of the human from mhcaller
                    objects = MHCaller.objects

                    # Get the human object from the list of objects
                    human = objects[0]

                    # Determine the offset for the human from the ground
                    offset = -1 * human.getJointPosition("ground")

                    # Import makehuman objects into the scene
                    mesh_paths = self.import_meshes(prim_path, stage, offset = offset)

                    # Update the skeleton values and insert it into the stage
                    self.usd_skel = self.skeleton.update_in_scene(stage, prim_path, offset = offset)

                    # Get the meshGeom for the human
                    meshGeom = stage.GetPrimAtPath(mesh_paths[0]).GetPrim()
                    # Add sample blendshape
                    blend = self.add_blendshape(meshGeom, data_path("targets/stomach/stomach-pregnant-incr.target"))

                    # Create bindings between meshes and the skeleton. Returns a list of
                    # bindings the length of the number of meshes
                    bindings = self.setup_bindings(mesh_paths, stage, self.usd_skel)

                    # Get the binding for the human and add the blendshape to it
                    human_binding = bindings[0]
                    self.add_blendshape_binding(human_binding,blend)

                    # Setup weights for corresponding mh_meshes (which hold the data) and
                    # bindings (which link USD_meshes to the skeleton)
                    self.setup_weights(self.mh_meshes, bindings, self.skeleton.joint_names, self.skeleton.joint_paths)

                    self.setup_materials(self.mh_meshes, mesh_paths, root_path, stage)

                    # Explicitly setup material for human skin
                    texture_path = data_path("skins/textures/skin.png")
                    skin = create_material(texture_path, "Skin", root_path, stage)
                    # Bind the skin material to the first prim in the list (the human)
                    bind_material(mesh_paths[0], skin, stage)
                else:
                    carb.log_warn("The selected prim must be a human!")
            elif len(selected_prim_paths) > 1:
                carb.log_warn("Please select only one prim")
        else:
            carb.log_warn("Please select a prim")

    def import_meshes(self, prim_path: str, stage: Usd.Stage, offset: List[float] = [0, 0, 0]):
        """Imports the meshes of the human into the scene. This is called when the human is
        added to the scene, and when the human is updated. This function creates mesh prims
        for both the human and its proxies, and attaches them to the human prim. If a mesh already
        exists in the scene, its values are updated instead of creating a new mesh.

        Parameters
        ----------
        prim_path : str
            Path to the human prim
        stage : Usd.Stage
            Stage to write to
        offset : List[float], optional
            Offset to move the mesh relative to the prim origin, by default [0, 0, 0]

        Returns
        -------
        paths : array of: Sdf.Path
            Usd Sdf paths to geometry prims in the scene
        """

        # Get the objects of the human from mhcaller
        objects = MHCaller.objects

        # Get the meshes of the human and its proxies
        meshes = [o.mesh for o in objects]

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
            usd_mesh_path = prim_path + "/" + name
            usd_mesh_paths.append(usd_mesh_path)
            # Check to see if the mesh prim already exists
            prim = stage.GetPrimAtPath(usd_mesh_path)

            if prim.IsValid():
                # omni.kit.commands.execute("DeletePrims", paths=[usd_mesh_path])
                point_attr = prim.GetAttribute('points')
                point_attr.Set(coords)

                face_count = prim.GetAttribute('faceVertexCounts')
                nface = [nPerFace] * int(len(newvertindices) / nPerFace)
                face_count.Set(nface)

                face_idx = prim.GetAttribute('faceVertexIndices')
                face_idx.Set(newvertindices)

                normals_attr = prim.GetAttribute('normals')
                normals_attr.Set(mesh.getNormals())

                meshGeom = UsdGeom.Mesh(prim)

            # If it doesn't exist, make it. This will run the first time a human is created and
            # whenever a new proxy is added
            else:
                # First determine if the mesh is a proxy
                p = mesh.object.proxy
                if p:
                    #  Determine if the mesh is a clothes proxy or a proxymesh. If not, then
                    #  an existing proxy of this type already exists, and we must overwrite it
                    type = p.type if p.type else "proxymeshes"
                    if not (type == "clothes" or type == "proxymeshes"):
                        for child in self.prim.GetChildren():
                            child_type = child.GetCustomDataByKey("Proxy_type:")
                            if child_type == type:
                                # If the child prim has the same type as the proxy, delete it
                                omni.kit.commands.execute("DeletePrims", paths=[child.GetPath()])
                                break

                meshGeom = UsdGeom.Mesh.Define(stage, usd_mesh_path)

                prim = meshGeom.GetPrim()

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

                # If the mesh is a proxy, write the proxy path to the mesh prim
                if mesh.object.proxy:
                    p = mesh.object.proxy
                    type = p.type if p.type else "proxymeshes"
                    prim.SetCustomDataByKey("Proxy_path:", p.file)
                    prim.SetCustomDataByKey("Proxy_type:", type)
                    prim.SetCustomDataByKey("Proxy_name:", p.name)

            # Set vertex uvs. UVs are represented as a list of tuples, each of which is a 2D
            # coordinate. UV's are used to map textures to the surface of 3D geometry
            #   Example: texture coordinates for 3 vertices
            #   texCoords.Set([(0, 1), (0, 0), (1, 0)])

            texCoords = meshGeom.CreatePrimvar(
                "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying
            )
            texCoords.Set(mesh.getUVs(newuvindices))

            # # Subdivision is set to none. The mesh is as imported and not further refined
            meshGeom.CreateSubdivisionSchemeAttr().Set("none")



        # ConvertPath strings to USD Sdf paths. TODO change to map() for performance
        paths = [Sdf.Path(mesh_path) for mesh_path in usd_mesh_paths]

        return paths

    def write_properties(self, prim_path: str, stage: Usd.Stage):
        """Writes the properties of the human to the human prim. This includes modifiers and
        proxies. This is called when the human is added to the scene, and when the human is
        updated

        Parameters
        ----------
        prim_path : str
            Path to the human prim
        stage : Usd.Stage
            Stage to write to
        """

        prim = stage.GetPrimAtPath(prim_path)

        # Add custom data to the prim by key, designating the prim is a human
        prim.SetCustomDataByKey("human", True)

        # Get the modifiers of the human in mhcaller
        modifiers = MHCaller.modifiers

        for m in modifiers:
            # Add the modifier to the prim as custom data by key. For modifiers,
            # the format is "group/modifer:value"
            prim.SetCustomDataByKey("Modifiers:" + m.fullName, m.getValue())


        # NOTE We are not currently using proxies in the USD export. Proxy data is stored
        # in their respective mesh prims, so that deleting proxy prims will also remove the
        # proxies. The following code is left here for reference.

        # Get the proxies of the human in mhcaller
        # proxies = MHCaller.proxies

        # for p in proxies:
        #     # Add the proxy to the prim as custom data by key under "Proxies".
        #     # Proxy type should be "proxymeshes" if type cannot be determined from the
        #     # proxy.type property.
        #     type = p.type if p.type else "proxymeshes"

        #     # Only "proxymeshes" and "clothes" should be subdictionaries of "Proxies"
        #     if type == "clothes" or type == "proxymeshes":
        #         prim.SetCustomDataByKey("Proxies:" + type + ":" + p.name, p.file)

        #     # Other proxy types should be added as a key to the prim with their
        #     # type as the key and the path as the value
        #     else:
        #         prim.SetCustomDataByKey("Proxies:" + type, p.file)

    def set_prim(self, usd_prim : Usd.Prim):
        """Updates the human based on the given prim's attributes

        Parameters
        ----------
        usd_prim : Usd.Prim
            Prim from which to update the human model."""

        self.prim = usd_prim

        # Get the data from the prim
        humandata = self.prim.GetCustomData()

        # Get the list of modifiers from the prim
        modifiers = humandata.get("Modifiers")
        for m, v in modifiers.items():
            MHCaller.human.getModifier(m).setValue(v, skipDependencies=False)

        # Gather proxies from the prim children
        proxies = []
        for child in self.prim.GetChildren():
            if child.GetTypeName() == "Mesh" and child.GetCustomDataByKey("Proxy_path:"):
                proxies.append(child)

        # Clear the makehuman proxies
        MHCaller.clear_proxies()

        # # Make sure the proxy list is not empty
        if proxies:
            for p in proxies:
                type = p.GetCustomDataByKey("Proxy_type:")
                path = p.GetCustomDataByKey("Proxy_path:")
                # name = p.GetCustomDataByKey("Proxy_name:")
                MHCaller.add_proxy(path, type)

        # Update the human in MHCaller
        MHCaller.human.applyAllTargets()

    def setup_weights(self, mh_meshes: List['Object3D'], bindings: List[UsdSkel.BindingAPI], joint_names: List[str], joint_paths: List[str]):
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
        joint_paths : list of str
            List of the full usd path to each joint corresponding to the skeleton to bind to
        """

         # Generate bone weights for all meshes up front so they can be reused for all
        rawWeights = MHCaller.human.getVertexWeights(
            MHCaller.human.getSkeleton()
        )  # Basemesh weights
        for mesh in self.mh_meshes:
            if mesh.object.proxy:
                # Transfer weights to proxy
                parentWeights = mesh.object.proxy.getVertexWeights(
                    rawWeights, MHCaller.human.getSkeleton()
                )
            else:
                parentWeights = rawWeights
            # Transfer weights to face/vert masked and/or subdivided mesh
            weights = mesh.getVertexWeights(parentWeights)

            # Attach these vertexWeights to the mesh to pass them around the
            # exporter easier, the cloned mesh is discarded afterwards, anyway
            
            # if this is the same person, just skip updating weights
            mesh.vertexWeights = weights

        # Iterate through corresponding meshes and bindings
        for mh_mesh, binding in zip(mh_meshes, bindings):

            # Calculate vertex weights
            indices, weights = self.calculate_influences(mh_mesh, joint_names)
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

            UsdSkel.NormalizeWeights(weights, elementSize)
            UsdSkel.SortInfluences(indices, weights, elementSize)

            # Assign indices to binding
            indices_attribute = binding.CreateJointIndicesPrimvar(
                constant=False, elementSize=elementSize
            )

            joint_attr = binding.GetPrim().GetAttribute('skel:joints')
            joint_attr.Set(joint_paths)

            indices_attribute.Set(indices)


            # Assign weights to binding
            weights_attribute = binding.CreateJointWeightsPrimvar(
                constant=False, elementSize=elementSize
            )

            weights_attribute.Set(weights)

    def calculate_influences(self, mh_mesh: Object3D, joint_names: List[str]):
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

        num_verts = mh_mesh.getVertexCount(excludeMaskedVerts=False)

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

    def setup_bindings(self, paths: List[Sdf.Path], stage: Usd.Stage, skeleton: UsdSkel.Skeleton):
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

            attrs = prim.GetAttribute('primvars:skel:jointWeights')
            # Check if joint weights have already been applied
            if attrs.IsValid():
                prim_path = prim.GetPath()
                sdf_path = Sdf.Path(prim_path)
                binding = UsdSkel.BindingAPI.Get(stage, sdf_path)

                # relationships = prim.GetRelationships()
                # 'material:binding' , 'proxyPrim', 'skel:animationSource','skel:blendShapeTargets','skel:skeleton'
                # get_binding.GetSkeletonRel()

            else:
                # Create a binding applied to the prim
                binding = UsdSkel.BindingAPI.Apply(prim)
                # Create a relationship between the binding and the skeleton
                binding.CreateSkeletonRel().SetTargets([skeleton.GetPath()])

            # Add the binding to the list to return
            bindings.append(binding)

        return bindings
    
    def setup_materials(self, mh_meshes: List['Object3D'], meshes: List[Sdf.Path], root: str, stage: Usd.Stage):
        """Fetches materials from Makehuman meshes and applies them to their corresponding
        Usd mesh prims in the stage.

        Parameters
        ----------
        mh_meshes : List['Object3D']
            List of makehuman meshes
        meshes : List[Sdf.Path]
            Paths to Usd meshes in the stage
        root : str
            The root path under which to create new prims
        stage : Usd.Stage
            Usd stage in which to create materials, and which contains the meshes
            to which to apply materials
        """
        for mh_mesh, mesh in zip(self.mh_meshes, meshes):
            # Get a texture path and name from the makehuman mesh
            texture, name = get_mesh_texture(mh_mesh)
            if texture:
                # If we can get a texture from the makehuman mesh, create a material
                # from it and bind it to the corresponding USD mesh in the stage
                material = create_material(texture, name, root, stage)
                bind_material(mesh, material, stage)

    def add_item(self, path: str):
        """Add a new asset to the human. Propagates changes to the Makehuman app
        and then upates the stage with the new asset. If the asset is a proxy,
        targets will not be applied. If the asset is a skeleton, targets must
        be applied.

        Parameters
        ----------
        path : str
            Path to an asset on disk
        """

        # Check if human has a prim
        if self.prim:
            # Add an item through the MakeHuman instance and update the widget view
            MHCaller.add_item(path)
            self.update_in_scene(self.prim.GetPath().pathString)
        else:
            carb.log_warn("No prim selected")

    @staticmethod
    def _set_scale(prim : Usd.Prim, scale : float):
        """Set scale of a prim.
        
        Parameters
        ----------
        prim : Usd.Prim
            The prim to scale.
        scale : float
            The scale to apply."""

        if prim == None:
            return
        # Uniform scale.
        sV = Gf.Vec3f(scale, scale, scale)
        scale = prim.GetAttribute("xformOp:scale").Get()
        if scale != None:
            prim.GetAttribute("xformOp:scale").Set(Gf.Vec3f(sV))
        else:
            # xformOpOrder is also updated.
            xformAPI = UsdGeom.XformCommonAPI(prim)
            xformAPI.SetScale(Gf.Vec3f(sV))
    def add_blendshape(self, mesh : UsdGeom.Mesh, target: str):
        """Create a USD blendshape from a Makehuman .target file
        
        Parameters
        ----------
        mesh : UsdGeom.Mesh
            The mesh under which to create the blendshape
        target : str
            Path to a .target file representing the blendshape/target
        """

        # Check if the file exists
        if not os.path.exists(target):
            carb.log_warn("Target file does not exist")
            return
        

        # Open and parse the target file
        with open(target, 'r') as f:
            lines = f.readlines()

            length = len(lines)
            # Create an empty numpy array to hold the vertex indices
            indices = np.empty(length)
            # Create an empty numpy array to hold the vertex offsets
            offsets = np.empty((length, 3))


            # Iterate through the lines and get the vertex index and offset
            linenum = 0
            for line in lines:
                # Make sure the line is not a comment
                if not line.startswith('#'):
                    # The first value is the index, the next 3 are the offset
                    index, x, y, z = line.split()
                    # Add the index and weight to the lists
                    indices[linenum] = int(index)
                    offsets[linenum] = [float(x), float(y), float(z)]
                    linenum += 1

        # Trim the numpy arrays to the actual length
        indices = indices[:linenum]
        offsets = offsets[:linenum]

        # Convert the numpy arrays to Vt arrays
        indices = Vt.IntArray.FromNumpy(indices)
        offsets = Vt.Vec3fArray.FromNumpy(offsets)

        # Get the name of the target
        name = os.path.basename(target).split('.')[0]

        # Sanitize the name for USD
        name = sanitize(name)

        # Get the current usd context and stage
        usd_context = omni.usd.get_context()
        stage = usd_context.get_stage()

        # Get the prim from the mesh
        prim = mesh.GetPrim()

        # Get the path to the prim
        prim_path = prim.GetPath().pathString

        # Get the path to the blendshape
        blendshape_path = prim_path + "/" + name

        # Create a blendshape prim
        blendshape = UsdSkel.BlendShape.Define(stage, blendshape_path)

        # Create blendshape attributes
        blendshape.CreateOffsetsAttr(offsets)
        blendshape.CreatePointIndicesAttr(indices)

        return blendshape

    def add_blendshape_binding(self, binding: UsdSkel.BindingAPI, blendshape: UsdSkel.BlendShape):
        """Create a binding between a blendshape and a mesh

        Parameters
        ----------
        binding : UsdSkel.BindingAPI
            The binding between a mesh and a skeleton
        blendshape : UsdSkel.BlendShape
            The blendshape to bind to the mesh
        """
        binding.CreateBlendShapeTargetsRel().SetTargets([blendshape.GetPath()])
