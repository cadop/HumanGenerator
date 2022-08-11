import omni.ui as ui
from . import mhcaller
from .ui_widgets import HumanPanel
from .browser import AssetBrowserWindow


class MHWindow(ui.Window):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.deferred_dock_in("Content", ui.DockPolicy.CURRENT_WINDOW_IS_ACTIVE)

        self.frame.set_build_fn(self._build_ui)

    def _build_ui(self):
        # Create instance of manager class
        mh_call = mhcaller.MHCaller()
        mh_call.filepath = "D:/human.obj"

        with self.frame:
            with ui.HStack(spacing=2):
                AssetBrowserWindow(mh_call)
                HumanPanel(mh_call)
