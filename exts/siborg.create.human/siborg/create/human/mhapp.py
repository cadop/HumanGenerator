class MHApp(object):
    """A singleton wrapper around the Makehuman app. Lets us use Makehuman functions without
    launching the whole application. Also holds all data about the state of our Human
    and available modifiers/assets, and allows us to create new humans without creating a new
    instance of MHApp.

    Attributes
    ----------
    G : Globals
        Makehuman global object. Stores globals needed by Makehuman internally
    human : Human
        Makehuman Human object. Encapsulates all human data (parameters, available)
        modifiers, skeletons, meshes, assets, etc) and functions.
    filepath : str
        Path on disk to which to write an OBJ directly from the Makehuman app. Does
        not include any changes made inside of Omniverse (outside of those made in
        the Makehuman extension).
    default_name : str
        The default human name to reset back to. All subsequent human names append
        the first available number to the default name, ie: human, human_01, human_02,
        etc.
    name : str
        The name of the current human. Used to update the prims of a human in the
        USD stage without making a new human
    is_reset : bool
        A flag to indicate the human has been reset. Used for creating a new human
        in the scene with default values, or resetting the values of the active
        human. Indicates that the new human needs a new name.
    """
    def __init__(self):
        """Constructs an instance of MHCaller. This involves setting up the
        needed components to use makehuman modules independent of the GUI.
        This includes app globals (G) and the human object."""
        self.G = G
        self.human = None
        self.filepath = None
        # default name
        self.default_name = "human"
        self.name = self.default_name
        self.is_reset = False
        self._config_mhapp()
        self.init_human()


    def __new__(cls):
        if not hasattr(cls, 'instance'):
        cls.instance = super(MHApp, cls).__new__(cls)
        return cls.instance