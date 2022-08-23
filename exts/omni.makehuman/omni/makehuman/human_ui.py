from omni.makehuman.mhcaller import modifier_image
import omni.ui as ui
from .ui_widgets import *
from .styles import *
from . import mh_usd

# class HumanPanel(ui.Frame):
class HumanPanel:
    def __init__(self, mhcaller, **kwargs):
        # super().__init__(width=0, **kwargs)
        self.mh_call = mhcaller

        # self.set_build_fn(self._build_widget)
        self._build_widget()

    def _build_widget(self):
        human = self.mh_call.human
        with ui.HStack():
            self.params = ParamPanel(human, width=300)
            self.buttons = ButtonPanel(self.mh_call, width=200)

    def destroy(self):
        # super().destroy()
        self.params.destroy()
        self.buttons.destroy()


class ParamPanel(ui.Frame):
    def __init__(self, human, **kwargs):
        super().__init__(**kwargs)
        self.human = human
        self.models = []
        self.set_build_fn(self._build_widget)

    # def _build_widget(self):
    #     human = self.human
    #     macro_params = (
    #         Param("Gender", human.setGender),
    #         Param("Age", human.setAge),
    #         Param("Muscle", human.setMuscle),
    #         Param("Weight", human.setWeight),
    #         Param("Height", human.setHeight),
    #         Param("Proportions", human.setBodyProportions),
    #     )
    #     macro_model = SliderEntryPanelModel(macro_params)
    #     race_params = (
    #         Param("African", human.setAfrican),
    #         Param("Asian", human.setAsian),
    #         Param("Caucasian", human.setCaucasian),
    #     )
    #     race_model = SliderEntryPanelModel(race_params)

    #     with ui.ScrollingFrame():
    #         with ui.CollapsableFrame(
    #             "Main", style=styles.frame_style, height=0
    #         ):
    #             with ui.VStack():
    #                 self.panels = (
    #                     SliderEntryPanel("Macrodetails", macro_model),
    #                     SliderEntryPanel("Race", race_model),
    #                 )

    def _build_widget(self):
        def modifier_param(m):
            tlabel = m.name.split("-")
            if "|" in tlabel[len(tlabel) - 1]:
                tlabel = tlabel[:-1]
            if len(tlabel) > 1 and tlabel[0] == m.groupName:
                label = tlabel[1:]
            else:
                label = tlabel
            label = " ".join([word.capitalize() for word in label])

            # Guess a suitable image path from target name
            tlabel = m.name.replace("|", "-").split("-")
            image = modifier_image(("%s.png" % "-".join(tlabel)).lower())
            return Param(
                label,
                m.updateValue,
                image=image,
                min=m.getMin(),
                max=m.getMax(),
                default=m.getDefaultValue(),
            )

        def group_params(group):
            params = [modifier_param(m) for m in self.human.getModifiersByGroup(group)]
            return params

        def build_macro_frame():
            human = self.human
            macro_params = (
                Param("Gender", human.setGender),
                Param("Age", human.setAge),
                Param("Muscle", human.setMuscle),
                Param("Weight", human.setWeight),
                Param("Height", human.setHeight),
                Param("Proportions", human.setBodyProportions),
            )
            macro_model = SliderEntryPanelModel(macro_params)
            race_params = (
                Param("African", human.setAfrican),
                Param("Asian", human.setAsian),
                Param("Caucasian", human.setCaucasian),
            )
            race_model = SliderEntryPanelModel(race_params)

            self.models.append(macro_model)
            self.models.append(race_model)

            with ui.CollapsableFrame("Macros", style=styles.frame_style, height=0):
                with ui.VStack():
                    self.panels = (
                        SliderEntryPanel(macro_model, label="General"),
                        SliderEntryPanel(race_model, label="Race"),
                    )

        with ui.ScrollingFrame():
            with ui.VStack():
                build_macro_frame()
                macrogroups = [g for g in self.human.modifierGroups if "macrodetails" in g]
                macrogroups = set(macrogroups)
                allgroups = set(self.human.modifierGroups).difference(macrogroups)
                for group in allgroups:
                    with ui.CollapsableFrame(group.capitalize(), style=styles.frame_style, collapsed=True):
                        model = SliderEntryPanelModel(group_params(group))
                        self.models.append(model)
                        SliderEntryPanel(model)

    def destroy(self):
        super().destroy()
        for model in self.models:
            model.destroy()

    # class ButtonPanel(ui.Frame):


class ButtonPanel:
    def __init__(self, mhcaller, **kwargs):
        # super().__init__(**kwargs)
        self.mh_call = mhcaller
        # self.set_build_fn(self._build_widget)
        self._build_widget(**kwargs)

    def _build_widget(self, **kwargs):
        with ui.VStack(**kwargs):
            self.drop = DropList("Currently Applied Proxies", self.mh_call)
            ui.Button(
                "Update in Scene",
                height=50,
                clicked_fn=lambda: mh_usd.add_to_scene(self.mh_call),
            )
            ui.Button(
                "New Human",
                height=50,
                clicked_fn=lambda: self.new_human(),
            )

    def new_human(self):
        self.mh_call.reset_human()
        mh_usd.add_to_scene(self.mh_call)

    def destroy(self):
        pass
        # super().destroy()
