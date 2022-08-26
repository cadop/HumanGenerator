

class MHOV:
    ''' Make human for omniverse manager class
    
    This is where we store data for every human, which can be referenced later as needed
    
    '''

    def __init__(self) -> None:
        self.root_human = None

        self.usdSkel = None
        self.joint_names = None
        self.joint_paths = None 
        self.skel_root_path = None