import os
import carb.settings
import omni.ui as ui
from omni.kit.browser.folder.core import FolderBrowserWidget
from .delegate import AssetDetailDelegate
from .model import MHAssetBrowserModel


class AssetBrowserFrame(ui.Frame):
    """
    Represent a window to show Assets
    """

    def __init__(self, mhcaller, list_widget, **kwargs):
        # TODO add docstring
        super().__init__(**kwargs)
        self.mh_call = mhcaller
        self.list_widget = list_widget
        self.set_build_fn(self._build_widget)

    def _build_widget(self):
        # TODO add docstring
        # A model to hold browser data
        self._browser_model = MHAssetBrowserModel(
            self.mh_call,
            self.list_widget,
            filter_file_suffixes=["mhpxy", "mhskel"],
            timeout=carb.settings.get_settings().get(
                "/exts/omni.makehuman.browser.asset/data/timeout"
            ),
        )
        # The delegate to execute browser actions
        self._delegate = AssetDetailDelegate(self._browser_model)

        # TODO does this need to be in a vstack?
        with ui.VStack(spacing=15):
            # Create the widget
            self._widget = FolderBrowserWidget(
                self._browser_model, detail_delegate=self._delegate
            )
