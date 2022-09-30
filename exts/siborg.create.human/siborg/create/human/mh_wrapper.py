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
    def __init__(self, skel, name, parentName, headJoint, tailJoint) -> None:

        self._mh_bone = skeleton.Bone(skel, name, parentName, headJoint, tailJoint)

        self.name = name
        self.skeleton = skel

        self.headJoint = headJoint
        self.tailJoint = tailJoint

    def getRelativeMatrix(self, offset: List[float] = [0, 0, 0]) -> np.NDArray:
        return self._mh_bone.getRelativeMatrix(offset)

    def getRestMatrix(self, offset: List[float] = [0, 0, 0]) -> np.NDArray:
        return self._mh_bone.getRestMatrix(offset)

    def getBindMatrix(self, offset: List[float] = [0, 0, 0]) -> np.NDArray:
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
        self._mh_skeleton = skeleton.Skeleton(name)
        self.roots = self._mh_skeleton.roots
        self.name = name

    def addBone(self, name: str, parent: str, head: str, tail: str) -> Bone:
        self._mh_skeleton.addBone(name, parent, head, tail)