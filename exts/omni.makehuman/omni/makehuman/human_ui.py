import omni.ui as ui
from .ui_widgets import *
from .styles import *


class HumanPanel(ui.Frame):
    def __init__(self, mhcaller, **kwargs):
        super().__init__(width=0, **kwargs)
        self.mh_call = mhcaller
        self.set_build_fn(self._build_widget)

    def _build_widget(self):
        human = self.mh_call.human
        with ui.HStack():
            ParamPanel(human, width=300)
            ButtonPanel(human, width=200)


class ParamPanel(ui.Frame):
    def __init__(self, human, **kwargs):
        super().__init__(**kwargs)
        self.human = human
        self.set_build_fn(self._build_widget)

    def _build_widget(self):
        human = self.human
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

        with ui.ScrollingFrame():
            with ui.CollapsableFrame(
                "Phenotype", style=styles.frame_style, height=0
            ):
                with ui.VStack():
                    SliderEntryPanel("Macrodetails", macro_params)
                    SliderEntryPanel("Race", race_params)


class ButtonPanel(ui.Frame):
    def __init__(self, mhcaller, **kwargs):
        super().__init__(**kwargs)
        self.mh_call = mhcaller
        self.set_build_fn(self._build_widget)

    def _build_widget(self):
        with ui.ScrollingFrame():
            with ui.VStack():
                ui.Button(
                    "add_to_scene",
                    clicked_fn=lambda: mh_usd.add_to_scene(
                        self.mh_call.objects
                    ),
                )
                ui.Button(
                    "store_obj", clicked_fn=lambda: self.mh_call.store_obj()
                )
