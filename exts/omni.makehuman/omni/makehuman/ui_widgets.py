import carb
import omni.ui as ui
import omni
import os
from typing import List, Tuple
from dataclasses import dataclass
import carb
from . import styles, mh_usd, ui_widgets
# TODO remove unused imports


class SliderEntry:
    def __init__(
        self,
        label: str,
        model: ui.SimpleFloatModel,
        fn: object,
        image: str = None,
        step : float=0.01,
        min : float=None,
        max : float=None,
        default : float=0,
    ):
        """Custom UI element that encapsulates a labeled slider and field

        Parameters
        ----------
        label : str
            Label to display for slider/field
        model : ui.SimpleFloatModel
            Model to publish changes to
        fn : object
            Function to run when changes are made
        image: str, optional
            Path on disk to an image to display. By default None
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
    """Dataclass to store SliderEntry parameter data
    
    Attributes
    ----------
    name: str
        The name of the parameter. Used for labeling.
    fn: object
        The method to execute when making changes to the parameter
    image: str, optional
        The path to the image to use for labeling. By default None
    min: float, optional
        The minimum allowed value of the parameter. By default 0
    max: float
        The maximum allowed value of the parameter. By default 1
    default: float
        The default value of the parameter. By default 0.5
    """

    name: str
    fn: object
    image: str = None
    min: float = 0
    max: float = 1
    default: float = 0.5


class SliderEntryPanelModel:
    """Provides a model for referencing SliderEntryPanel data. References models
    for each individual SliderEntry widget in the SliderEntryPanel widget.
    

    """
    def __init__(self, params: List[Param]):
        """Constructs an instance of SliderEntryPanelModel and instantiates models
        to hold parameter data for individual SliderEntries

        Parameters
        ----------
        params : list of `Param`
            A list of parameter objects, each of which contains the data to create
            a SliderEntry widget

        Attributes
        ----------
        params : list of `Param`
            List of parameter objects
        float_models : list of `ui.SimpleFloatModel`
            List of models to track SliderEntry values
        subscriptions : list of `Subscription`
            List of event subscriptions triggered by editing a SliderEntry
        """
        self.params = []
        """Param objects corresponding to each SliderEntry widget"""
        self.float_models = []
        """Models corresponding to each SliderEntry widget. Each model
        tracks the corresponding widget's value"""
        self.subscriptions = []
        """List of event subscriptions triggered by editing a SliderEntry"""
        for p in params:
            self.add_param(p)

    def add_param(self, param: Param):
        """_summary_

        Parameters
        ----------
        param : Param
            _description_
        """
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

    def _sanitize_and_run(self, param : Param, float_model : ui.SimpleFloatModel):
        """Make sure that values are within an acceptable range and then run the
        assigned function

        Parameters
        ----------
        param : Param
            Parameter object which contains acceptable value bounds and
            references the function to run
        float_model : ui.SimpleFloatModel
            Model which stores the value from the widget
        """
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

    # def get_float_model(self, param : Param):
    #     # TODO add docstring
    #     index = self.params.index(param)
    #     return self.float_models[index]

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
