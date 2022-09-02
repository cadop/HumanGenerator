from typing import Optional, Callable
from omni.kit.browser.core import OptionMenuDescription, OptionsMenu
from omni.kit.browser.folder.core.models.folder_browser_item import FolderCollectionItem
import omni.client, carb
import aiohttp, asyncio
import os, zipfile
from ..shared import data_path
from .downloader import Downloader
class FolderOptionsMenu(OptionsMenu):
    """
    Represent options menu used in material browser. 
    """

    def __init__(self):
        super().__init__()
        self.downloader = Downloader(self.log_fn, )
        self._download_menu_desc = OptionMenuDescription(
            "Download Assets",
            clicked_fn=self._on_download_assets,
            get_text_fn=self._get_menu_item_text,
            enabled_fn=self.downloader.not_downloading
        )
        self.append_menu_item(self._download_menu_desc)

    def destroy(self) -> None:
        super().destroy()

    def log_fn(self, proportion : float):
        carb.log_info(f"Download is {int(proportion * 100)}% done")

    def _get_menu_item_text(self) -> str:
        # Show download state if download starts
        if self.downloader._is_downloading:
            return "Download In Progress"
        return "Download Assets"

    def _on_download_assets(self):
        loop = asyncio.get_event_loop()
        asyncio.run_coroutine_threadsafe(self._download(), loop)

    async def _download(self):
        # Makehuman system assets
        url = "https://download.tuxfamily.org/makehuman/asset_packs/makehuman_system_assets/makehuman_system_assets.zip"
        # Smaller zip for testing
        # url = "https://download.tuxfamily.org/makehuman/asset_packs/shirts03/shirts03_ccby.zip"
        dest_url = data_path("")
        await self.downloader.download(url, dest_url)
        self.refresh_collection()

    def refresh_collection(self):
        collection_item: FolderCollectionItem = self._browser_widget.collection_selection
        if collection_item:
            collection_item.folder._timeout = 10
            collection_item.folder.start_traverse()