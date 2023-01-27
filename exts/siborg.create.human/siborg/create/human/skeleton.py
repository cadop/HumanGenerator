from pxr import Usd, Gf, UsdSkel
from typing import List
import numpy as np
from .shared import sanitize
from .mhcaller import skeleton as mhskel
from .mhcaller import MHCaller


class Bone:
    """Bone which constitutes skeletons to be imported using the HumanGenerator
    extension. Has a parent and children, transforms in space, and named joints
    at the head and tail.

    Attributes
    ----------
    name : str
        Human-readable bone name.
    """

    def __init__(self, skel: 'Skeleton', name: str, parent: str, head: str, tail: str) -> None:
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
        self._mh_bone = mhskel.Bone(skel, name, parent, head, tail)

        self.name = name
        self.skeleton = skel

        self.headJoint = head
        self.tailJoint = tail

    def getRelativeMatrix(self, offset: List[float] = [0, 0, 0]) -> np.ndarray:
        """_summary_

        Parameters
        ----------
        offset : List[float], optional
            Geometric translation to apply, by default [0, 0, 0]

        Returns
        -------
        np.ndarray
            _description_
        """
        return self._mh_bone.getRelativeMatrix(offset)

    def getRestMatrix(self, offset: List[float] = [0, 0, 0]) -> np.ndarray:
        """_summary_

        Parameters
        ----------
        offset : List[float], optional
            Geometric translation to apply, by default [0, 0, 0]

        Returns
        -------
        np.ndarray
            _description_
        """
        return self._mh_bone.getRestMatrix(offset)

    def getBindMatrix(self, offset: List[float] = [0, 0, 0]) -> np.ndarray:
        """_summary_

        Parameters
        ----------
        offset : List[float], optional
            Geometric translation to apply, by default [0, 0, 0]

        Returns
        -------
        np.ndarray
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
    joint_paths : list of: str
        Paths to joints in the stage hierarchy that are used as joint indices
    joint_names : list of: str
        List of joint names in USD (breadth-first traversal) order. It is
        important that joints be ordered this way so that their indices can be
        used for skinning / weighting.
    """

    def __init__(self, name="Skeleton") -> None:
        """Create a skeleton instance

        Parameters
        ----------
        name : str, optional
            Name of the skeleton, by default "Skeleton"
        """

        # Set the skeleton to the makehuman default
        
        _mh_skeleton = MHCaller.human.getSkeleton()
        self._rel_transforms = []
        self._bind_transforms = []

        self.roots = _mh_skeleton.roots
        self.joint_paths = []
        self.joint_names = []

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

    def add_to_stage(self, stage: Usd.Stage, skel_root_path: str, new_root_bone: bool = False):
        """Adds the skeleton to the USD stage

        Parameters
        ----------
        stage : Usd.Stage
            Stage in which to create skeleton prims
        skelroot_path : str
            Path to the human root prim in the stage
        new_root_bone : bool, optional
            Whether or not to prepend a new root at the origin, by default False
        """

        root_bone = self.roots[0]

        if new_root_bone:
            root_bone = self.prepend_root(root_bone)

        self.setup_skeleton(root_bone)

        skeleton_path = skel_root_path + "/Skeleton"

        usdSkel = UsdSkel.Skeleton.Define(stage, skeleton_path)

        # add joints to skeleton by path
        attribute = usdSkel.GetJointsAttr()
        # exclude root
        attribute.Set(self.joint_paths)

        # Add bind transforms to skeleton
        usdSkel.CreateBindTransformsAttr(self._bind_transforms)

        # setup rest transforms in joint-local space
        usdSkel.CreateRestTransformsAttr(self._rel_transforms)

        return usdSkel

    def prepend_root(self, oldRoot: Bone, newroot_name: str = "RootJoint", offset: List[float] = [0, 0, 0]) -> Bone:
        """Adds a new root bone to the head of a skeleton, ahead of the existing root bone.

        Parameters
        ----------
        oldRoot : Bone
            The original MakeHuman root bone
        newroot_name : str, optional
            The name for the new root bone, by default "RootJoint"
        offset : List[float], optional
            Geometric translation to apply, by default [0, 0, 0]

        Returns
        -------
        newRoot : Bone
            The new root bone of the Skeleton
        """
        # make a "super-root" bone, parent to the root, with identity transforms so
        # we can abide by Lina Halper's animation retargeting guidelines:
        # https://docs.omniverse.nvidia.com/prod_extensions/prod_extensions/ext_animation-retargeting.html
        newRoot = self.addBone(
            newroot_name, None, "newRoot_head", oldRoot.tailJoint)
        oldRoot.parent = newRoot
        newRoot.headPos -= offset
        newRoot.build()
        newRoot.children.append(oldRoot)
        return newRoot

    def _process_bone(self, bone: Bone, path: str, offset: List[float] = [0, 0, 0]) -> None:
        """Get the name, path, relative transform, and bind transform of a joint
        and add its values to the lists of stored values

        Parameters
        ----------
        bone : Bone
            The bone to process for Usd
        path : str
            Path to the parent of this bone
        offset : List[float], optional
            Geometric translation to apply, by default [0, 0, 0]
        """

        # sanitize the name for USD paths
        name = sanitize(bone.name)
        path += name
        self.joint_paths.append(path)

        # store original name for later joint weighting
        self.joint_names.append(bone.name)

        # Get matrix for joint transform relative to its parent. Move to offset
        # to match mesh transform in scene
        relxform = bone.getRelativeMatrix(offsetVect=offset)
        # Transpose the matrix as USD stores transforms in row-major format
        relxform = relxform.transpose()
        # Convert type for USD and store
        relative_transform = Gf.Matrix4d(relxform.tolist())
        self._rel_transforms.append(relative_transform)

        # Get matrix which represents a joints transform in its binding position
        # for binding to a mesh. Move to offset to match mesh transform.
        # getBindMatrix() returns a tuple of the bind matrix and the bindinv
        # matrix. Since omniverse uses row-major format, we can just use the
        # already transposed bind matrix.
        bxform = bone.getBindMatrix(offsetVect=offset)
        # Convert type for USD and store
        bind_transform = Gf.Matrix4d(bxform[1].tolist())
        # bind_transform = Gf.Matrix4d().SetIdentity() TODO remove
        self._bind_transforms.append(bind_transform)

    def setup_skeleton(self, bone: Bone, offset: List[float] = [0, 0, 0]) -> None:
        """Traverse the imported skeleton and get the data for each bone for
        adding to the stage

        Parameters
        ----------
        bone : Bone
            The root bone at which to start traversing the imported skeleton.
        offset : List[float], optional
            Geometric translation to apply, by default [0, 0, 0]
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
        self._process_bone(bone, "")

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

                    self._process_bone(neighbor, path, offset)

    def update_in_scene(self, stage: Usd.Stage, skel_root_path: str):
        """Resets the skeleton values in the stage, updates the skeleton from makehuman.
        
        Parameters
        ----------
        stage : Usd.Stage
            The stage in which to update the skeleton
        skel_root_path : str
            The path to the skeleton root in the stage
        """
        # Get the skeleton from makehuman
        _mh_skeleton = MHCaller.human.getSkeleton()

        # Clear out any existing data
        self._rel_transforms = []
        self._bind_transforms = []
        self.joint_paths = []
        self.joint_names = []

        # Get the root bone(s) of the skeleton
        self.roots = _mh_skeleton.roots
