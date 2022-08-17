import omni.ui as ui
from . import mhcaller
from .human_ui import HumanPanel
from .browser import AssetBrowserFrame
from .ui_widgets import *


class MHWindow(ui.Window):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.panel = None
        self.browser = None
        self.deferred_dock_in("Content", ui.DockPolicy.CURRENT_WINDOW_IS_ACTIVE)

        self.frame.set_build_fn(self._build_ui)

    def _build_ui(self):
        # Create instance of manager class
        mh_call = mhcaller.MHCaller()
        mh_call.filepath = "D:/human.obj"

        with self.frame:
            with ui.Stack(ui.Direction.RIGHT_TO_LEFT, spacing=2):
                self.panel = HumanPanel(mh_call)
                self.browser = AssetBrowserFrame(
                    mh_call, self.panel.buttons.drop.model
                )

    def destroy(self):
        super().destroy()
        self.panel.destroy()
        self.browser.destroy()
