from .ext_ui import DropListModel, DropList, ParamPanelModel, ParamPanel
from .browser import MHAssetBrowserModel, AssetBrowserFrame
from .human import Human
from .styles import window_style
import omni.ui as ui
import omni
import carb


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

    def __init__(self, *args, **kwargs):
        """Constructs an instance of MHWindow"""
        super().__init__(*args, **kwargs)
        # Holds the state of the realtime toggle
        self.toggle_model = ui.SimpleBoolModel()
        # Holds the state of the proxy list
        self.list_model = DropListModel()
        # Holds the state of the parameter list
        self.param_model = ParamPanelModel(self.toggle_model)
        # A model to hold browser data
        self.browser_model = MHAssetBrowserModel(
            self.list_model,
            filter_file_suffixes=["mhpxy", "mhskel", "mhclo"],
            timeout=carb.settings.get_settings().get(
                "/exts/siborg.create.human.browser.asset/data/timeout"
            ),
        )

        # Keep track of the human and human prim path
        self._human = Human()
        self._human_prim_path = ""

        # Dock UI wherever the "Content" tab is found (bottom panel by default)
        self.deferred_dock_in(
            "Content", ui.DockPolicy.CURRENT_WINDOW_IS_ACTIVE)

        # Subscribe to human selection events on the message bus
        bus = omni.kit.app.get_app().get_message_bus_event_stream()
        selection_event = carb.events.type_from_string("siborg.create.human.human_selected")
        self._selection_sub = bus.create_subscription_to_push_by_type(selection_event, self._on_human_selected)

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
                with ui.ZStack(width=0):
                    # Draggable splitter
                    with ui.Placer(offset_x=self.frame.computed_content_width/4, draggable=True, drag_axis=ui.Axis.X):
                        ui.Rectangle(width=5, name="splitter")
                    with ui.HStack():
                        self.param_panel = ParamPanel(self.param_model, lambda: self._human.update_in_scene(self._human_prim_path))
                        ui.Spacer(width=spacer_width)
                with ui.VStack():
                    self.proxy_list = DropList(
                        "Currently Applied Assets", self.list_model)
                    with ui.HStack(height=0):
                        # Toggle whether changes should propagate instantly
                        ui.Label("Update Instantly")
                        ui.CheckBox(self.toggle_model)
                    # Creates a new human in scene and resets modifiers and assets
                    ui.Button(
                        "New Human",
                        height=50,
                        clicked_fn=self.new_human,
                    )
                    # Updates current human in omniverse scene
                    ui.Button(
                        "Update Selected Human",
                        height=50,
                        clicked_fn=lambda: self._human.update_in_scene(self._human_prim_path),
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

        # Update the human prim path
        self._human_prim_path = event.payload["prim_path"]

        # Update the list of applied proxies stored in the list model
        self.proxy_list.model.update()
        # Update the list of applied modifiers
        self.param_panel.load_values(prim)

    def new_human(self):
        """Creates a new human in the scene and selects it"""
        
        # Reset the human class
        self._human.reset()

        # Create a new human
        self._human_prim_path = self._human.add_to_scene()
        # Get selection.
        selection = omni.usd.get_context().get_selection()
        # Select the new human.
        selection.set_selected_prim_paths([self._human_prim_path], True)

    def destroy(self):
        """Called when the window is destroyed. Unsuscribes from human selection events"""
        self._selection_sub.unsubscribe()
        self._selection_sub = None
        super().destroy()
