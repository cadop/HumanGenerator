import omni.ui as ui
from . import ui_widgets
from . import mhcaller
from .ui_widgets import Param
from . import styles
from . import mh_usd


class MHWindow(ui.Window):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Create instance of manager class
        self.mh_call = mhcaller.MHCaller()
        self.mh_call.filepath = "D:/human.obj"

        human = self.mh_call.human
        macro_params = (
            Param("Gender", human.setGender),
            Param("Age", human.setAge),
            Param("Muscle", human.setMuscle),
            Param("Weight", human.setWeight),
            Param("Height", human.setHeight),
            Param("Proportions", human.setBodyProportions),
        )
        race_params = (
            Param("African", human.setAfrican),
            Param("Asian", human.setAsian),
            Param("Caucasian", human.setCaucasian),
        )

        with self.frame:
            with ui.ScrollingFrame():
                with ui.VStack():
                    with ui.CollapsableFrame("Phenotype", style=styles.frame_style, height=0):
                        with ui.VStack():
                            ui_widgets.Panel("Macrodetails", macro_params)
                            ui_widgets.Panel("Race", race_params)
                    with ui.HStack():
                        ui.Button("add_to_scene", clicked_fn=lambda: mh_usd.add_to_scene(human.meshes))
                        ui.Button("store_obj", clicked_fn=lambda: self.mh_call.store_obj()),
