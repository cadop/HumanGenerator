import omni.ui as ui
import omni.kit.commands
import json
from typing import List, TypeVar, Union, Callable
from dataclasses import dataclass, field
from . import styles
from pxr import Usd, Tf
import os
import inspect
from siborg.create.human.shared import data_path
from collections import defaultdict

class SliderEntry:
    """Custom UI element that encapsulates a labeled slider and field
    Attributes
    ----------
    label : str
        Label to display for slider/field
    model : ui.SimpleFloatModel
        Model to publish changes to
    fn : object
        Function to run when updating the human after changes are made
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
        step: float = 0.01,
        min: float = None,
        max: float = None,
        default: float = 0,
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
        with ui.HStack(height=0, style=styles.sliderentry_style):
            # If an image is available, display it
            if self.image:
                ui.Image(self.image, height=75, style={"border_radius": 5})
            # Stack the label and slider on top of each other
            with ui.VStack(spacing = 5):
                ui.Label(
                    self.label,
                    height=15,
                    alignment=ui.Alignment.CENTER,
                    name="label_param",
                )
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
    label: str
        A label for the parameter
    full_name: str
        The original, full name of the modifier
    blend: str
        The base name of the blendshape(s) to modify
    image: str, optional
        The path to the image to use for labeling. By default None
    min_blend: str, optional
        Suffix (appended to `blendshape`) naming the blendshape for decreasing the value. Empty string by default.
    max_blend: str, optional
        Suffix (appended to `blendshape`) naming the blendshape for increasing the value. Empty string by default.
    min: float, optional
        The minimum value for the parameter. By default -1
    max: float, optional
        The maximum value for the parameter. By default 1
    value : ui.SimpleFloatModel
        The model to track the current value of the parameter. By default None
    """

    label: str
    full_name: str
    blend: str
    image: str = None
    min_blend: str = ""
    max_blend: str = ""
    min: float = -1
    max: float = 1
    value: ui.SimpleFloatModel = None

class ModifierGroup:
    """A UI widget providing a labeled group of slider entries

    Attributes
    ----------
    label : str
        Display title for the group. Can be none if no title is desired.
    params : list of Param
        List of parameters to display in the group
    """

    def __init__(self, label: str = None, params: List[Param] = None):
        self.label = label
        self.params = params or []
        self._build_widget()

    def _build_widget(self):
        """Construct the UI elements"""
        # Layer widgets on top of a rectangle to create a group frame
        with ui.ZStack(style=styles.panel_style, height=0):
            ui.Rectangle(name="group_rect")
            with ui.VStack(name="contents", spacing = 8):
                # If the panel has a label, show it
                if self.label:
                    ui.Label(self.label, height=0)
                # Create a slider entry for each parameter
                for param in self.params:
                    SliderEntry(
                        param.label,
                        param.value,
                        lambda x: None,
                        image=param.image,
                        min=param.min,
                        max=param.max,
                        default=0,
                    )

    def destroy(self):
        """Destroys the instance of SliderEntryPanel. Executes the destructor of
        the SliderEntryPanel's SliderEntryPanelModel instance.
        """
        self.params = None

class ModifierUI(ui.Frame):
    """UI Widget for displaying and modifying human parameters

    Attributes
    ----------
    model : ParamPanelModel
        Stores data for the panel
    toggle : ui.SimpleBoolModel
        Model to track whether changes should be instant
    models : list of SliderEntryPanelModel
        Models for each group of parameter sliders
    """

    def __init__(self, **kwargs):
        """Constructs an instance of ParamPanel. Panel contains a scrollable list of collapseable groups. These include
        a group of macros (which affect multiple modifiers simultaneously), as well as groups of modifiers for
        different body parts. Each modifier can be adjusted using a slider or doubleclicking to enter values directly.
        Values are restricted based on the limits of a particular modifier.
        """

        # Subclassing ui.Frame allows us to use styling on the whole widget
        super().__init__(**kwargs)
        # If no instant update function is passed, use a dummy function and do nothing
        self.groups = self.parse_modifiers()
        self.set_build_fn(self._build_widget)

    def _build_widget(self):
        with self:
            for group, params in self.groups.items():
                ModifierGroup(group, params)

    def parse_modifiers(self):
        """Parses modifiers from a json file and builds the UI"""
        manager = omni.kit.app.get_app().get_extension_manager()
        ext_id = manager.get_enabled_extension_id("siborg.create.human")
        ext_path = manager.get_extension_path(ext_id)
        json_path = os.path.join(ext_path, "data", "modifiers", "modeling_modifiers.json")

        groups = defaultdict(list)

        with open(json_path, "r") as f:
            data = json.load(f)
            for group in data:
                for modifier in group["modifiers"]:
                    if "target" in modifier:
                        tlabel = modifier["target"].split("-")
                        if "|" in tlabel[len(tlabel) - 1]:
                            tlabel = tlabel[:-1]
                        if len(tlabel) > 1 and tlabel[0] == group:
                            label = tlabel[1:]
                        else:
                            label = tlabel
                        label = " ".join([word.capitalize() for word in label])

                        # Guess a suitable image path from modifier name
                        tlabel = modifier["target"].replace("|", "-").split("-")
                        # image = modifier_image(("%s.png" % "-".join(tlabel)).lower())
                        image = None

                        # Blendshapes are named based on the modifier name
                        blend = Tf.MakeValidIdentifier(modifier["target"])
                        
                        # Some modifiers only adress one blendshape, others adress two in either direction
                        min_val = 0
                        max_val = 1
                        
                        if "min" in modifier:
                            min_blend = Tf.MakeValidIdentifier(f"{blend}_{modifier['min']}")
                            min_val = -1
                        if "max" in modifier:
                            max_blend = Tf.MakeValidIdentifier(f"{blend}_{modifier['max']}")


                        # Create a parameter for the modifier
                        param = Param(
                            label,
                            modifier["target"],
                            image or None,
                            blend,
                            min_blend,
                            max_blend,
                            min_val,
                            max_val
                        )
                        # Add the parameter to the group
                        groups[group["group"]].append(param)

        return groups


    def reset(self):
        """Reset every SliderEntryPanel to set UI values to defaults
        """
        for model in self.models:
            model.reset()

    def load_values(self, human_prim: Usd.Prim):
        """Load values from the human prim into the UI. Specifically, this function
        loads the values of the modifiers from the prim and updates any which
        have changed.

        Parameters
        ----------
        HumanPrim : Usd.Prim
            The USD prim representing the human
        """

        # Make the prim exists
        if not human_prim.IsValid():
            return
        
        # Reset the UI to defaults
        self.reset()

        # Get the data from the prim
        humandata = human_prim.GetCustomData()

        modifiers = humandata.get("Modifiers")

        # Set any changed values in the models
        for SliderEntryPanelModel in self.models:
            for param in SliderEntryPanelModel.params:
                if param.full_name in modifiers:
                    param.value.set_value(modifiers[param.full_name])

    def update_models(self):
        """Update all models"""
        for model in self.models:
            model.apply_changes()

    def destroy(self):
        """Destroys the ParamPanel instance as well as the models attached to each group of parameters
        """
        super().destroy()
        for model in self.models:
            model.destroy()


class NoSelectionNotification:
    """
    When no human selected, show notification.
    """
    def __init__(self):
        self._container = ui.ZStack()
        with self._container:
            ui.Rectangle()
            with ui.VStack(spacing=10):
                ui.Spacer(height=10)
                with ui.HStack(height=0):
                    ui.Spacer()
                    ui.ImageWithProvider(
                        data_path('human_icon.png'),
                        width=192,
                        height=192,
                        fill_policy=ui.IwpFillPolicy.IWP_PRESERVE_ASPECT_FIT
                    )
                    ui.Spacer()
                self._message_label = ui.Label(
                    "No human is current selected.",
                    height=0,
                    alignment=ui.Alignment.CENTER
                )
                self._suggestion_label = ui.Label(
                    "Select a human prim to see its properties here.",
                    height=0,
                    alignment=ui.Alignment.CENTER
                )

    @property
    def visible(self) -> bool:
        return self._container.visible

    @visible.setter
    def visible(self, value) -> None:
        self._container.visible = value

    def set_message(self, message: str) -> None:
        messages = message.split("\n")
        self._message_label.text = messages[0]
        self._suggestion_label.text = messages[1]


def modifier_image(name : str):
    """Guess the path to a modifier's corresponding image on disk based on the name
    of the modifier. Useful for building UI for list of modifiers.

    Parameters
    ----------
    name : str
        Name of the modifier

    Returns
    -------
    str
        The path to the image on disk
    """
    if name is None:
        # If no modifier name is provided, we can't guess the file name
        return None
    name = name.lower()
    # Return the modifier path based on the modifier name
    # TODO determine if images can be loaded from the Makehuman module stored in
    # site-packages so we don't have to include the data twice
    return os.path.join(os.path.dirname(inspect.getfile(makehuman)),targets.getTargets().images.get(name, name))
