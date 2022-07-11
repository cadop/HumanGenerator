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
import humanmodifier


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
        # except Exception as e:
        #     warnings.Warning("MH APP EXISTS")
        #     return

    def init_human(self):
        self.human = human.Human(files3d.loadMesh(mh.getSysDataPath("3dobjs/base.obj"), maxFaces=5))
        humanmodifier.loadModifiers("data/modifiers/modeling_modifiers.json", self.human)
        self.G.app.selectedHuman = self.human

    def set_age(self, age):
        if not (age > 1 and age < 89):
            return
        self.human.setAgeYears(age)
        # exportObj(f"D:/human_{age}.obj",self.human)

        # G.app.loadHuman()
        # G.app.loadScene()
        # G.app.loadMainGui()
        # G.app.loadPlugin("mhapi","C:\\Users\\jhg29\\Documents\\GitHub\\mh\\src\\makehuman\\plugins\\1_mhapi\\__init__.py")
        # G.app.mhapi.exports.exportAsOBJ("D:/human.obj")

    @property
    def mesh(self):
        objects = self.human.getObjects()
        meshes = [o.mesh for o in objects]

        # if config.hiddenGeom:
        #     # Disable the face masking on copies of the input meshes
        #     meshes = [m.clone(filterMaskedVerts=False) for m in meshes]
        #     for m in meshes:
        #         # Would be faster if we could tell clone() to do this, but it would
        #         # make the interface more complex.
        #         # We could also let the wavefront module do this, but this would
        #         # introduce unwanted "magic" behaviour into the export function.
        #         face_mask = np.ones(m.face_mask.shape, dtype=bool)
        #         m.changeFaceMask(face_mask)
        #         m.calcNormals()
        #         m.updateIndexBuffer()
        return meshes

    def store_obj(self, filepath=None):
        """store object on disk

        Parameters
        ----------
        filepath : str
            _description_
        mesh : makehuman.mesh
            _description_
        """

        if filepath is None:
            filepath = self.filepath

        wavefront.writeObjFile(filepath, self.mesh)
