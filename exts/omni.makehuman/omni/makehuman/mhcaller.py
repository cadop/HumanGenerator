import warnings
import io
from makehuman import makehuman

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
        self.G = G
        self.human = None
        self.filepath = None
        self._config_mhapp()
        self.init_human()

    def _config_mhapp(self):
        try:
            self.G.app = MHApplication()
        except:
            return
        # except Exception as e: warnings.Warning("MH APP EXISTS") return

    def init_human(self):
        self.human = human.Human(files3d.loadMesh(mh.getSysDataPath("3dobjs/base.obj"), maxFaces=5))
        # set the makehuman instance human so that features (eg skeletons) can
        # access it globally
        self.G.app.selectedHuman = self.human
        humanmodifier.loadModifiers(mh.getSysDataPath("modifiers/modeling_modifiers.json"), self.human)
        self.add_proxy(
            "C:\\Users\\jhg29\\AppData\\Local\\makehuman-community\\makehuman\\data\\eyes\\low-poly\\low-poly.mhpxy"
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
        if not (age > 1 and age < 89):
            return
        self.human.setAgeYears(age)
        # exportObj(f"D:/human_{age}.obj",self.human)

        # G.app.loadHuman() G.app.loadScene() G.app.loadMainGui()
        # G.app.loadPlugin("mhapi","C:\\Users\\jhg29\\Documents\\GitHub\\mh\\src\\makehuman\\plugins\\1_mhapi\\__init__.py")
        # G.app.mhapi.exports.exportAsOBJ("D:/human.obj")

    @property
    def objects(self):
        # Make sure proxies are up-to-date
        self.update()
        return self.human.getObjects()

    def update(self):
        for obj in self.human.getObjects()[1:]:
            mesh = obj.getSeedMesh()
            pxy = obj.getProxy()
            pxy.update(mesh, False)
            mesh.update()

    def store_obj(self, filepath=None):

        if filepath is None:
            filepath = self.filepath

        wavefront.writeObjFile(filepath, self.mesh)

    def add_proxy(self, proxypath):
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
