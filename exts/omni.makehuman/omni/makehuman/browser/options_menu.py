from typing import Optional, Callable
from omni.kit.browser.core import OptionMenuDescription, OptionsMenu
from omni.kit.browser.folder.core.models.folder_browser_item import FolderCollectionItem
import omni.client, carb
import aiohttp, asyncio
import os, zipfile
from ..shared import data_path

class FolderOptionsMenu(OptionsMenu):
    """
    Represent options menu used in material browser. 
    """

    def __init__(self):
        super().__init__()
        self.dest_url = data_path("")
        self.url = "https://download.tuxfamily.org/makehuman/asset_packs/makehuman_system_assets/makehuman_system_assets.zip"
        self._download_menu_desc = OptionMenuDescription(
            "Download Assets",
            clicked_fn=self._on_download_assets,
            get_text_fn=self._get_menu_item_text,
        )
        self.append_menu_item(self._download_menu_desc)

    def destroy(self) -> None:
        super().destroy()

    def _get_menu_item_text(self) -> str:
        # Show download state if download starts
        return "Download Assets"

    def _on_download_assets(self):
        loop = asyncio.get_event_loop()
        asyncio.run_coroutine_threadsafe(self._download(), loop)

    def on_progress_fn(self, proportion : float):
        carb.log_info(f"Download is {int(proportion * 100)}% done")

    async def _download(self) -> None:
        ret_value = {"url": None}
        async with aiohttp.ClientSession() as session:
            content = bytearray()
            # Download content from the given url
            downloaded = 0
            async with session.get(self.url) as response:
                size = int(response.headers.get("content-length", 0))
                if size > 0:
                    async for chunk in response.content.iter_chunked(1024 * 512):
                        content.extend(chunk)
                        downloaded += len(chunk)
                        if self.on_progress_fn:
                            self.on_progress_fn(float(downloaded) / size)
                else:
                    if self.on_progress_fn:
                        self.on_progress_fn(0)
                    content = await response.read()
                    if self.on_progress_fn:
                        self.on_progress_fn(1)

            if response.ok:
                # Write to destination
                filename = os.path.basename(self.url.split("?")[0])
                self.dest_url = f"{self.dest_url}/{filename}"
                (result, list_entry) = await omni.client.stat_async(self.dest_url)
                ret_value["status"] = await omni.client.write_file_async(self.dest_url, content)
                ret_value["url"] = self.dest_url
                if  ret_value["status"] == omni.client.Result.OK:
                    # TODO handle file already exists
                    pass
                z = zipfile.ZipFile(self.dest_url, 'r')
                z.extractall(os.path.dirname(self.dest_url))
                self.refresh_collection()
            else:
                carb.log_error(f"[access denied: {self.url}")
                ret_value["status"] = omni.client.Result.ERROR_ACCESS_DENIED
        return ret_value

    def refresh_collection(self):
        collection_item: FolderCollectionItem = self._browser_widget.collection_selection
        if collection_item:
            collection_item.folder._timeout = 10
            collection_item.folder.start_traverse()