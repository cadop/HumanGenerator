import omni.ext
import omni.ui as ui
import carb
import carb.events
import omni

from .window import MHWindow, WINDOW_TITLE

class MakeHumanExtension(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.

    def on_startup(self, ext_id):

        # subscribe to stage events
        # see https://github.com/mtw75/kit_customdata_view
        self._usd_context = omni.usd.get_context()
        self._selection = self._usd_context.get_selection()
        self._human_selection_event = carb.events.type_from_string("siborg.create.human.human_selected")
        
        # subscribe to stage events
        self._events = self._usd_context.get_stage_event_stream()
        self._stage_event_sub = self._events.create_subscription_to_push(
            self._on_stage_event,
            name='human seletion changed',
            )

        # get message bus event stream so we can push events to the message bus
        self._bus = omni.kit.app.get_app().get_message_bus_event_stream()

        # create a model to hold the selected prim path
        self._selected_primpath_model = ui.SimpleStringModel("-")

        # create a window for the extension
        print("[siborg.create.human] HumanGeneratorExtension startup")
        self._window = MHWindow(WINDOW_TITLE)

    def _on_stage_event(self, event):
        if event.type == int(omni.usd.StageEventType.SELECTION_CHANGED):
            self._on_selection_changed()

    def _on_selection_changed(self):
        # get the current selection and stage
        selection = self._selection.get_selected_prim_paths()
        stage = self._usd_context.get_stage()
        print(f"== selection changed with {len(selection)} items")

        if selection and stage:
            if len(selection) > 0:
                path = selection[-1]
                print(path)
                self._selected_primpath_model.set_value(path)
                prim = stage.GetPrimAtPath(path)
                prim_kind = prim.GetTypeName()
                # If the selection is a human, push an event to the event stream with the prim as a payload
                # This event will be picked up by the window and used to update the UI
                if prim_kind == "SkelRoot" and prim.GetCustomDataByKey("human"):
                    carb.log_warn("Human selected")
                    self._bus.push(self._human_selection_event, payload={"prim_path": path})

    def on_shutdown(self):
        print("[siborg.create.human] HumanGenerator shutdown")
        self._window.destroy()
        self._window = None
        # unsubscribe from stage events
        self._stage_event_sub.unsubscribe()
        self._stage_event_sub = None