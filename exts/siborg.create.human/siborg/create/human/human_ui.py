from siborg.create.human.mhcaller import MHCaller, modifier_image
from typing import Generic, TypeVar
import omni.ui as ui
from .ui_widgets import *
from .styles import *
from . import mh_usd





Human = TypeVar('Human')

class ParamPanelModel(ui.AbstractItemModel):
    def __init__(self, mh_call : MHCaller, toggle : ui.SimpleBoolModel, **kwargs):
        """Constructs an instance of ParamPanelModel, which stores data for a ParamPanel.

        Parameters
        ----------
        mh_call : MHCaller
            Wrapper around Makehuman data (including human data) and functions
        toggle : ui.SimpleBoolModel
            Model to track whether changes should be instant
        """



        super().__init__(**kwargs)
        # Wrapper around Makehuman data (including human data) and functions
        self.mh_call = mh_call
        # model to track whether changes should be instant
        self.toggle = toggle

        # Reference to models for each modifier/parameter. The models store modifier
        # data for reference in the UI
        self.models = []

    
class ParamPanel(ui.Frame):
    """UI Widget for displaying and modifying human parameters
    
    Attributes
    ----------
    model : ParamPanelModel
        Stores data for the panel
    mh_call : MHCaller
        Wrapper around Makehuman data (including human data) and functions
    toggle : ui.SimpleBoolModel
        Model to track whether changes should be instant
    models : list of SliderEntryPanelModel
        Models for each group of parameter sliders
    """

    def __init__(self, model : ParamPanelModel, **kwargs):
        """Constructs an instance of ParamPanel. Panel contains a scrollable list of collapseable groups. These include a group of macros (which affect multiple modifiers simultaneously), as well as groups of modifiers for different body parts. Each modifier can be adjusted using a slider or doubleclicking to enter values directly. Values are restricted based on the limits of a particular modifier.

        Parameters
        ----------
        mh_call : MHCaller
            Wrapper around Makehuman data (including human data) and functions
        toggle : ui.SimpleBoolModel
            Model to track whether changes should be instant
        """

        # Subclassing ui.Frame allows us to use styling on the whole widget
        super().__init__(**kwargs)
        self.model = model
        self.mh_call = model.mh_call
        self.toggle = model.toggle
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
                      for m in self.mh_call.human.getModifiersByGroup(group)]
            return params

        def build_macro_frame():
            """Builds UI widget for the group of macro modifiers (which affect multiple individual modifiers simultaneously). This includes:
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
            # TODO rename to indicate private function
            # Shorten human reference for convenience
            human = self.mh_call.human

            # Explicitly create parameters for panel of macros (general modifiers that
            # affect a group of targets). Otherwise these look bad. Creates a nice
            # panel to have open by default
            macro_params = (
                Param("Gender", human.setGender),
                Param("Age", human.setAge),
                Param("Muscle", human.setMuscle),
                Param("Weight", human.setWeight),
                Param("Height", human.setHeight),
                Param("Proportions", human.setBodyProportions),
            )
            # Create a model for storing macro parameter data
            macro_model = SliderEntryPanelModel(macro_params, self.mh_call, self.toggle)

            # Separate set of race parameters to also be included in the Macros group
            # TODO make race parameters automatically normalize in UI
            race_params = (
                Param("African", human.setAfrican),
                Param("Asian", human.setAsian),
                Param("Caucasian", human.setCaucasian),
            )
            # Create a model for storing race parameter data
            race_model = SliderEntryPanelModel(race_params, self.mh_call, self.toggle)

            self.models.append(macro_model)
            self.models.append(race_model)

            # Create category widget for macros
            with ui.CollapsableFrame("Macros", style=styles.frame_style, height=0):
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
                    g for g in self.mh_call.human.modifierGroups if "macrodetails" in g]
                macrogroups = set(macrogroups)

                # Remove macro groups from list of modifier groups as we have already
                # included them explicitly
                allgroups = set(
                    self.mh_call.human.modifierGroups).difference(macrogroups)

                for group in allgroups:
                    # Create a collapseable frame for each modifier group
                    with ui.CollapsableFrame(group.capitalize(), style=styles.frame_style, collapsed=True):
                        # Model to hold panel parameters
                        model = SliderEntryPanelModel(group_params(group), self.mh_call, self.toggle)
                        self.models.append(model)
                        # Create panel of slider entries for modifier group
                        SliderEntryPanel(model)

    def reset(self):
        """Reset every SliderEntryPanel to set UI values to defaults
        """
        for model in self.models:
            model.reset()

    def destroy(self):
        """Destroys the ParamPanel instance as well as the models attached to each group of parameters
        """
        super().destroy()
        for model in self.models:
            model.destroy()

