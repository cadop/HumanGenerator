import omni.ui as ui
from . import mhcaller
from .human_ui import HumanPanel
from .browser import AssetBrowserFrame
from .ui_widgets import *


class MHWindow(ui.Window):
    """
    Main UI window. Contains all UI widgets. Extends omni.ui.Window.

    Attributes
    -----------
    panel : HumanPanel
        A widget that includes anels for modifiers, listing/removing applied
        proxies, and executing human creation and updates
    browser: AssetBrowserFrame
        A browser for MakeHuman assets, including clothing, hair, and skeleton rigs.
    """
    

    def __init__(self, *args, **kwargs):
        """Constructs an instance of MHWindow"""

        super().__init__(*args, **kwargs)

        # Reference to UI panel for destructor
        self.panel = None
        # Reference to asset browser for destructor
        self.browser = None

        # Dock UI wherever the "Content" tab is found (bottom panel by default)
        self.deferred_dock_in(
            "Content", ui.DockPolicy.CURRENT_WINDOW_IS_ACTIVE)

        self.frame.set_build_fn(self._build_ui)

    def _build_ui(self):

        # Create instance of manager class
        mh_call = mhcaller.MHCaller()

        mh_call.filepath = "D:/human.obj"

        with self.frame:

            # Widgets are built starting on the right
            with ui.Stack(ui.Direction.RIGHT_TO_LEFT, spacing=2):

                # Right-most panel includes panels for modifiers, listing/removing
                # applied proxies, and executing Human creation and updates
                self.panel = HumanPanel(mh_call)

                # Left-most panel is a browser for MakeHuman assets. It includes
                # a reference to the list of applied proxies so that an update
                # can be triggered when new assets are added
                self.browser = AssetBrowserFrame(
                    mh_call, self.panel.buttons.drop.model
                )

    # Properly destroying UI elements and references prevents 'Zombie UI'
    # (abandoned objects that interfere with Kit)
    def destroy(self):
        """Destroys the instance of MHWindow
        """
        super().destroy()
        self.panel.destroy()
        self.browser.destroy()
