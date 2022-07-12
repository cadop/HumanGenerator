import omni.ui as ui
from . import mhcaller
import omni


class SliderEntry:
    def __init__(self, mh_call: mhcaller, label: str, fn, step=0.01, min=None, max=None):
        self.mh_call = mh_call
        self.label = label
        self.fn = fn
        self.step = step
        self.min = min
        self.max = max
        self._build_widget()

    def _build_widget(self):
        with ui.HStack(width=ui.Percent(100), height=0):
            ui.Label(self.label, height=15)

            self.model = ui.SimpleFloatModel()

            self.drag = ui.FloatDrag(
                min=self.min,
                max=self.max,
                step=self.step,
                width=ui.Percent(50),
            )
            self.drag.model.add_value_changed_fn(lambda m: self._sanitize_and_run(m))

    def _sanitize_and_run(self, m: ui.AbstractValueModel):
        getval = m.get_value_as_float
        if getval() < self.min:
            m.set_value(self.min)
        if getval() > self.max:
            m.set_value(self.max)
        self.fn(m.get_value_as_float())


class Macrodetails:
    def __init__(self) -> None:
        pass


class Breastshape:
    def __init__(self) -> None:
        pass


class Race:
    def __init__(self) -> None:
        pass
