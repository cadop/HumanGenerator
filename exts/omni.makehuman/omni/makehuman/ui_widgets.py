import carb
import omni.ui as ui
import omni
from typing import Tuple
from dataclasses import dataclass
import carb
from . import styles, mh_usd, ui_widgets


class SliderEntry:
    def __init__(
        self,
        label: str,
        fn: object,
        step=0.01,
        min=None,
        max=None,
        default=0,
    ):
        """Custom UI element that encapsulates a labeled slider and field

        Parameters
        ----------
        label : str
            Widget label
        fn : object
            Function to trigger when value is changed
        step : float, optional
            Division between values, by default 0.01
        min : float, optional
            Minimum value, by default None
        max : float, optional
            Maximum value, by default None
        default : float, optional
            Default parameter value, by default 0
        """
        self.label = label
        self.fn = fn
        self.step = step
        self.min = min
        self.max = max
        self.default = default
        self._build_widget()

    def _build_widget(self):
        """Construct the UI elements"""
        with ui.HStack(
            width=ui.Percent(100), height=0, style=styles.sliderentry_style
        ):
            ui.Label(
                self.label,
                height=15,
                alignment=ui.Alignment.RIGHT,
                name="label_param",
            )
            self.drag = ui.FloatDrag(step=self.step)
            if self.min is not None:
                self.drag.min = self.min
            if self.max is not None:
                self.drag.max = self.max
            self.drag.model.set_value(self.default)
            self.drag.model.add_end_edit_fn(lambda m: self._sanitize_and_run())

    def _sanitize_and_run(self):
        """Make sure that values are within an acceptable range and then run the
        assigned function"""
        m = self.drag.model
        getval = m.get_value_as_float
        if getval() < self.min:
            m.set_value(self.min)
        if getval() > self.max:
            m.set_value(self.max)
        self.fn(m.get_value_as_float())


@dataclass
class Param:
    """Dataclass to store SliderEntry parameters"""

    name: str
    fn: object
    min: float = 0
    max: float = 1
    default: float = 0.5


class Panel:
    def __init__(self, label: str, params: Param):
        """A UI widget providing a labeled group of parameters

        Parameters
        ----------
        label : str
            Display title for the group
        params : list of Param
            List of Param data objects to populate the panel
        """
        self.label = label
        self.params = params
        self._build_widget()

    def _build_widget(self):
        """Construct the UI elements"""
        with ui.ZStack(style=styles.panel_style, height=0):
            ui.Rectangle(name="group_rect")
            with ui.VStack(name="contents"):
                ui.Label(self.label, height=0)
                for p in self.params:
                    SliderEntry(
                        p.name, p.fn, min=p.min, max=p.max, default=p.default
                    )


class HumanPanel(ui.Frame):
    def __init__(self, mhcaller):
        self.mh_call = mhcaller
        super().__init__(width=300)
        self.set_build_fn(self._build_widget)

    def _build_widget(self):
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

        with ui.ScrollingFrame():
            with ui.VStack():
                with ui.CollapsableFrame(
                    "Phenotype", style=styles.frame_style, height=0
                ):
                    with ui.VStack():
                        ui_widgets.Panel("Macrodetails", macro_params)
                        ui_widgets.Panel("Race", race_params)
                with ui.HStack():
                    ui.Button(
                        "add_to_scene",
                        clicked_fn=lambda: mh_usd.add_to_scene(
                            self.mh_call.objects
                        ),
                    )
                    ui.Button(
                        "store_obj",
                        clicked_fn=lambda: self.mh_call.store_obj(),
                    ),
