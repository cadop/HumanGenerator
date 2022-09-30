import numpy as np
from typing import List, Tuple


class Bone:
    """Template for skeletons which can be imported using the HumanGenerator extension.
    A class which provides compatible data and and methods can be used wherever
    this type is specified. This class does not contain any data or functionality.

    Attributes
    ----------
    name : str
        Human-readable bone name.
    """
    def __init__(self) -> None:
        self.name = ""
        pass

    def getRelativeMatrix(self, offsetVect: List[float] = [0, 0, 0]) -> np.NDArray:
        pass

    def getRestMatrix(self, offsetVect: List[float] = [0, 0, 0]) -> np.NDArray:
        pass

    def getBindMatrix(self, offsetVect: List[float] = [0, 0, 0]) -> Tuple[np.NDArray, np.NDArray]:
        pass


class Skeleton:
    """Template for skeletons which can be imported using the HumanGenerator extension.
    A class which provides compatible data and and methods can be used wherever
    this type is specified. This class does not contain any data or functionality.

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
