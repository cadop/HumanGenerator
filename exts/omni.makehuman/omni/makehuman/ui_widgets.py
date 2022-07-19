import carb
import omni.ui as ui
import omni
from typing import Tuple
from dataclasses import dataclass
import carb
from . import styles


class SliderEntry:
    def __init__(self, label: str, fn: object, step=0.01, min=None, max=None, default=None, style=None):
        self.label = label
        self.fn = fn
        self.step = step
        self.min = min
        self.max = max
        self.default = default
        self.style = style
        self._build_widget()

    def _build_widget(self):
        with ui.HStack(width=ui.Percent(100), height=0, style=styles.sliderentry_style):
            ui.Label(self.label, height=15, alignment=ui.Alignment.RIGHT, name="label_param")
            # self.model = ui.SimpleFloatModel()
            self.drag = ui.FloatDrag(step=self.step)
            if self.min is not None:
                self.drag.min = self.min
            if self.max is not None:
                self.drag.max = self.max
            self.drag.model.set_value(self.default)
            self.drag.model.add_end_edit_fn(lambda m: self._sanitize_and_run(m))

    def _sanitize_and_run(self, m: ui.SimpleFloatModel):
        getval = m.get_value_as_float
        if getval() < self.min:
            m.set_value(self.min)
        if getval() > self.max:
            m.set_value(self.max)
        self.fn(m.get_value_as_float())


@dataclass
class Param:
    name: str
    fn: object
    min: float = 0
    max: float = 1
    default: float = 0.5


class Panel:
    def __init__(self, label: str, params):
        self.label = label
        self.params = params
        self._build_widget()

    def _build_widget(self):
        with ui.ZStack(style=styles.panel_style, height=0):
            ui.Rectangle(name="group_rect")
            with ui.VStack(name="contents"):
                ui.Label(self.label, height=0)
                for p in self.params:
                    SliderEntry(p.name, p.fn, min=p.min, max=p.max, default=p.default)