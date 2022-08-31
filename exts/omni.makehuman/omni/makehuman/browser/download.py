import carb
import aiohttp
import carb
import carb.input
import omni.kit.app
import omni.usd
import omni.ext
from typing import Callable, Dict
import zipfile
import os

class Downloader:

    async def __init__(self, download_url, dest_url: str, unzip : bool = True, on_progress_fn: Callable[[float], None] = None) -> Dict:
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