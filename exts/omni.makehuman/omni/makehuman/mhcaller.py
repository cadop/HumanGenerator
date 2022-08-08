import warnings
import io
from makehuman import makehuman

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
import proxy, gui3d, events3d
import numpy as np
import carb


class MHCaller:
    def __init__(self):
        """Setup the needed componenets to use makehuman modules independent of
        the GUI. This includes app globals (G) and the human object."""
        self.G = G
        self.human = None
        self.filepath = None
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
        # except Exception as e: warnings.Warning("MH APP EXISTS") return

    def init_human(self):
        """Initialize the human and set some required files from disk. This
        includes the skeleton and any proxies (hair, clothes, accessories etc.)
        The weights from the base skeleton must be transfered to the chosen
        skeleton or else there will be unweighted verts on the meshes.
        """
        # TODO add means of browsing and loading proxies and skeletons
        self.human = human.Human(files3d.loadMesh(mh.getSysDataPath("3dobjs/base.obj"), maxFaces=5))
        # set the makehuman instance human so that features (eg skeletons) can
        # access it globally
        self.G.app.selectedHuman = self.human
        humanmodifier.loadModifiers(mh.getSysDataPath("modifiers/modeling_modifiers.json"), self.human)
        # Add eyes
        self.add_proxy(
            "C:\\Users\\jhg29\\AppData\\Local\\makehuman-community\\makehuman\\data\\eyes\\high-poly\\high-poly.mhpxy"
        )
        # Add some clothes
        self.add_proxy(
            "C:\\Users\\jhg29\\AppData\\Local\\makehuman-community\\makehuman\\data\\clothes\\male_casualsuit03\\male_casualsuit03.mhpxy"
        )

        base_skel = skeleton.load(
            mh.getSysDataPath("rigs/default.mhskel"),
            self.human.meshData,
        )
        cmu_skel = skeleton.load(
            "C:\\Users\\jhg29\\AppData\\Local\\makehuman-community\\makehuman\\data\\rigs\\cmu_mb.mhskel",
            self.human.meshData,
        )

        # Build joint weights on our chosen skeleton, derived from the base
        # skeleton
        cmu_skel.autoBuildWeightReferences(base_skel)

        self.human.setBaseSkeleton(base_skel)
        # Actually add the skeleton
        self.human.setSkeleton(cmu_skel)
        self.human.applyAllTargets()

    def set_age(self, age):
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
        """Human objects property class for up-to-date sub-objects

        Returns
        -------
        list of: guiCommon.Object
            All 3D objects included in the human. This includes the human
            itself, as well as any proxies
        """
        # Make sure proxies are up-to-date
        self.update()
        return self.human.getObjects()

    def update(self):
        """Propagate changes to meshes and proxies"""
        for obj in self.human.getObjects()[1:]:
            mesh = obj.getSeedMesh()
            pxy = obj.getProxy()
            pxy.update(mesh, False)
            mesh.update()

    def store_obj(self, filepath=None):
        """Write obj file to disk using makehuman's built-in exporter

        Parameters
        ----------
        filepath : str, optional
            Path on disk to which to write the file. If none, uses self.filepath
        """
        if filepath is None:
            filepath = self.filepath

        wavefront.writeObjFile(filepath, self.mesh)

    def add_proxy(self, proxypath):
        """Load a proxy (hair, nails, clothes, etc.) and apply it to the human

        Parameters
        ----------
        proxypath : str
            Path to the proxy file on disk
        """
        #  Derived from work by @tomtom92 at the MH-Community forums
        print(proxypath)
        pxy = proxy.loadProxy(self.human, proxypath, type="Eyes")
        mesh, obj = pxy.loadMeshAndObject(self.human)
        mesh.setPickable(True)
        gui3d.app.addObject(obj)
        mesh2 = obj.getSeedMesh()
        fit_to_posed = True
        pxy.update(mesh2, fit_to_posed)
        mesh2.update()
        obj.setSubdivided(self.human.isSubdivided())
        self.human.setEyesProxy(pxy)
        vertsMask = np.ones(self.human.meshData.getVertexCount(), dtype=bool)
        proxyVertMask = proxy.transferVertexMaskToProxy(vertsMask, pxy)
        # Apply accumulated mask from previous clothes layers on this clothing
        # piece
        obj.changeVertexMask(proxyVertMask)
        # if pxy.deleteVerts is not None and len(pxy.deleteVerts > 0): #
        #     carb.log_info( #     ( #         "Loaded %s deleted verts (%s
        #     faces) from %s proxy.", #
        #     np.count_nonzero(pxy.deleteVerts), #
        #     len(self.human.meshData.getFacesForVertices(np.argwhere(pxy.deleteVerts)[...,
        #     0])), #         pxy.name, #     ) # ) Modify accumulated
        #     (basemesh) verts mask
        verts = np.argwhere(pxy.deleteVerts)[..., 0]
        vertsMask[verts] = False
        self.human.changeVertexMask(vertsMask)
        event = events3d.HumanEvent(self.human, "proxy")
        event.proxy = "eyes"
        self.human.callEvent("onChanged", event)
