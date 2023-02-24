from .ext_ui import DropListModel, DropList, ParamPanelModel, ParamPanel
from .browser import MHAssetBrowserModel, AssetBrowserFrame
from .human import Human
from .styles import window_style
import omni.ui as ui
import omni.kit.ui
import omni
import carb

WINDOW_TITLE = "Human Generator"
class MHWindow(ui.Window):
    """
    Main UI window. Contains all UI widgets. Extends omni.ui.Window.

    Attributes
    -----------
    panel : HumanPanel
        A widget that includes panels for modifiers, listing/removing applied
        proxies, and executing human creation and updates
    browser: AssetBrowserFrame
        A browser for MakeHuman assets, including clothing, hair, and skeleton rigs.
    """

    def __init__(self, title, menu_path):
        """Constructs an instance of MHWindow
        
        Parameters
        ----------
        menu_path : str
            The path to the menu item that opens the window
        """

        super().__init__(title)

        self._menu_path = menu_path

        # Holds the state of the realtime toggle
        self.toggle_model = ui.SimpleBoolModel()
        # Holds the state of the parameter list
        self.param_model = ParamPanelModel(self.toggle_model)
        # Keep track of the human
        self._human = Human()

        # A model to hold browser data
        self.browser_model = MHAssetBrowserModel(
            self._human,
            filter_file_suffixes=["mhpxy", "mhskel", "mhclo"],
            timeout=carb.settings.get_settings().get(
                "/exts/siborg.create.human.browser.asset/data/timeout"
            ),
        )

        # Dock UI wherever the "Content" tab is found (bottom panel by default)
        self.deferred_dock_in(
            "Content", ui.DockPolicy.CURRENT_WINDOW_IS_ACTIVE)

        # Subscribe to human selection events on the message bus
        bus = omni.kit.app.get_app().get_message_bus_event_stream()
        selection_event = carb.events.type_from_string("siborg.create.human.human_selected")
        self._selection_sub = bus.create_subscription_to_push_by_type(selection_event, self._on_human_selected)

        # Run when visibility changes
        self.set_visibility_changed_fn(self._on_visibility_changed)

        self.frame.set_build_fn(self._build_ui)

    def _build_ui(self):
        spacer_width = 5
        with self.frame:
            # Widgets are built starting on the left
            with ui.HStack(style=window_style):
                with ui.ZStack(width=0):
                    # Draggable splitter
                    with ui.Placer(offset_x=self.frame.computed_content_width/1.8, draggable=True, drag_axis=ui.Axis.X):
                        ui.Rectangle(width=5, name="splitter")
                    with ui.HStack():
                        # Left-most panel is a browser for MakeHuman assets. It includes
                        # a reference to the list of applied proxies so that an update
                        # can be triggered when new assets are added
                        self.browser = AssetBrowserFrame(self.browser_model)
                        ui.Spacer(width=spacer_width)
                with ui.HStack():
                    with ui.VStack():
                        self.param_panel = ParamPanel(self.param_model, lambda: self.update_human())
                        with ui.HStack(height=0):
                            # Toggle whether changes should propagate instantly
                            ui.Label("Update Instantly")
                            ui.CheckBox(self.toggle_model)
                with ui.VStack(width = 100):
                    # Creates a new human in scene and resets modifiers and assets
                    ui.Button(
                        "New Human",
                        clicked_fn=self.new_human,
                    )
                    # Updates current human in omniverse scene
                    ui.Button(
                        "Update Human",
                        clicked_fn=lambda: self.update_human(),
                    )

    def _on_human_selected(self, event):
        """Callback for human selection events

        Parameters
        ----------
        event : carb.events.Event
            The event that was pushed to the event stream. Contains payload data with
            the selected prim path
        """

        # Get the stage
        stage = omni.usd.get_context().get_stage()

        # Get the prim from the path in the event payload
        prim = stage.GetPrimAtPath(event.payload["prim_path"])

        # Update the human in MHCaller
        self._human.set_prim(prim)

        # Update the list of applied proxies stored in the list model
        self.proxy_list.model.update()
        # Update the list of applied modifiers
        self.param_panel.load_values(prim)

    def new_human(self):
        """Creates a new human in the scene and selects it"""
        
        # Reset the human class
        self._human.reset()

        # Create a new human
        self._human.prim = self._human.add_to_scene()

        # Get selection.
        selection = omni.usd.get_context().get_selection()
        # Select the new human.
        selection.set_selected_prim_paths([self._human.prim_path], True)

    def update_human(self):
        """Updates the current human in the scene"""
        # Apply any changed parameters to the human
        self.param_panel.update_models()

        # Update the human in the scene
        self._human.update_in_scene(self._human.prim_path)

    def destroy(self):
        """Called when the window is destroyed. Unsuscribes from human selection events"""
        self._selection_sub.unsubscribe()
        self._selection_sub = None
        super().destroy()

    def on_shutdown(self):
        """Called when the extension is shutting down"""
        self._win=None

    def _on_visibility_changed(self, visible):
        omni.kit.ui.get_editor_menu().set_value(self._menu_path, visible)

    def show(self):
        self.visible = True
        self.focus()
        
    def hide(self):
        self.visible = False