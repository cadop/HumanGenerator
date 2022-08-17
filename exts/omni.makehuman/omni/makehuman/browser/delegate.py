import carb
import omni.ui as ui
import omni.kit.app
from omni.kit.browser.core import get_legacy_viewport_interface
from omni.kit.browser.folder.core import FolderDetailDelegate
from .model import MHAssetBrowserModel, AssetDetailItem

import asyncio
from pathlib import Path
from typing import Optional

CURRENT_PATH = Path(__file__).parent
ICON_PATH = CURRENT_PATH.parent.parent.parent.parent.joinpath("icons")


class AssetDetailDelegate(FolderDetailDelegate):
    """
    Delegate to show asset item in detail view
    Args:
        model (AssetBrowserModel): Asset browser model
    """

    def __init__(self, model: MHAssetBrowserModel):
        super().__init__(model=model)
        self.model = model
        self.mhcaller = model.mhcaller
        self._dragging_url = None
        self._settings = carb.settings.get_settings()
        self._context_menu: Optional[ui.Menu] = None
        self._action_item: Optional[AssetDetailItem] = None

        self._viewport = None
        self._drop_helper = None

    def destroy(self):
        self._viewport = None
        self._drop_helper = None
        super().destroy()

    def get_thumbnail(self, item) -> str:
        """Set default sky thumbnail if thumbnail is None"""
        if item.thumbnail is None:
            return f"{ICON_PATH}/usd_stage_256.png"
        else:
            return item.thumbnail

    def on_drag(self, item: AssetDetailItem) -> str:
        """Could be dragged to viewport window"""
        thumbnail = self.get_thumbnail(item)
        icon_size = 128
        with ui.VStack(width=icon_size):
            if thumbnail:
                ui.Spacer(height=2)
                with ui.HStack():
                    ui.Spacer()
                    ui.ImageWithProvider(
                        thumbnail, width=icon_size, height=icon_size
                    )
                    ui.Spacer()
            ui.Label(
                item.name,
                word_wrap=False,
                elided_text=True,
                skip_draw_when_clipped=True,
                alignment=ui.Alignment.TOP,
                style_type_name_override="GridView.Item",
            )
        return item.url

    def on_double_click(self, item):
        self.model.list_widget.add_child(item.url)
