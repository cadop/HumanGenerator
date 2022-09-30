import numpy as np
from typing import List, Tuple
import makehuman

# Makehuman loads most modules by manipulating the system path, so we have to
# run this before we can run the rest of our makehuman imports
makehuman.set_sys_path()
# skeleton (imported from MakeHuman via path) provides Bone and Skeleton classes
import skeleton


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
        _bone._mh_bone = self._mh_skeleton.addBone(name, parent, head, tail)
        return _bone
