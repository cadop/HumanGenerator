import carb
import omni.ui as ui
import omni
import os
from typing import Tuple
from dataclasses import dataclass
import carb
from . import styles, mh_usd, ui_widgets
from .mhcaller import MHCaller
# TODO remove unused imports


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
        # TODO add image
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
        # TODO Remove width and include height in style
        with ui.HStack(width=ui.Percent(100), height=0, style=styles.sliderentry_style):
            # TODO include height and alignment in style
            ui.Label(
                self.label,
                height=15,
                alignment=ui.Alignment.RIGHT,
                name="label_param",
            )
            # If an image is available, display it
            if self.image:
                ui.Image(self.image)
            # create a floatdrag (can be used as a slider or an entry field) to
            # input parameter values
            self.drag = ui.FloatDrag(model=self.model, step=self.step)
            # Limit drag values to within min and max if provided
            if self.min is not None:
                self.drag.min = self.min
            if self.max is not None:
                self.drag.max = self.max


@dataclass
class Param:
    """Dataclass to store SliderEntry parameters"""
    # TODO add variable descriptions to docstring

    name: str
    fn: object
    image: str = None
    min: float = 0
    max: float = 1
    default: float = 0.5


class SliderEntryPanelModel:
    def __init__(self, params: Param, mh_call : MHCaller, toggle : ui.SimpleBoolModel = None):
        # TODO add docstring
        self.params = []
        self.toggle = toggle
        self.mh_call = mh_call
        self.float_models = []
        self.subscriptions = []
        for p in params:
            self.add_param(p)

    def add_param(self, param):
        # TODO add docstring
        # Add the parameter to the list of parameters
        self.params.append(param)
        # Simple float model to store parameter value
        float_model = ui.SimpleFloatModel()
        # Set the float model value to the default value of the parameter
        float_model.set_value(param.default)
        # Subscribe to changes in parameter editing
        # TODO Make option to update human in stage everytime a change is made
        # TODO Implement viewport for realtime changes
        self.subscriptions.append(
            float_model.subscribe_end_edit_fn(
                lambda m: self._sanitize_and_run(param, float_model))
        )
        # Add model to list of models
        self.float_models.append(float_model)

    def _sanitize_and_run(self, param, float_model):
        """Make sure that values are within an acceptable range and then run the
        assigned function"""
        m = float_model
        # Get the value from the slider model
        getval = m.get_value_as_float
        # Set the value to the min or max if it goes under or over respectively
        if getval() < param.min:
            m.set_value(param.min)
        if getval() > param.max:
            m.set_value(param.max)
        # Run the function given by the parameter using the value from the widget
        param.fn(m.get_value_as_float())
        # If instant update is toggled on, add the changes to the stage instantly
        if self.toggle.get_value_as_bool():
            mh_usd.add_to_scene(self.mh_call)

    def get_float_model(self, param):
        # TODO add docstring
        index = self.params.index(param)
        return self.float_models[index]

    def destroy(self):
        # TODO add docstring
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
            # TODO edit description to be consistent with docstring style
            # "(None by default)" -> "by default None"
        """
        self.label = label
        self.model = model
        self._build_widget()

    def _build_widget(self):
        """Construct the UI elements"""
        # Layer widgets on top of a rectangle to create a group frame
        # TODO add height to style
        with ui.ZStack(style=styles.panel_style, height=0):
            ui.Rectangle(name="group_rect")
            with ui.VStack(name="contents"):
                # If the panel has a label, show it
                if self.label:
                    ui.Label(self.label, height=0)
                # Create a slider entry for each parameter and corresponding float model
                for param, float_model in zip(self.model.params, self.model.float_models):
                    SliderEntry(
                        param.name,
                        float_model,
                        param.fn,
                        image=param.image,
                        min=param.min,
                        max=param.max,
                        default=param.default,
                    )

    def destroy(self):
        #TODO add docstring
        self.model.destroy()


class DropListItemModel(ui.SimpleStringModel):
    def __init__(self, text, mh_item=None) -> None:
        # TODO add docstring
        # Initialize superclass and store text
        super().__init__(text)
        # Store the makehuman item
        self.mh_item = mh_item

    def destroy(self):
        # TODO add docstring
        super().destroy()


class DropListDelegate(ui.AbstractItemDelegate):
    def __init__(self):
        # TODO add docstring
        super().__init__()

    def build_widget(self, model, item, column_id, level, expanded):
        # TODO add docstring
        # Get the model that represents a given list item
        value_model = model.get_item_value_model(item, column_id)
        # Create a label and style it after the default TreeView item style
        label = ui.Label(value_model.as_string,
                         style_type_name_override="TreeView.Item")
        # Remove item when double clicked by passing the makehuman item from the
        # list item model and the list model which has a reference to the Makehuman
        # wrapper
        label.set_mouse_double_clicked_fn(
            lambda x, y, b, m: self.on_double_click(b, value_model.mh_item, model))

    def on_double_click(self, button, item, list_model):
        """Called when the user double-clicked the item in TreeView"""
        # TODO fix docstring grammar
        if button != 0:
            return
        list_model.mh_call.remove_item(item)
        list_model.update()


class DropListItem(ui.AbstractItem):
    """Single item of the model"""

    def __init__(self, text, item=None):
        # TODO add docstring
        super().__init__()
        self.model = DropListItemModel(text, mh_item=item)

    def destroy(self):
        # TODO add docstring
        super().destroy()
        self.model.destroy()


class DropListModel(ui.AbstractItemModel):
    """
    model = DropListModel(mhcaller)
    ui.TreeView(model)
    """
    # TODO remove unclear example

    def __init__(self, mhcaller, *args):
        # TODO add docstring
        self.mh_call = mhcaller
        super().__init__()
        self.update()

    def drop(self, item_tagget, source):
        # TODO add docstring
        # TODO determine if this should be moved to a delegate
        self.add_child(source)

    def add_child(self, item):
        # TODO add docstring
        # Add an item through the MakeHuman instance and update the widget view
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
        In our case we use DropListItemModel.
        """
        return item.model

    def update(self):
        # TODO add docstring
        # TODO use makehuman internal function to gather proxies
        # Gather all proxies from the human object
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
        # TODO change whitespace
        self.children = [DropListItem(i.name, item=i)
                         for i in items if i is not None]
        # Propagate changes to UI
        self._item_changed(None)

    # TODO remove
    # def drop_accepted(self, url, *args):
    #     if self.types is None:
    #         return True
    #     if os.path.splitext(url)[1] in self.types:
    #         return True
    #     else:
    #         return False


class DropList:
    def __init__(self, label, mhcaller):
        # TODO add docstring
        self.label = label
        # Model for storing widget data - accepts reference to Makehuman wrapper
        self.model = DropListModel(mhcaller)
        self._build_widget()

    def _build_widget(self):
        # TODO add docstring
        # Layer widgets on top of a rectangle to create a group frame
        with ui.ZStack(style=styles.panel_style):
            ui.Rectangle(name="group_rect")
            with ui.VStack(name="contents"):
                ui.Label(self.label, height=0)
                # Make a scrollable area for long lists
                with ui.ScrollingFrame():
                    # Create a delegate to handle execution, doubleclick, and
                    # widget building
                    self.delegate = DropListDelegate()
                    # Create the list widget
                    ui.TreeView(
                        self.model,
                        delegate=self.delegate,
                        root_visible=False,
                        header_visible=False,
                        drop_between_items=False,
                    )
