import makehuman

# Makehuman loads most modules by manipulating the system path, so we have to
# run this before we can run the rest of our makehuman imports

makehuman.set_sys_path()

import human
import files3d
import mh
from core import G
from mhmain import MHApplication
import humanmodifier, skeleton
import proxy, gui3d, events3d, targets
from getpath import findFile


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
    """

    def __new__(cls):
        """Singleton pattern. Only one instance of MHApp can exist at a time."""
        if not hasattr(cls, 'instance'):
            cls.instance = super(MHApp, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        """Constructs an instance of MHCaller. This involves setting up the
        needed components to use makehuman modules independent of the GUI.
        This includes app globals (G) and the human object."""
        self.G = G
        self.human = None
        self._config_mhapp()
        self.init_human()

    def _config_mhapp(self):
        """Declare and initialize the makehuman app, and move along if we
        encounter any errors (omniverse sometimes fails to purge the app
        singleton on extension reload, which can throw an error. This just means
        the app already exists)
        """
        try:
            self.G.app = MHApplication()
        except:
            return

    def init_human(self):
        """Initialize the human and set some required files from disk. This
        includes the skeleton and any proxies (hair, clothes, accessories etc.)
        The weights from the base skeleton must be transfered to the chosen
        skeleton or else there will be unweighted verts on the meshes.
        """
        self.human = human.Human(files3d.loadMesh(
            mh.getSysDataPath("3dobjs/base.obj"), maxFaces=5))
        # set the makehuman instance human so that features (eg skeletons) can
        # access it globally
        self.G.app.selectedHuman = self.human
        humanmodifier.loadModifiers(mh.getSysDataPath(
            "modifiers/modeling_modifiers.json"), self.human)
        # Add eyes
        # self.add_proxy(data_path("eyes/high-poly/high-poly.mhpxy"), "eyes")
        self.base_skel = skeleton.load(
            mh.getSysDataPath("rigs/default.mhskel"),
            self.human.meshData,
        )
        # cmu_skel = skeleton.load(data_path("rigs/cmu_mb.mhskel"), self.human.meshData)
        # Build joint weights on our chosen skeleton, derived from the base
        # skeleton
        # cmu_skel.autoBuildWeightReferences(self.base_skel)

        self.human.setBaseSkeleton(self.base_skel)
        # Actually add the skeleton
        # self.human.setSkeleton(self.base_skel)
        self.human.applyAllTargets()

    def reset_human(self):
        """Resets the human object to its initial state. This involves setting the
        human's name to its default, resetting all modifications, and resetting all
        proxies. Does not reset the skeleton. Also flags the human as having been
        reset so that the new name can be created when adding to the Usd stage.
        """
        self.is_reset = True
        self.name = self.default_name
        self.human.resetMeshValues()
        # Restore eyes
        # self.add_proxy(data_path("eyes/high-poly/high-poly.mhpxy"), "eyes")
        # Remove skeleton
        self.human.skeleton = None
        # HACK Set the age to itself to force an update of targets
        self.human.setAge(self.human.getAge())

    @property
    def objects(self):
        """List of objects attached to the human.

        Returns
        -------
        list of: guiCommon.Object
            All 3D objects included in the human. This includes the human
            itself, as well as any proxies
        """
        # Make sure proxies are up-to-date
        self.update()
        return self.human.getObjects()

    @property
    def properties(self):
        """List of properties attached to the human.

        Returns
        -------
        list of: humanmodifier.Modifier
            All properties included in the human. This includes any modifiers and their values
            as well as any proxies.
        """
        return [m for m in self.modifiers if m.getValue() or m.isMacro()]

    def update(self):
        """Propagate changes to meshes and proxies"""
        # For every mesh object except for the human (first object), update the
        # mesh and corresponding proxy
        # See https://github.com/makehumancommunity/makehuman/search?q=adaptproxytohuman
        for obj in self.human.getObjects()[1:]:
            mesh = obj.getSeedMesh()
            pxy = obj.getProxy()
            # Update the proxy
            pxy.update(mesh, False)
            # Update the mesh
            mesh.update()
