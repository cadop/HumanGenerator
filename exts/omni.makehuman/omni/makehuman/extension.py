import omni.ext
from . import mh_ui
from .mh_ui import Param
import omni.ui as ui
from omni.makehuman import mhcaller
import omni
import carb
from . import mh_usd
from . import styles

# from . import assetconverter

# Any class derived from `omni.ext.IExt` in top level module (defined in `python.modules` of `extension.toml`) will be
# instantiated when extension gets enabled and `on_startup(ext_id)` will be called. Later when extension gets disabled
# on_shutdown() is called.


class MakeHumanExtension(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.

    def on_startup(self, ext_id):
        print("[omni.makehuman] MakeHumanExtension startup")

        # Create instance of manager class
        mh_call = mhcaller.MHCaller()
        mh_call.filepath = "D:/human.obj"
        primpath = "/World/human"

        self.human = mh_call.human
        macro_params = (
            Param("Gender", self.human.setGender),
            Param("Age", self.human.setAge),
            Param("Muscle", self.human.setMuscle),
            Param("Weight", self.human.setWeight),
            Param("Height", self.human.setHeight),
            Param("Proportions", self.human.setBodyProportions),
        )
        race_params = (
            Param("African", self.human.setAfrican),
            Param("Asian", self.human.setAsian),
            Param("Caucasian", self.human.setCaucasian),
        )

        self._window = ui.Window("MakeHuman", width=300, height=300)
        with self._window.frame:
            with ui.ScrollingFrame():
                with ui.VStack():
                    with ui.CollapsableFrame("Phenotype", style=styles.frame_style, height=0):
                        with ui.VStack():
                            mh_ui.Panel("Macrodetails", macro_params)
                            mh_ui.Panel("Race", race_params)
                    with ui.HStack():
                        ui.Button("add_to_scene", clicked_fn=lambda: self.add_to_scene())
                        ui.Button("store_obj", clicked_fn=lambda: mh_call.store_obj()),

    def on_shutdown(self):
        print("[omni.makehuman] makehuman shutdown")

    def add_to_scene(self):
        objects = self.human.getObjects(excludeZeroFaceObjs=True)
        meshes = [o.mesh for o in objects]
        mh_usd.add_to_scene(meshes)
