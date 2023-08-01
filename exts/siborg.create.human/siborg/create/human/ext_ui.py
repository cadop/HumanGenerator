import omni.ui as ui
import omni.kit.commands
import json
from typing import List, TypeVar, Union, Callable
from dataclasses import dataclass, field
from . import styles
from pxr import Usd
import os
import inspect
from siborg.create.human.shared import data_path

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
    name: str
        The name of the parameter. Used for labeling.
    full_name: str
        The full name of the parameter. Used for referencing
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
    value : ui.SimpleFloatModel
        The model to track the current value of the parameter. By default None
    """

    name: str
    full_name: str
    fn: object
    image: str = None
    min: float = 0
    max: float = 1
    default: float = 0.5
    value: ui.SimpleFloatModel = None



class SliderEntryPanelModel:
    """Provides a model for referencing SliderEntryPanel data. References models
    for each individual SliderEntry widget in the SliderEntryPanel widget.

    Attributes
    ----------
    params : list of `Param`
        List of parameter objects. Each contains a float model to track the current value
    toggle : ui.SimpleBoolModel
        Tracks whether or not the human should update immediately when changes are made
    instant_update : Callable
        A function to call when instant update is toggled
    subscriptions : list of `Subscription`
        List of event subscriptions triggered by editing a SliderEntry
    """

    def __init__(self, params: List[Param], toggle: ui.SimpleBoolModel = None, instant_update: Callable = None):
        """Constructs an instance of SliderEntryPanelModel and instantiates models
        to hold parameter data for individual SliderEntries

        Parameters
        ----------
        params : list of `Param`
            A list of parameter objects, each of which contains the data to create
            a SliderEntry widget and a model to track the current value
        toggle : ui.SimpleBoolModel, optional
            Tracks whether or not the human should update immediately when changes are made, by default None
        instant_update : Callable
            A function to call when instant update is toggled
        """

        self.params = []
        """Param objects corresponding to each SliderEntry widget"""
        self.changed_params = []
        """Params o SliderEntry widgets that have been changed"""

        self.subscriptions = []
        """List of event subscriptions triggered by editing a SliderEntry"""
        for p in params:
            self.add_param(p)

    def parse_modifiers(self):
        """Parses modifiers from a json file and builds the UI"""
        ext_path = omni.kit.commands.get_app().get_extension_manager().get_extension_path("siborg.create.human")
        json_path = os.path.join(ext_path, "data", "modifiers.json")
        with open(json_path, "r") as f:
            data = json.load(f)
        return data

    def add_param(self, param: Param):
        """Adds a parameter to the SliderEntryPanelModel. Subscribes to the parameter's model
        to check for editing changes

        Parameters
        ----------
        param : Param
            The Parameter object from which to create the subscription
        """

        # Create a model to track the current value of the parameter. Set the value to the default
        param.value = ui.SimpleFloatModel(param.default)

        # Add the parameter to the list of parameters
        self.params.append(param)

        # Subscribe to changes in parameter editing
        self.subscriptions.append(
            param.value.subscribe_end_edit_fn(
                lambda m: self._sanitize_and_run(param))
        )

    def reset(self):
        """Resets the values of each floatmodel to parameter default for UI reset
        """
        for param in self.params:
            param.value.set_value(param.default)

    def _sanitize_and_run(self, param: Param):
        """Make sure that values are within an acceptable range and then add the parameter to the
        list of changed parameters

        Parameters
        ----------
        param : Param
            Parameter object which contains acceptable value bounds and
            references the function to run
        """
        m = param.value
        # Get the value from the slider model
        getval = m.get_value_as_float
        # Set the value to the min or max if it goes under or over respectively
        if getval() < param.min:
            m.set_value(param.min)
        if getval() > param.max:
            m.set_value(param.max)

        # Check if the parameter is already in the list of changed parameters. If so, remove it.
        # Then, add the parameter to the list of changed parameters
        if param in self.changed_params:
            self.changed_params.remove(param)
        self.changed_params.append(param)

        # If instant update is toggled on, add the changes to the stage instantly
        if self.toggle.get_value_as_bool():
            # Apply the changes
            self.apply_changes()
            # Run the instant update function
            self.instant_update()

    def apply_changes(self):
        """Apply the changes made to the parameters. Runs the function associated with each
        parameter using the value from the widget
        """
        for param in self.changed_params:
            param.fn(param.value.get_value_as_float())
        # Clear the list of changed parameters
        self.changed_params = []

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
        with ui.ZStack(style=styles.panel_style, height=0):
            ui.Rectangle(name="group_rect")
            with ui.VStack(name="contents", spacing = 8):
                # If the panel has a label, show it
                if self.label:
                    ui.Label(self.label, height=0)
                # Create a slider entry for each parameter
                for param in self.model.params:
                    SliderEntry(
                        param.name,
                        param.value,
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

class ParamPanelModel(ui.AbstractItemModel):
    def __init__(self, **kwargs):
        """Constructs an instance of ParamPanelModel, which stores data for a ParamPanel.
        """

        super().__init__(**kwargs)
        # model to track whether changes should be instant

        # Reference to models for each modifier/parameter. The models store modifier
        # data for reference in the UI, and track the values of the sliders
        self.models = []


class ParamPanel(ui.Frame):
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

    def __init__(self, model: ParamPanelModel, **kwargs):
        """Constructs an instance of ParamPanel. Panel contains a scrollable list of collapseable groups. These include
        a group of macros (which affect multiple modifiers simultaneously), as well as groups of modifiers for
        different body parts. Each modifier can be adjusted using a slider or doubleclicking to enter values directly.
        Values are restricted based on the limits of a particular modifier.

        Parameters
        ----------
        model: ParamPanelModel
            Stores data for the panel.
        """

        # Subclassing ui.Frame allows us to use styling on the whole widget
        super().__init__(**kwargs)
        self.model = model
        # If no instant update function is passed, use a dummy function and do nothing
        self.models = model.models
        self.set_build_fn(self._build_widget)


    def _build_widget(self):
        """Build widget UI
        """
        Modifier = TypeVar('Modifier')

        def modifier_param(m: Modifier):
            """Generate a parameter data object from a human modifier,

            Parameters
            ----------
            m : Modifier
                Makehuman Human modifier object. Represents a set of targets to apply to the human when modifying

            Returns
            -------
            Param
                Parameter data object holding all the modifier data needed to build UI elements
            """
            # print(m.name)
            # Guess a suitable title from the modifier name
            tlabel = m.name.split("-")
            if "|" in tlabel[len(tlabel) - 1]:
                tlabel = tlabel[:-1]
            if len(tlabel) > 1 and tlabel[0] == m.groupName:
                label = tlabel[1:]
            else:
                label = tlabel
            label = " ".join([word.capitalize() for word in label])

            # Guess a suitable image path from modifier name
            tlabel = m.name.replace("|", "-").split("-")
            image = modifier_image(("%s.png" % "-".join(tlabel)).lower())

            # Store modifier info in dataclass for building UI elements
            return Param(
                label,
                m.fullName,
                m.updateValue,
                image=image,
                min=m.getMin(),
                max=m.getMax(),
                default=m.getDefaultValue(),
            )

        def group_params(group: str):
            """Creates a list of parameters for all the modifiers in the given group

            Parameters
            ----------
            group : str
                The name name of a modifier group

            Returns
            -------
            List of Param
                A list of all the parameters built from modifiers in the group
            """
            params = [modifier_param(m)
                      for m in MHCaller.human.getModifiersByGroup(group)]
            return params

        def build_macro_frame():
            """Builds UI widget for the group of macro modifiers (which affect multiple individual modifiers
            simultaneously). This includes:
            + Gender
            + Age
            + Muscle
            + Weight
            + Height
            + Proportions

            Parameters that affect how much the human resembles a particular racial group:
            + African
            + Asian
            + Caucasian
            """
            # Shorten human reference for convenience
            human = MHCaller.human

            # Explicitly create parameters for panel of macros (general modifiers that
            # affect a group of targets). Otherwise these look bad. Creates a nice
            # panel to have open by default
            macro_params = (
                Param("Gender", "macrodetails/Gender", human.setGender),
                Param("Age", "macrodetails/Age", human.setAge),
                Param("Muscle", "macrodetails-universal/Muscle", human.setMuscle),
                Param("Weight", "macrodetails-universal/Weight", human.setWeight),
                Param("Height", "macrodetails-height/Height", human.setHeight),
                Param("Proportions", "macrodetails-proportions/BodyProportions", human.setBodyProportions),
            )
            # Create a model for storing macro parameter data
            macro_model = SliderEntryPanelModel(macro_params, self.toggle,  self.instant_update)

            # Separate set of race parameters to also be included in the Macros group
            # TODO make race parameters automatically normalize in UI
            race_params = (
                Param("African", "macrodetails/African", human.setAfrican),
                Param("Asian", "macrodetails/Asian", human.setAsian),
                Param("Caucasian", "macrodetails/Caucasian", human.setCaucasian),
            )
            # Create a model for storing race parameter data
            race_model = SliderEntryPanelModel(race_params, self.toggle, self.instant_update)

            self.models.append(macro_model)
            self.models.append(race_model)

            # Create category widget for macros
            with ui.CollapsableFrame("Macros", style=styles.frame_style, height=0, collapsed=True):
                with ui.VStack():
                    # Create panels for macros and race
                    self.panels = (
                        SliderEntryPanel(macro_model, label="General"),
                        SliderEntryPanel(race_model, label="Race"),
                    )

        # The scrollable list of modifiers
        with ui.ScrollingFrame():
            with ui.VStack():
                # Add the macros frame first
                build_macro_frame()

                # Create a set of all modifier groups that include macros
                macrogroups = [
                    g for g in MHCaller.human.modifierGroups if "macrodetails" in g]
                macrogroups = set(macrogroups)

                # Remove macro groups from list of modifier groups as we have already
                # included them explicitly
                allgroups = set(
                    MHCaller.human.modifierGroups).difference(macrogroups)

                for group in allgroups:
                    # Create a collapseable frame for each modifier group
                    with ui.CollapsableFrame(group.capitalize(), style=styles.frame_style, collapsed=True):
                        # Model to hold panel parameters
                        model = SliderEntryPanelModel(
                            group_params(group), self.toggle,self.instant_update)
                        self.models.append(model)
                        # Create panel of slider entries for modifier group
                        SliderEntryPanel(model)

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
