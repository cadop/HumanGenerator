import omni.ext
import omni.ui as ui
import carb
import carb.events
import omni
import siborg.create.human.mhusd as mhusd

# from .window import MHWindow, WINDOW_TITLE

class MakeHumanExtension(omni.ext.IExt):
    # # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # # this extension is located on filesystem.

    def on_startup(self, ext_id):

    #     # subscribe to stage events
    #     # see https://github.com/mtw75/kit_customdata_view
    #     self._usd_context = omni.usd.get_context()
    #     self._selection = self._usd_context.get_selection()
    #     self._human_selection_event = carb.events.type_from_string("siborg.create.human.human_selected")
        
    #     # subscribe to stage events
    #     self._events = self._usd_context.get_stage_event_stream()
    #     self._stage_event_sub = self._events.create_subscription_to_push(
    #         self._on_stage_event,
    #         name='human seletion changed',
    #         )

    #     # get message bus event stream so we can push events to the message bus
    #     self._bus = omni.kit.app.get_app().get_message_bus_event_stream()

    #     # create a model to hold the selected prim path
    #     self._selected_primpath_model = ui.SimpleStringModel("-")

    #     # Create a path for menu item to open the window
    #     self._menu_path = f"Window/{WINDOW_TITLE}"

    #     # create a window for the extension
        print("[siborg.create.human] HumanGeneratorExtension startup")
    #     self._window = None
    #     self._menu = omni.kit.ui.get_editor_menu().add_item(self._menu_path, self._on_menu_click, True)


    # def _on_menu_click(self, menu, toggled):
    #     """Handles showing and hiding the window from the 'Windows' menu."""
    #     if toggled:
    #         if self._window is None:
    #             self._window = MHWindow(WINDOW_TITLE, self._menu_path)
    #         else:
    #             self._window.show()
    #     else:
    #         if self._window is not None:
    #             self._window.hide()

    # def _on_stage_event(self, event):
    #     if event.type == int(omni.usd.StageEventType.SELECTION_CHANGED):
    #         self._on_selection_changed()

    # def _on_selection_changed(self):
    #     # get the current selection and stage
    #     selection = self._selection.get_selected_prim_paths()
    #     stage = self._usd_context.get_stage()
    #     print(f"== selection changed with {len(selection)} items")

    #     if selection and stage:
    #         if len(selection) > 0:
    #             path = selection[-1]
    #             print(path)
    #             self._selected_primpath_model.set_value(path)
    #             prim = stage.GetPrimAtPath(path)
    #             prim_kind = prim.GetTypeName()
    #             # If the selection is a human, push an event to the event stream with the prim as a payload
    #             # This event will be picked up by the window and used to update the UI
    #             if prim_kind == "SkelRoot" and prim.GetCustomDataByKey("human"):
    #                 carb.log_warn("Human selected")
    #                 self._bus.push(self._human_selection_event, payload={"prim_path": path})

        self._window = ui.Window("My Window", width=300, height=300)
        with self._window.frame:
            with ui.VStack():
                label = ui.Label("")
                

                def on_click():
                    mhusd.make_human()

                with ui.HStack():
                    ui.Button("Add", clicked_fn=on_click)

    def on_shutdown(self):
        print("[siborg.create.human] HumanGenerator shutdown")
    #     omni.kit.ui.get_editor_menu().remove_item(self._menu)
    #     if self._window is not None:
    #         self._window.destroy()
    #         self._window = None
    #     # unsubscribe from stage events
    #     self._stage_event_sub = None

