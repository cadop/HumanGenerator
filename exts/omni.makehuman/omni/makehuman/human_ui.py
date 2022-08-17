import omni.ui as ui
from .ui_widgets import *
from .styles import *
from . import mh_usd


class HumanPanel(ui.Frame):
    def __init__(self, mhcaller, **kwargs):
        super().__init__(width=0, **kwargs)
        self.mh_call = mhcaller
        self.set_build_fn(self._build_widget)

    def _build_widget(self):
        human = self.mh_call.human
        with ui.HStack():
            self.panels = (
                ParamPanel(human, width=300),
                ButtonPanel(self.mh_call, width=200),
            )

    def destroy(self):
        super().destroy()
        for panel in self.panels:
            panel.destroy()


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
        macro_model = SliderEntryPanelModel(macro_params)
        race_params = (
            Param("African", human.setAfrican),
            Param("Asian", human.setAsian),
            Param("Caucasian", human.setCaucasian),
        )
        race_model = SliderEntryPanelModel(race_params)

        with ui.ScrollingFrame():
            with ui.CollapsableFrame("Phenotype", style=styles.frame_style, height=0):
                with ui.VStack():
                    self.panels = (
                        SliderEntryPanel("Macrodetails", macro_model),
                        SliderEntryPanel("Race", race_model),
                    )

    def destroy(self):
        super().destroy()
        for panel in self.panels:
            panel.destroy()


class ButtonPanel(ui.Frame):
    def __init__(self, mhcaller, **kwargs):
        super().__init__(**kwargs)
        self.mh_call = mhcaller
        self.set_build_fn(self._build_widget)

    def _build_widget(self):
        with ui.VStack():
            self.drop = DropList((".mhpxy"))
            ui.Button(
                "add_to_scene",
                height=50,
                clicked_fn=lambda: mh_usd.add_to_scene(self.mh_call.objects),
            )
            ui.Button(
                "store_obj", height=50, clicked_fn=lambda: self.mh_call.store_obj()
            )

    def destroy(self):
        super().destroy()
        self.drop.destroy()
