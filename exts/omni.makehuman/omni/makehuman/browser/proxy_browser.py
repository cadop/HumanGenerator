import os
import carb.settings
from omni.makehuman.mhcaller import MHCaller
from omni.makehuman.ui_widgets import DropList
import omni.ui as ui
from omni.kit.browser.folder.core import FolderBrowserWidget
from .delegate import AssetDetailDelegate
from .model import MHAssetBrowserModel


class AssetBrowserFrame(ui.Frame):
    """A widget to browse and select Makehuman assets
    Attributes
    ----------
    mhcaller : MHCaller
        Wrapper object for Makehuman functions
    list_widget : DropList
        The widget in which to reflect changes when assets are added 
    """

    def __init__(self, mhcaller: MHCaller, list_widget: DropList, **kwargs):
        """Constructs an instance of AssetBrowserFrame. This is a browser that
        displays available Makehuman assets (skeletons/rigs, proxies) and allows
        a user to apply them to the human.

        Parameters
        ----------
        mhcaller : MHCaller
            Wrapper object for Makehuman functions
        list_widget : DropList
            The widget in which to reflect changes when assets are added 
        """
        super().__init__(**kwargs)
        self.mh_call = mhcaller
        self.list_widget = list_widget
        self.set_build_fn(self._build_widget)

    def _build_widget(self):
        """Build UI widget"""
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
