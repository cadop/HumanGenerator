import omni.ext
from . import mh_ui
from .mh_ui import Param
import omni.ui as ui
from omni.makehuman import mhcaller
import omni
import carb
from . import mh_usd

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

        human = mh_call.human
        macro_params = (
            Param("Gender", human.setGender),
            Param("Age", human.setAge),
            Param("African", human.setAfrican),
            Param("Asian", human.setAsian),
            Param("Caucasian", human.setCaucasian),
        )

        # body_params = (
        #     Param("Muscle", human.setMuscle),
        #     Param("Weight", human.setWeight),
        #     Param("Height", human.setHeight),
        #     Param("Proportions", human.setBodyProportions),
        # )

        self._window = ui.Window("MakeHuman", width=300, height=300)
        with self._window.frame:
            with ui.VStack():
                with ui.CollapsableFrame("Phenotype"):
                    mh_ui.Panel("Macrodetails", macro_params)
                with ui.HStack():
                    ui.Button(
                        "add_to_scene",
                        clicked_fn=lambda: mh_usd.add_to_scene(human.mesh),
                    )
                    ui.Button("Save Human", clicked_fn=lambda: mh_call.store_obj())

    def on_shutdown(self):
        print("[omni.makehuman] makehuman shutdown")

    # def add_to_scene(self, input_obj, primpath):

    #     usd_context = omni.usd.get_context()

    #     omni.kit.commands.execute(
    #         "CreateReferenceCommand",
    #         usd_context=usd_context,
    #         path_to=primpath,
    #         asset_path=input_obj,
    #         instanceable=True,
    #     )
