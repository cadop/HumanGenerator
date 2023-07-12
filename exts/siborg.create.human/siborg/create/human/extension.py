import omni.ext
import omni.ui as ui
import carb
import carb.events
import omni
from functools import partial
import asyncio

from .window import MHWindow, WINDOW_TITLE, MENU_PATH

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

        ui.Workspace.set_show_window_fn(WINDOW_TITLE, partial(self.show_window, None))

        # create a menu item to open the window
        editor_menu = omni.kit.ui.get_editor_menu()
        if editor_menu:
            self._menu = editor_menu.add_item(
                MENU_PATH, self.show_window, toggle=True, value=True
            )
        # show the window
        ui.Workspace.show_window(WINDOW_TITLE)
        print("[siborg.create.human] HumanGeneratorExtension startup")

    def on_shutdown(self):
        self._menu = None
        if self._window:
            self._window.destroy()
            self._window = None

        # Deregister the function that shows the window from omni.ui
        ui.Workspace.set_show_window_fn(WINDOW_TITLE, None)

    async def _destroy_window_async(self):
        # wait one frame, this is due to the one frame defer
        # in Window::_moveToMainOSWindow()
        await omni.kit.app.get_app().next_update_async()
        if self._window:
            self._window.destroy()
            self._window = None

    def visibility_changed(self, visible):
        # Called when window closed by user
        editor_menu = omni.kit.ui.get_editor_menu()
        # Update the menu item to reflect the window state
        if editor_menu:
            editor_menu.set_value(MENU_PATH, visible)
        if not visible:
            # Destroy the window, since we are creating new window
            # in show_window
            asyncio.ensure_future(self._destroy_window_async())

    def show_window(self, menu, value):
        """Handles showing and hiding the window"""
        if value:
            self._window = MHWindow(WINDOW_TITLE)
            # # Dock window wherever the "Content" tab is found (bottom panel by default)
            self._window.deferred_dock_in("Content", ui.DockPolicy.CURRENT_WINDOW_IS_ACTIVE)
            self._window.set_visibility_changed_fn(self.visibility_changed)
        elif self._window:
            self._window.visible = False

    def _on_stage_event(self, event):
        """Handles stage events. This is where we get notified when the user selects/deselects a prim in the viewport."""
        if event.type == int(omni.usd.StageEventType.SELECTION_CHANGED):
            # Get the current selection
            selection = self._selection.get_selected_prim_paths()

            # Check if the selection is empty
            if not selection:
                # Push an event to the message bus with "None" as a payload
                # This event will be picked up by the window and used to update the UI
                carb.log_warn("Human deselected")
                self._bus.push(self._human_selection_event, payload={"prim_path": None})
            else:
                # Get the stage
                stage = self._usd_context.get_stage()

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
