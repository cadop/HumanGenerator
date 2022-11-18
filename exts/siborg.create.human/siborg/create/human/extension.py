import omni.ext
import siborg.create.human
import omni.ui as ui
from .mhcaller import MHCaller
from .browser import AssetBrowserFrame
from .ext_ui import DropListModel, DropList, ParamPanelModel, ParamPanel
import carb
from .styles import window_style
from .browser import MHAssetBrowserModel
import omni
from .human import Human


class MakeHumanExtension(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.

    def on_startup(self, ext_id):
        print("[siborg.create.human] HumanGeneratorExtension startup")
        self._window = MHWindow("Human Generator")

    def on_shutdown(self):
        print("[siborg.create.human] HumanGenerator shutdown")
        self._window.destroy()
        self._window = None


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
        # Create instance of manager class
        self.mhcaller = MHCaller()
        # Holds the state of the realtime toggle
        self.toggle_model = ui.SimpleBoolModel()
        # Holds the state of the proxy list
        self.list_model = DropListModel(self.mhcaller)
        # Holds the state of the parameter list
        self.param_model = ParamPanelModel(self.mhcaller, self.toggle_model)
        # A model to hold browser data
        self.browser_model = MHAssetBrowserModel(
            self.mhcaller,
            self.list_model,
            filter_file_suffixes=["mhpxy", "mhskel", "mhclo"],
            timeout=carb.settings.get_settings().get(
                "/exts/siborg.create.human.browser.asset/data/timeout"
            ),
        )

        # Dock UI wherever the "Content" tab is found (bottom panel by default)
        self.deferred_dock_in(
            "Content", ui.DockPolicy.CURRENT_WINDOW_IS_ACTIVE)

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
                        self.param_panel = ParamPanel(self.param_model)
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
                    ## Updates current human in omniverse scene
                    # ui.Button(
                    #     "Update Meshes in Scene",
                    #     height=50,
                    #     clicked_fn=lambda: mh_usd.add_to_scene(self.mhcaller, True),
                    # )

    def new_human(self):
        """Creates a new human in the scene and selects it"""
        human = Human()
        prim_path = human.add_to_scene()
        # Get selection.
        selection = omni.usd.get_context().get_selection()
        # Select the new human.
        selection.set_selected_prim_paths([prim_path], True)
