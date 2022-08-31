from typing import Optional, Callable
from omni.kit.browser.core import OptionMenuDescription, OptionsMenu
from omni.kit.browser.folder.core.models.folder_browser_item import FolderCollectionItem
import omni.client, carb
import aiohttp
import os, zipfile
class FolderOptionsMenu(OptionsMenu):
    """
    Represent options menu used in material browser. 
    """

    def __init__(self):
        super().__init__()

        self._download_menu_desc = OptionMenuDescription(
            "Download Assets",
            clicked_fn=lambda a: self._on_download_assets(),
            get_text_fn=self._get_menu_item_text,
        )
        self.append_menu_item(self._download_menu_desc)

    def destroy(self) -> None:
        super().destroy()

    def _get_menu_item_text(self) -> str:
        # Show download state if download starts
        return "Download Assets"

    async def _on_download_assets(self, download_url : str, on_progress_fn: Callable[[float], None] = None) -> None:
        ret_value = {"url": None}
        async with aiohttp.ClientSession() as session:
            content = bytearray()
            # Download content from the given url
            downloaded = 0
            async with session.get(download_url) as response:
                size = int(response.headers.get("content-length", 0))
                if size > 0:
                    async for chunk in response.content.iter_chunked(1024 * 512):
                        content.extend(chunk)
                        downloaded += len(chunk)
                        if on_progress_fn:
                            on_progress_fn(float(downloaded) / size)
                else:
                    if on_progress_fn:
                        on_progress_fn(0)
                    content = await response.read()
                    if on_progress_fn:
                        on_progress_fn(1)

            if response.ok:
                # Write to destination
                filename = os.path.basename(download_url.split("?")[0])
                dest_url = f"{dest_url}/{filename}"
                (result, list_entry) = await omni.client.stat_async(dest_url)
                ret_value["status"] = await omni.client.write_file_async(dest_url, content)
                ret_value["url"] = dest_url
            else:
                carb.log_error(f"[access denied: {download_url}")
                ret_value["status"] = omni.client.Result.ERROR_ACCESS_DENIED
        z = zipfile.ZipFile(result)
        return z.extractall(), ret_value
