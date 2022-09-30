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


class Skeleton(skeleton.Bone):
    """Skeleton which can be imported using the HumanGenerator extension.

    Attributes
    ----------
    roots : list of Bone
        Root bones. Bones which have children that can be traversed to form the
        entire skeleton.
    """
    def __init__(self) -> None:
        self.roots = []
        pass

    def addBone(name: str, parentName: str, headJoint: str, tailJoint: str) -> Bone:
        pass
