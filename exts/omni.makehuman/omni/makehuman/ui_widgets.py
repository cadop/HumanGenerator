from xml.sax.xmlreader import AttributesImpl
import carb
from omni.makehuman.mhcaller import MHCaller
import omni.ui as ui
import omni
import os
from typing import List, Tuple, TypeVar, Union
from dataclasses import dataclass
import carb
from . import styles, mh_usd, ui_widgets
from .mhcaller import MHCaller
# TODO remove unused imports


class SliderEntry:
    """Custom UI element that encapsulates a labeled slider and field
    Attributes
    ----------
    label : str
        Label to display for slider/field
    model : ui.SimpleFloatModel
        Model to publish changes to
    fn : object
        Function to run when changes are made
    image: str
        Path on disk to an image to display
    step : float
        Division between values for the slider
    min : float
        Minimum value
    max : float
        Maximum value
    default : float
        Default parameter value
    """
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
        """Constructs an instance of SliderEntry

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
            Division between values for the slider, by default 0.01
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
    
    Attributes
    ----------
    params : list of `Param`
        List of parameter objects
    toggle : ui.SimpleBoolModel
        Tracks whether or not the human should update immediately when changes are made
    mh_call : MHCaller
        Wrapper object for Makehuman functions and data
    float_models : list of `ui.SimpleFloatModel`
        List of models to track SliderEntry values
    subscriptions : list of `Subscription`
        List of event subscriptions triggered by editing a SliderEntry
    """
    def __init__(self, params : List[Param], mh_call : MHCaller, toggle : ui.SimpleBoolModel = None):
        """Constructs an instance of SliderEntryPanelModel and instantiates models
        to hold parameter data for individual SliderEntries

        Parameters
        ----------
        params : list of `Param`
            A list of parameter objects, each of which contains the data to create
            a SliderEntry widget
        mh_call : MHCaller
            Wrapper object for Makehuman functions and data
        toggle : ui.SimpleBoolModel, optional
            Tracks whether or not the human should update immediately when changes are made, by default None
        """
        self.params = []
        """Param objects corresponding to each SliderEntry widget"""
        self.toggle = toggle
        self.mh_call = mh_call
        self.float_models = []
        """Models corresponding to each SliderEntry widget. Each model
        tracks the corresponding widget's value"""
        self.subscriptions = []
        """List of event subscriptions triggered by editing a SliderEntry"""
        for p in params:
            self.add_param(p)

    def add_param(self, param: Param):
        """Adds a parameter to the SliderEntryPanelModel. Creates a SimpleFloatModel
        initialized with the default parameter value, and subscribes the model to
        editing changes, as well as triggering the parameter function when edits
        are made.

        Parameters
        ----------
        param : Param
            The Parameter object from which to create the model and subscription
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
        # If instant update is toggled on, add the changes to the stage instantly
        if self.toggle.get_value_as_bool():
            mh_usd.add_to_scene(self.mh_call)

    # def get_float_model(self, param : Param):
    #     # TODO add docstring
    #     index = self.params.index(param)
    #     return self.float_models[index]

    def destroy(self):
        """Destroys the instance of SliderEntryPanelModel. Deletes event
        subscriptions. Important for preventing zombie-UI and unintended behavior
        when the extension is reloaded.
        """
        self.subscriptions = None


class SliderEntryPanel:
    """A UI widget providing a labeled group of slider entries

    Attributes
    ----------
    model : SliderEntryPanelModel
        Model to hold parameters for each slider
    label : str
        Display title for the group. Can be none if no title is desired.
    """
    def __init__(self, model: SliderEntryPanelModel, label: str = None):
        """

        Parameters
        ----------
        model : SliderEntryPanelModel
            Model to hold parameters
        label : str, Optional
            Display title for the group, by default None
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
        """Destroys the instance of SliderEntryPanel. Executes the destructor of
        the SliderEntryPanel's SliderEntryPanelModel instance.
        """
        self.model.destroy()

# Makehuman imports (and therefore types) are not available before runtime
# as the Makehuman app loads them through path manipulation. We have to define
# them explicitly for type hints
Skeleton = TypeVar("Skeleton")
Proxy = TypeVar("Proxy")

class DropListItemModel(ui.SimpleStringModel):
    """
    A model for referencing DropListItem data. Is a simple extension of the
    SimpleStringModel class that also references a Makehuman asset item.

    Attributes
    ----------
    mh_item : Union[Skeleton, Proxy]
        A Makehuman asset (skeleton or proxy) object to be displayed and referenced
        by the list item
    """
    def __init__(self, text : str, mh_item : Union[Skeleton, Proxy]=None) -> None:
        """Construct an instance of DropListItemModel. Stores a string in the parent
        class (SimpleStringModel) to be accessed by UI widgets, and keeps a reference
        to the asset that the list item refers to. 

        Parameters
        ----------
        text : str
            Visible text for the DropListItem UI widget
        mh_item : Union[Skeleton, Proxy], optional
            Makehuman asset (skeleton or proxy), by default None
        """
        # Initialize superclass and store text
        super().__init__(text)
        # Store the makehuman item
        self.mh_item = mh_item

    def destroy(self):
        """Destroys the instance of DropListItemModel
        """
        super().destroy()





class DropListItem(ui.AbstractItem):
    """Single UI element in a DropList
    
    Attributes
    ----------
    model : DropListItemModel
        Model to store DropListItem data (ie: display text, asset item)
    """

    def __init__(self, text : str, item : Union[Skeleton, Proxy]=None):
        """Constructs an instance of DropListItem. Item is a simple wrapper around
        a DropListItemModel for adding to a DropList.

        Parameters
        ----------
        text : str
            The name of the asset to display
        item : Union[Skeleton, Proxy], optional
            The Makehuman asset object, by default None
        """
        super().__init__()
        self.model = DropListItemModel(text, mh_item=item)

    def destroy(self):
        """Destroys the instance of DropListItem. Executes destructor of superclass
        and the DropListItem's DropListItemModel.
        """
        super().destroy()
        self.model.destroy()


class DropListModel(ui.AbstractItemModel):
    """
    Model to reference DropList data. Handles references to the data of each
    list item, as well as updating the UI, Makehuman app, and human instance when
    assets are added or removed.

    Attributes
    ----------
    mh_call : MHCaller
        Wrapper object around Makehuman functions 
    """

    def __init__(self, mhcaller : MHCaller, *args):
        """Constructs an instance of 

        Parameters
        ----------
        mhcaller : MHCaller
            Wrapper object around Makehuman functions 
        """
        self.mh_call = mhcaller
        super().__init__()
        self.update()

    def drop(self, item_tagget, source : str):
        """Method to execute when an item is dropped on the DropList widget

        Parameters
        ----------
        item_tagget : 
            Maintains backwards compatibility with old API
        source : str
            The string returned by the item being dropped. Expected to be a path
        """
        # TODO determine if this should be moved to a delegate
        self.add_child(source)

    def add_child(self, item : str):
        """Add a new item to the list. Propagates changes to the Makehuman app 
        and uses those changes to update the UI with new elements.

        Parameters
        ----------
        item : str
            Path to an asset on disk
        """
        # Add an item through the MakeHuman instance and update the widget view
        self.mh_call.add_item(item)
        self.update()

    def get_item_children(self, item):
        """Returns all the children of an item when the widget asks it. Required
        for compatibility with ui.TreeView, which implements the list view.

        Parameters
        ----------
        item : DropListItemModel
            Should always be None, as none of the list items should have children
            in a flat list.

        Returns
        -------
        List of Union[Skeleton, Proxy]
            Makehuman Skeletons and Proxies contained in the DropList
        """
        if item is not None:
            # Since we are doing a flat list, we return the children of root only.
            # If it's not root we return.
            return []

        return self.children

    def get_item_value_model_count(self, item):
        """The number of columns. We have a flat list (list items have no children),
        so there is only one column.

        Parameters
        ----------
        item : DropListItemModel
            Unused. Maintains compatibility with API.

        Returns
        -------
        int
            The number of columns, which is always one.
        """
        return 1

    def get_item_value_model(self, item : DropListItem, column_id : int):
        """Return value model of a particular list item. The value model, in this
        case a DropListItemModel, tracks the item's label and a reference to the
        corresponding asset.

        Parameters
        ----------
        item : DropListItem
            The model of the particular item in the list
        column_id : int
            Unused. The ID of the column of the item being addressed.
            Needed to maintain API compatibility.

        Returns
        -------
        DropListItemModel
            The model that holds the data of the DropListItem
        """
        return item.model

    def update(self):
        """Gathers all assets (Skeleton/Proxies) from the human, and updates the
        list UI to reflect any changes.
        """
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
class DropListDelegate(ui.AbstractItemDelegate):
    """Delegate object for executing functions needed by a DropList. Can be used
    when creating a TreeView to add double-clickable/removeable elements
    """
    def __init__(self):
        """Constructs an instance of DropListDelegate
        """
        super().__init__()

    def build_widget(self, model : DropListModel, item : DropListItemModel, column_id : int, level : int, expanded : bool):
        """Build widget UI

        Parameters
        ----------
        model : DropListModel
            Model that stores data about the entire list
        item : DropListItemModel
            Stores data about one list item in particular
        column_id : int
            The ID of the column where our list item is found. Should be 0, as our list is flat
        level : int
            Unused. The depth of an item in the list tree. Needed to maintain API compatibility
        expanded : bool
            Unused. Whether or not a list item is expanded to show its children. None of our
            list items have children, so this should always be false. Needed to maintain
            compatibility with API.
        """
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

    def on_double_click(self, button : int, item : Union[Skeleton, Proxy], list_model : DropListModel):
        """Executed on doubleclick. Removes the clicked item from the list.

        Parameters
        ----------
        button : int
            The number of the mouse button being clicked. 0 is left click (primary)
        item : Union[Skeleton, Proxy]
            A Makehuman asset item
        list_model : DropListModel
            The model that references all of the list data
        """
        if button != 0:
            return
        list_model.mh_call.remove_item(item)
        list_model.update()

class DropList:
    """A scrollable list onto which assets can be dropped from the Makehuman asset
    browser. Items can also be removed by doubleclicking on a list item. Displays
    the assets which are currently applied to the human.

    Attributes
    ----------
    label : str
        The label to display above the list
    model : DropListModel
        An object in which to store data for the list and all of its items
    """
    def __init__(self, label : str, mhcaller : MHCaller):
        """Constructs an instance of DropList. Passes the Makehuman application
        wrapper to the DropListModel so changes to the human can be reflected in
        the list and vice-versa.

        Parameters
        ----------
        label : str
            Label to display above the list
        mhcaller : MHCaller
            Wrapper object around Makehuman data and functions 
        """
        self.label = label
        # Model for storing widget data - accepts reference to Makehuman wrapper
        self.model = DropListModel(mhcaller)
        self._build_widget()

    def _build_widget(self):
        """Builds widget UI
        """
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