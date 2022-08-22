import carb
import omni.ui as ui
import omni
import os
from typing import Tuple
from dataclasses import dataclass
import carb
from . import styles, mh_usd, ui_widgets


class SliderEntry:
    def __init__(
        self,
        label: str,
        model: ui.SimpleFloatModel,
        fn: object,
        image: str = None,
        step=0.01,
        min=None,
        max=None,
        default=0,
    ):
        """Custom UI element that encapsulates a labeled slider and field

        Parameters
        ----------

        model : ui.SimpleFloatModel
            Model to publish changes to
        fn : object
            Function to run when changes are made
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
        self.model = model
        self.fn = fn
        self.step = step
        self.min = min
        self.max = max
        self.default = default
        self.image = image
        self._build_widget()

    def _build_widget(self):
        """Construct the UI elements"""
        with ui.HStack(width=ui.Percent(100), height=0, style=styles.sliderentry_style):
            ui.Label(
                self.label,
                height=15,
                alignment=ui.Alignment.RIGHT,
                name="label_param",
            )
            if self.image:
                ui.Image(self.image)
            self.drag = ui.FloatDrag(model=self.model, step=self.step)
            if self.min is not None:
                self.drag.min = self.min
            if self.max is not None:
                self.drag.max = self.max


@dataclass
class Param:
    """Dataclass to store SliderEntry parameters"""

    name: str
    fn: object
    min: float = 0
    max: float = 1
    default: float = 0.5


class SliderEntryPanelModel:
    def __init__(self, params: Param):
        self.params = []
        self.float_models = []
        self.subscriptions = []
        for p in params:
            self.add_param(p)

    def add_param(self, param):
        self.params.append(param)
        float_model = ui.SimpleFloatModel()
        float_model.set_value(param.default)
        self.subscriptions.append(
            float_model.subscribe_end_edit_fn(lambda m: self._sanitize_and_run(param, float_model))
        )
        self.float_models.append(float_model)

    def _sanitize_and_run(self, param, float_model):
        """Make sure that values are within an acceptable range and then run the
        assigned function"""
        m = float_model
        getval = m.get_value_as_float
        if getval() < param.min:
            m.set_value(param.min)
        if getval() > param.max:
            m.set_value(param.max)
        param.fn(m.get_value_as_float())

    def get_float_model(self, param):
        index = self.params.index(param)
        return self.float_models[index]

    def destroy(self):
        self.subscriptions = None


class SliderEntryPanel:
    def __init__(self, model: SliderEntryPanelModel, label: str = None):
        """A UI widget providing a labeled group of slider entries

        Parameters
        ----------
        model : SliderEntryPanelModel
            Model to hold parameters
        label : str, Optional
            Display title for the group (None by default)
        """
        self.label = label
        self.model = model
        self._build_widget()

    def _build_widget(self):
        """Construct the UI elements"""
        with ui.ZStack(style=styles.panel_style, height=0):
            ui.Rectangle(name="group_rect")
            with ui.VStack(name="contents"):
                if self.label:
                    ui.Label(self.label, height=0)
                for param, float_model in zip(self.model.params, self.model.float_models):
                    SliderEntry(
                        param.name,
                        float_model,
                        param.fn,
                        min=param.min,
                        max=param.max,
                        default=param.default,
                    )

    def destroy(self):
        self.model.destroy()


class DropListItem(ui.AbstractItem):
    """Single item of the model"""

    def __init__(self, text):
        super().__init__()
        self.model = ui.SimpleStringModel(text)

    def __repr__(self):
        return f'"{self.model.as_string}"'

    def destroy(self):
        super().destroy()
        self.model.destroy()


class DropListModel(ui.AbstractItemModel):
    """
    model = DropListModel(mhcaller)
    ui.TreeView(model)
    """

    def __init__(self, mhcaller, *args):
        self.mh_call = mhcaller
        super().__init__()
        self.update()

    def drop(self, item_tagget, source):
        self.add_child(source)

    def add_child(self, item):
        self.mh_call.add_item(item)
        self.update()

    def get_item_children(self, item):
        """Returns all the children when the widget asks it."""
        if item is not None:
            # Since we are doing a flat list, we return the children of root only.
            # If it's not root we return.
            return []

        return self.children

    def get_item_value_model_count(self, item):
        """The number of columns"""
        return 1

    def get_item_value_model(self, item, column_id):
        """
        Return value model.
        It's the object that tracks the specific value.
        In our case we use ui.SimpleStringModel.
        """
        return item.model

    def update(self):
        items = [
            self.mh_call.human.eyebrowsProxy,
            self.mh_call.human.eyelashesProxy,
            self.mh_call.human.eyesProxy,
            self.mh_call.human.hairProxy,
            self.mh_call.human.proxy,
            self.mh_call.human.skeleton,
        ]
        # Add clothing from dict
        items += self.mh_call.human.clothesProxies.values()
        # Populate the list with non-Nonetype items
        self.children = [DropListItem(i.name) for i in items if i is not None]
        self._item_changed(None)

    # def drop_accepted(self, url, *args):
    #     if self.types is None:
    #         return True
    #     if os.path.splitext(url)[1] in self.types:
    #         return True
    #     else:
    #         return False


class DropList:
    def __init__(self, label, mhcaller):
        self.label = label
        self.model = DropListModel(mhcaller)
        self._build_widget()

    def _build_widget(self):
        with ui.ZStack(style=styles.panel_style):
            ui.Rectangle(name="group_rect")
            with ui.VStack(name="contents"):
                ui.Label(self.label, height=0)
                with ui.ScrollingFrame():
                    ui.TreeView(
                        self.model,
                        root_visible=False,
                        header_visible=False,
                        drop_between_items=False,
                    )
