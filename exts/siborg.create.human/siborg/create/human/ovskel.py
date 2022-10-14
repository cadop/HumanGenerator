from pxr import Usd, Gf, UsdSkel
from typing import List
import numpy as np
from .shared import sanitize
from .mh_wrapper import skeleton


class OVSkel:
    """Object which holds methods and data for creating a skeleton in the scene

    Attributes
    ----------
    name : str
        Name of the human this skeleton represents. Used for prim path names.
    usdSkel : UsdSkel.Skeleton
        The USD formatted skeleton with parameters applied
    skel_in : Skeleton
        A skeleton object compatible with the Skeleton definition
    joint_paths : list of: str
        List of joint paths that are used as joint indices
    joint_names : list of: str
        List of joint names in USD (breadth-first traversal) order. It is
        important that joints be ordered this way so that their indices can be
        used for skinning / weighting.
    joint_paths : list of str
        Paths to joints in the stage hierarchy
    joint_names : list of str
        Names of joints in the stage
    scale : float
        Scale factor
    offset : list of float
        Offset vector for placement relative to origin
    """

    def __init__(self, name: str, skel_in: Skeleton, offset: List[float] = [0, 0, 0], scale: float = 10):
        """Get the skeleton data from makehuman and place it in the stage. Also adds
        a new parent to the root bone, so the root can have an identity transform at
        the origin. This helps keep the character above ground, and follows the
        guidelines outlined by Lina Halper for the Animation Retargeting extension
        See: docs.omniverse.nvidia.com/prod_extensions/prod_extensions/ext_animation-retargeting.html

        Parameters
        ----------
        name : str
            Name to use for the path to the skeleton
        skel_in : Skeleton
            A skeleton object compatible with the Skeleton definition The skeleton
            data to import into the scene
        offset : list of float, optional
            Offset vector for placement in scene, by default [0,0,0]
        scale : float, optional
            Scale factor, by default 10
        """
        self.name = name
        self.usdSkel = None
        self.skel_in = skel_in
        self.joint_paths = []
        self.joint_names = []
        self.rel_transforms = []
        self.bind_transforms = []
        self.scale = scale
        self.offset = offset

    def add_to_stage(self, stage: Usd.Stage, stage_root_path: str, new_root: bool = False):
        """Adds a skeleton to the Usd stage using data from the MakeHuman skeleton

        Parameters
        ----------
        stage : Usd.Stage
            Stage in which to create skeleton prims
        stage_root_path : str
            Path to the root prim in the stage
        new_root : bool, optional
            Whether or not to prepend a new root at the origin, by default False
        """
        root_bone = self.skel_in.roots[0]

        if new_root:
            root_bone = self.prepend_root(root_bone)

        self.setup_skeleton(root_bone)

        skel_root_path = stage_root_path + self.name
        skeleton_path = skel_root_path + "/Skeleton"

        skelRoot = UsdSkel.Root.Define(stage, skel_root_path)
        usdSkel = UsdSkel.Skeleton.Define(stage, skeleton_path)

        # add joints to skeleton by path
        attribute = usdSkel.GetJointsAttr()
        # exclude root
        attribute.Set(self.joint_paths)

        # Add bind transforms to skeleton
        usdSkel.CreateBindTransformsAttr(self.bind_transforms)

        # setup rest transforms in joint-local space
        usdSkel.CreateRestTransformsAttr(self.rel_transforms)

    def setup_skeleton(self, bone: Bone) -> None:
        """Traverse the imported skeleton and get the data for each bone for
        adding to the stage

        Parameters
        ----------
        bone : Bone
            The root bone at which to start traversing the imported skeleton.
        """
        # Setup a breadth-first search of our skeleton as a tree
        # Use the new root of the imported skeleton as the root bone of our tree

        visited = []  # List to keep track of visited bones.
        queue = []  # Initialize a queue
        path_queue = []  # Keep track of paths in a parallel queue

        visited.append(bone)
        queue.append(bone)
        name = sanitize(bone.name)
        path_queue.append(name + "/")

        # joints are relative to the root, so we don't prepend a path for the root
        self.process_bone(bone, "")

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

                    self.process_bone(neighbor, path)

    def prepend_root(self, oldRoot: Bone, newroot_name: str = "RootJoint") -> Bone:
        """Adds a new root bone to the head of a skeleton, ahead of the existing root bone.

        Parameters
        ----------
        oldRoot : Bone
            The original MakeHuman root bone
        newroot_name : str, optional
            The name for the new root bone, by default "RootJoint"

        Returns
        -------
        newRoot : Bone
            The new root bone of the Skeleton
        """
        # make a "super-root" bone, parent to the root, with identity transforms so
        # we can abide by Lina Halper's animation retargeting guidelines:
        # https://docs.omniverse.nvidia.com/prod_extensions/prod_extensions/ext_animation-retargeting.html
        newRoot = self.skel_in.addBone(newroot_name, None, "newRoot_head", oldRoot.tailJoint)
        oldRoot.parent = newRoot
        newRoot.headPos -= self.offset
        newRoot.build()
        newRoot.children.append(oldRoot)
        return newRoot

    def process_bone(self, bone: Bone, path: str) -> None:
        """Get the name, path, relative transform, and bind transform of a joint
        and add its values to the lists of stored values

        Parameters
        ----------
        bone : Bone
            The Makehuman bone to process for Usd
        path : str
            Path to the parent of this bone
        """

        # sanitize the name for USD paths
        name = sanitize(bone.name)
        path += name
        self.joint_paths.append(path)

        # store original name for later joint weighting
        self.joint_names.append(bone.name)

        # Get matrix for joint transform relative to its parent. Move to offset
        # to match mesh transform in scene
        relxform = bone.getRelativeMatrix(offsetVect=self.offset)
        # Transpose the matrix as USD stores transforms in row-major format
        relxform = relxform.transpose()
        # Convert type for USD and store
        relative_transform = Gf.Matrix4d(relxform.tolist())
        self.rel_transforms.append(relative_transform)

        # Get matrix for joint transform at rest in global coordinate space. Move
        # to offset to match mesh transform in scene
        gxform = bone.getRestMatrix(offsetVect=self.offset)
        # Transpose the matrix as USD stores transforms in row-major format
        gxform = gxform.transpose()
        # Convert type for USD and store
        global_transform = Gf.Matrix4d(gxform.tolist())
        self.global_transforms.append(global_transform)

        # Get matrix which represents a joints transform in its binding position
        # for binding to a mesh. Move to offset to match mesh transform.
        bxform = bone.getBindMatrix(offsetVect=self.offset)
        # Convert type for USD and store
        bind_transform = Gf.Matrix4d(bxform.tolist())
        # bind_transform = Gf.Matrix4d().SetIdentity() TODO remove
        self.bind_transforms.append(bind_transform)


class Bone:
    """Bone which constitutes skeletons to be imported using the HumanGenerator
    extension. Has a parent and children, transforms in space, and named joints
    at the head and tail.

    Attributes
    ----------
    name : str
        Human-readable bone name.
    """
    def __init__(self, skel: Skeleton, name: str, parent: str, head: str, tail: str) -> None:
        """Create a Bone instance

        Parameters
        ----------
        skel : Skeleton
            Skeleton to which the bone belongs
        name : str
            Name of the bone
        parent : str
            Name of the parent bone. This is the bone "above" and is one level closer to
            the root of the skeleton
        head : str
            Name of the head joint
        tail : str
            Name of the tail joint
        """
        self._mh_bone = skeleton.Bone(skel, name, parent, head, tail)

        self.name = name
        self.skeleton = skel

        self.headJoint = head
        self.tailJoint = tail

    def getRelativeMatrix(self, offset: List[float] = [0, 0, 0]) -> np.NDArray:
        """_summary_

        Parameters
        ----------
        offset : List[float], optional
            _description_, by default [0, 0, 0]

        Returns
        -------
        np.NDArray
            _description_
        """
        return self._mh_bone.getRelativeMatrix(offset)

    def getRestMatrix(self, offset: List[float] = [0, 0, 0]) -> np.NDArray:
        """_summary_

        Parameters
        ----------
        offset : List[float], optional
            _description_, by default [0, 0, 0]

        Returns
        -------
        np.NDArray
            _description_
        """
        return self._mh_bone.getRestMatrix(offset)

    def getBindMatrix(self, offset: List[float] = [0, 0, 0]) -> np.NDArray:
        """_summary_

        Parameters
        ----------
        offset : List[float], optional
            _description_, by default [0, 0, 0]

        Returns
        -------
        np.NDArray
            _description_
        """
        return self._mh_bone.getBindMatrix(offset)[1]


class Skeleton:
    """Skeleton which can be imported using the HumanGenerator extension. Provides
    root bone(s), which have a tree of children that can be traversed to get the data
    for the entire rig.

    Attributes
    ----------
    name : str
        Name of the skeleton rig, by default "Skeleton"
    roots : list of Bone
        Root bones. Bones which have children that can be traversed to constitute the
        entire skeleton.
    """
    def __init__(self, name="Skeleton") -> None:
        """Create a skeleton instance

        Parameters
        ----------
        name : str, optional
            Name of the skeleton, by default "Skeleton"
        """
        self._mh_skeleton = skeleton.Skeleton(name)
        self.roots = self._mh_skeleton.roots
        self.name = name

    def addBone(self, name: str, parent: str, head: str, tail: str) -> Bone:
        """Add a new bone to the Skeleton

        Parameters
        ----------
        name : str
            Name of the new bone
        parent : str
            Name of the parent bone under which to put the new bone
        head : str
            Name of the joint at the head of the new bone
        tail : str
            Name of the joint at the tail of the new bone

        Returns
        -------
        Bone
            The bone which has been added to the skeleton
        """
        _bone = Bone(self, name, parent, head, tail)
        # HACK Bone() creates a new Bone for _mh_bone by default. How can we
        # avoid doing this twice without revealing it to the user? 
        _bone._mh_bone = self._mh_skeleton.addBone(name, parent, head, tail)
        return _bone