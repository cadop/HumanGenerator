import omni.ext
import omni.ui as ui
from . import mhcaller
import omni


def slider_entry(mh_call, label, division=0.01, min=None, max=None):

    with ui.HStack():
        ui.Label(label, height=15, width=50)
        field = ui.FloatField(height=15, width=50)
        ui.FloatSlider(min=1, max=89, step=0.25, model=field.model)
        field.model.add_value_changed_fn(lambda m: mh_call.set_age(m.get_value_as_int()))
