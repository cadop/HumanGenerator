import os
import carb.settings
import omni.ui as ui
from omni.kit.browser.folder.core import FolderBrowserWidget
from .delegate import AssetDetailDelegate
from .model import AssetBrowserModel


class AssetBrowserWindow(ui.Frame):
    """
    Represent a window to show Assets
    """

    def __init__(self, mhcaller, **kwargs):
        super().__init__(**kwargs)
        self.mh_call = mhcaller
        self.set_build_fn(self._build_widget)

    def _build_widget(self):
        self._browser_model = AssetBrowserModel(
            filter_file_suffixes=[".usd", ".usda", ".usdc"],
            timeout=carb.settings.get_settings().get(
                "/exts/omni.kit.browser.asset/data/timeout"
            ),
        )
        self._delegate = AssetDetailDelegate(self._browser_model)

        with ui.VStack(spacing=15):
            self._widget = FolderBrowserWidget(
                self._browser_model, detail_delegate=self._delegate
            )
