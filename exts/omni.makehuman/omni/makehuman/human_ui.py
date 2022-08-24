from omni.makehuman.mhcaller import modifier_image
import omni.ui as ui
from .ui_widgets import *
from .styles import *
from . import mh_usd


class HumanPanel:
    # UI Widget that includes list of modifiers, applied assets, and function buttons
    def __init__(self, mhcaller, **kwargs):
        # TODO remove **kwargs
        # Reference to manager class for Makehuman
        self.mh_call = mhcaller

        self._build_widget()

    def _build_widget(self):

        # Human object
        human = self.mh_call.human

        with ui.HStack():

            # UI for modifiers and parameters (affects physical characteristics)
            self.params = ParamPanel(human, width=300)

            # UI for tracking applied assets and executing functions (eg. Create New Human)
            self.buttons = ButtonPanel(self.mh_call, width=200)

    def destroy(self):
        # super().destroy()
        self.params.destroy()
        self.buttons.destroy()


class ParamPanel(ui.Frame):
    def __init__(self, human, toggle : ui.SimpleBoolModel, **kwargs):
        # Subclassing ui.Frame allows us to use styling on the whole widget
        super().__init__(**kwargs)

        self.human = human
        # model to track whether changes should be instant
        self.toggle = toggle

        # Reference to models for each modifier/parameter. The models store modifier
        # data for reference in the UI
        self.models = []

        self.set_build_fn(self._build_widget)

    def _build_widget(self):

        def modifier_param(m):
            # TODO add docstring
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

        def group_params(group):
            # TODO add docstring
            params = [modifier_param(m)
                      for m in self.human.getModifiersByGroup(group)]
            return params

        def build_macro_frame():
            # TODO rename to indicate private function
            # Shorten human reference for convenience
            human = self.human

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
            macro_model = SliderEntryPanelModel(macro_params)

            # Separate set of race parameters to also be included in the Macros group
            # TODO make race parameters automatically normalize in UI
            race_params = (
                Param("African", human.setAfrican),
                Param("Asian", human.setAsian),
                Param("Caucasian", human.setCaucasian),
            )
            # Create a model for storing race parameter data
            race_model = SliderEntryPanelModel(race_params)

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
                    g for g in self.human.modifierGroups if "macrodetails" in g]
                macrogroups = set(macrogroups)

                # Remove macro groups from list of modifier groups as we have already
                # included them explicitly
                allgroups = set(
                    self.human.modifierGroups).difference(macrogroups)

                for group in allgroups:
                    # Create a collapseable frame for each modifier group
                    with ui.CollapsableFrame(group.capitalize(), style=styles.frame_style, collapsed=True):
                        # Model to hold panel parameters
                        model = SliderEntryPanelModel(group_params(group))
                        self.models.append(model)
                        # Create panel of slider entries for modifier group
                        SliderEntryPanel(model)

    def destroy(self):
        super().destroy()
        for model in self.models:
            model.destroy()

class ButtonPanel:
    def __init__(self, mhcaller, **kwargs):
        # Include instance of Makehuman wrapper class
        self.mh_call = mhcaller
        # Model to store whether changes should happen immediately
        self.toggle = ui.SimpleBoolModel()

        # Pass **kwargs to buildwidget so we can apply styling as though ButtonPanel
        # extended a base ui class
        self._build_widget(**kwargs)

    def _build_widget(self, **kwargs):
        with ui.VStack(**kwargs):
            # Widget to list applied proxies TODO change to "Currently Applied Assets"
            self.drop = DropList("Currently Applied Proxies", self.mh_call)
            with ui.HStack(height=0):
                # Toggle whether changes should propagate instantly
                ui.Label("Update Instantly")
                ui.CheckBox(self.toggle)
            # Updates current human in omniverse scene
            ui.Button(
                "Update in Scene",
                height=50,
                clicked_fn=lambda: mh_usd.add_to_scene(self.mh_call),
            )

            # Creates a new human in scene and resets modifiers and assets
            ui.Button(
                "New Human",
                height=50,
                clicked_fn=lambda: self.new_human(),
            )

    def new_human(self):

        # Reset the human object in the makehuman wrapper. Also flags the human for
        # name change to avoid overwriting existing humans
        self.mh_call.reset_human()

        # Add the new, now reset human to the scene
        mh_usd.add_to_scene(self.mh_call)

    def destroy(self):
        # No superclass to destroy, no models to destroy
        # TODO do we need to reference the DropList model for destruction?
        pass
