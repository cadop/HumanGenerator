import omni.ui as ui
from . import mhcaller
from .human_ui import ParamPanel, ParamPanelModel
from .browser import AssetBrowserFrame
from .ui_widgets import *
from .styles import window_style
from .browser import MHAssetBrowserModel

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
        self.mh_call = mhcaller.MHCaller()
        
        # Holds the state of the realtime toggle
        self.toggle_model = ui.SimpleBoolModel()

        # Holds the state of the proxy list
        self.list_model = DropListModel(self.mh_call)

        # Holds the state of the parameter list
        self.param_model = ParamPanelModel(self.mh_call, self.toggle_model)

        # A model to hold browser data
        self.browser_model = MHAssetBrowserModel(
            self.mh_call,
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



        self.mh_call.filepath = "D:/human.obj"



        
        with self.frame:

            # Widgets are built starting on the right
            with ui.HStack(style = window_style):
                with ui.ZStack(width=0):
                    # Draggable splitter
                    with ui.Placer(offset_x=800,draggable=True, drag_axis=ui.Axis.X):
                        ui.Rectangle(width=5, name="splitter")
                    with ui.HStack():
                        # Left-most panel is a browser for MakeHuman assets. It includes
                        # a reference to the list of applied proxies so that an update
                        # can be triggered when new assets are added
                        self.browser = AssetBrowserFrame(self.browser_model)
                        ui.Spacer(width=5)
                with ui.ZStack(width=0):
                    # Draggable splitter
                    with ui.Placer(offset_x=300,draggable=True, drag_axis=ui.Axis.X):
                        ui.Rectangle(width=5, name="splitter")
                    with ui.HStack():
                        self.param_panel = ParamPanel(self.param_model)
                        ui.Spacer(width=5)
                with ui.VStack():
                    self.proxy_list = DropList("Currently Applied Assets", self.list_model)
                    with ui.HStack(height=0):
                        # Toggle whether changes should propagate instantly
                        ui.Label("Update Instantly")
                        ui.CheckBox(self.toggle_model)
                    # Creates a new human in scene and resets modifiers and assets
                    ui.Button(
                        "New Human",
                        height=50,
                        clicked_fn=lambda: self.new_human(),
                    )
                    # Updates current human in omniverse scene
                    ui.Button(
                        "Update Human in Scene",
                        height=50,
                        clicked_fn=lambda: mh_usd.add_to_scene(self.mh_call, True),
                    )

    def new_human(self):
        """Creates a new human in the stage. Makes calls to the Makehuman function wrapper MHCaller for resetting the human parameters and assets as well as flagging the human for renaming. Then creates a new human in the stage with the reset data. 
        """
        # Reset the human object in the makehuman wrapper. Also flags the human for
        # name change to avoid overwriting existing humans
        self.mh_call.reset_human()
        # Reset list of applied assets
        self.list_model.update()
        # Reset list of modifiers
        self.param_panel.reset()
        # Add the new, now reset human to the scene
        mh_usd.add_to_scene(self.mh_call)



    # Properly destroying UI elements and references prevents 'Zombie UI'
    # (abandoned objects that interfere with Kit)
    def destroy(self):
        """Destroys the instance of MHWindow
        """
        super().destroy()