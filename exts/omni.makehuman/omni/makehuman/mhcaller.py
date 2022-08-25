from typing import TypeVar, Union
import warnings
import io
import makehuman
from pathlib import Path

# Makehuman loads most modules by manipulating the system path, so we have to
# run this before we can run the rest of our makehuman imports

makehuman.set_sys_path()

import human
import files3d
import mh
from core import G
from mhmain import MHApplication
from shared import wavefront
import humanmodifier, skeleton
import proxy, gui3d, events3d, targets
from getpath import findFile
import numpy as np
import carb
from .shared import data_path


class MHCaller:
    """A wrapper around the Makehuman app. Lets us use Makehuman functions without
    launching the whole application. Also holds all data about the state of our Human
    and available modifiers/assets.

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
        self.add_proxy(data_path("eyes/high-poly/high-poly.mhpxy"), "eyes")
        self.human.applyAllTargets()

    def init_human(self):
        """Initialize the human and set some required files from disk. This
        includes the skeleton and any proxies (hair, clothes, accessories etc.)
        The weights from the base skeleton must be transfered to the chosen
        skeleton or else there will be unweighted verts on the meshes.
        """
        self.human = human.Human(files3d.loadMesh(mh.getSysDataPath("3dobjs/base.obj"), maxFaces=5))
        # set the makehuman instance human so that features (eg skeletons) can
        # access it globally
        self.G.app.selectedHuman = self.human
        humanmodifier.loadModifiers(mh.getSysDataPath("modifiers/modeling_modifiers.json"), self.human)
        # Add eyes
        self.add_proxy(data_path("eyes/high-poly/high-poly.mhpxy"), "eyes")
        self.base_skel = skeleton.load(
            mh.getSysDataPath("rigs/default.mhskel"),
            self.human.meshData,
        )
        cmu_skel = skeleton.load(data_path("rigs/cmu_mb.mhskel"), self.human.meshData)
        # Build joint weights on our chosen skeleton, derived from the base
        # skeleton
        cmu_skel.autoBuildWeightReferences(self.base_skel)

        self.human.setBaseSkeleton(self.base_skel)
        # Actually add the skeleton
        self.human.setSkeleton(cmu_skel)
        self.human.applyAllTargets()

    def set_age(self, age : float):
        """Set human age, safety checking that it's within an acceptable range

        Parameters
        ----------
        age : float
            Desired age in years
        """
        if not (age > 1 and age < 89):
            return
        self.human.setAgeYears(age)

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
    def meshes(self):
        """All of the meshes of all of the objects attached to a human. This
        includes the mesh of the human itself as well as the meshes of all proxies
        (clothing, hair, musculature, eyes, etc.)"""
        return [o.mesh for o in self.objects]

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

    # TODO remove this function. We can convert from USD if we want to export
    def store_obj(self, filepath=None):
        """Write obj file to disk using makehuman's built-in exporter

        Parameters
        ----------
        filepath : str, optional
            Path on disk to which to write the file. If none, uses self.filepath
        """
        if filepath is None:
            filepath = self.filepath

        wavefront.writeObjFile(filepath, self.meshes)

    def add_proxy(self, proxypath : str, proxy_type  : str = None):
        """Load a proxy (hair, nails, clothes, etc.) and apply it to the human

        Parameters
        ----------
        proxypath : str
            Path to the proxy file on disk
        proxy_type: str, optional
            Proxy type, None by default
            Can be automatically determined using path names, but otherwise
            must be defined (this is a limitation of how makehuman handles
            proxies)
        """
        #  Derived from work by @tomtom92 at the MH-Community forums
        #  See: http://www.makehumancommunity.org/forum/viewtopic.php?f=9&t=17182&sid=7c2e6843275d8c6c6e70288bc0a27ae9
        # Load the proxy
        pxy = proxy.loadProxy(self.human, proxypath, type=proxy_type)
        # Get the mesh and Object3D object from the proxy applied to the human
        mesh, obj = pxy.loadMeshAndObject(self.human)
        # TODO is this next line needed?
        mesh.setPickable(True)
        # TODO Can this next line be deleted? The app isn't running
        gui3d.app.addObject(obj)

        # Fit the proxy mesh to the human
        mesh2 = obj.getSeedMesh()
        fit_to_posed = True
        pxy.update(mesh2, fit_to_posed)
        mesh2.update()

        # Set the object to be subdivided if the human is subdivided
        # TODO is this needed?
        obj.setSubdivided(self.human.isSubdivided())

        # Get proxy type if none is given
        if proxy_type is None:
            proxy_type = self.guess_proxy_type(proxypath)

        # Set/add proxy based on type
        if proxy_type == "eyes":
            self.human.setEyesProxy(pxy)
        elif proxy_type == "clothes":
            self.human.addClothesProxy(pxy)
        elif proxy_type == "eyebrows":
            self.human.setEyebrowsProxy(pxy)
        elif proxy_type == "eyelashes":
            self.human.setEyelashesProxy(pxy)
        elif proxy_type == "hair":
            self.human.setHairProxy(pxy)
        else:
            # Body proxies (musculature, etc)
            self.human.setProxy(pxy)

        vertsMask = np.ones(self.human.meshData.getVertexCount(), dtype=bool)
        proxyVertMask = proxy.transferVertexMaskToProxy(vertsMask, pxy)
        # Apply accumulated mask from previous layers on this proxy
        obj.changeVertexMask(proxyVertMask)

        # Delete masked vertices
        # TODO add toggle for this feature in UI
        # verts = np.argwhere(pxy.deleteVerts)[..., 0]
        # vertsMask[verts] = False
        # self.human.changeVertexMask(vertsMask)

    Proxy = TypeVar("Proxy")

    def remove_proxy(self, proxy: Proxy):
        """Removes a proxy from the human. Executes a particular method for removal
        based on proxy type.

        Parameters
        ----------
        proxy : proxy.Proxy
            The Makehuman proxy to remove from the human
        """
        proxy_type = proxy.type.lower()
        # Use MakeHuman internal methods to remove proxy based on type
        if proxy_type == "eyes":
            self.human.setEyesProxy(None)
        elif proxy_type == "clothes":
            self.human.removeClothesProxy(proxy.uuid)
        elif proxy_type == "eyebrows":
            self.human.setEyebrowsProxy(None)
        elif proxy_type == "eyelashes":
            self.human.setEyelashesProxy(None)
        elif proxy_type == "hair":
            self.human.setHairProxy(None)
        else:
            # Body proxies (musculature, etc)
            self.human.setProxy(None)

    Skeleton = TypeVar("Skeleton")

    def remove_item(self, item : Union[Skeleton, Proxy]):
        """Removes a Makehuman asset from the human. Assets include Skeletons
        as well as proxies. Determines removal method based on asset object type.

        Parameters
        ----------
        item : Union[Skeleton,Proxy]
            Makehuman skeleton or proxy to remove from the human
        """
        # TODO handle removing skeletons
        if isinstance(item, proxy.Proxy):
            self.remove_proxy(item)
        else:
            return

    def add_item(self, path : str):
        """Add a Makehuman asset (skeleton or proxy) to the human.

        Parameters
        ----------
        path : str
            Path to the asset on disk
        """
        if "mhpxy" in path:
            self.add_proxy(path)
        elif "mhskel" in path:
            self.set_skel(path)

    def set_skel(self, path : str):
        """Change the skeleton applied to the human. Loads a skeleton from disk.
        The skeleton position can be used to drive the human position in the scene.

        Parameters
        ----------
        path : str
            The path to the skeleton to load from disk
        """
        # Load skeleton from path
        skel = skeleton.load(path, self.human.meshData)
        # Build skeleton weights based on base skeleton
        skel.autoBuildWeightReferences(self.base_skel)
        # Set the skeleton and update the human
        self.human.setSkeleton(skel)
        self.human.applyAllTargets()

    def guess_proxy_type(self, path : str):
        """Guesses a proxy's type based on the path from which it is loaded.

        Parameters
        ----------
        path : str
            The path to the proxy on disk

        Returns
        -------
        Union[str,None]
            The proxy type, or none if the type could not be determined
        """
        proxy_types = ("eyes", "clothes", "eyebrows", "eyelashes", "hair")
        for type in proxy_types:
            if type in path:
                return type
        return None

def modifier_image(name : str):
    """Guess the path to a modifier's corresponding image on disk based on the name
    of the modifier. Useful for building UI for list of modifiers.

    Parameters
    ----------
    name : str
        Name of the modifier

    Returns
    -------
    str
        The path to the image on disk
    """
    if name is None:
        # If no modifier name is provided, we can't guess the file name
        return None
    name = name.lower()
    # Return the modifier path based on the modifier name
    # TODO determine if images can be loaded from the Makehuman module stored in
    # site-packages so we don't have to include the data twice
    return str(Path(__file__).parents[2]) + "/" + targets.getTargets().images.get(name, name)
