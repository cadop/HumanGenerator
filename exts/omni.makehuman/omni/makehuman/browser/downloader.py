from typing import Callable
import carb
import aiohttp
import omni.client
import os, zipfile


class Downloader:

    def __init__(self, log_fn : Callable[[float, float], None]) -> None:
        self._is_downloading = False
        self._log_fn = log_fn

    async def download(self, url : str, dest_url : str) -> None:
        ret_value = {"url": None}
        async with aiohttp.ClientSession() as session:
            self._is_downloading = True
            content = bytearray()
            # Download content from the given url
            downloaded = 0
            async with session.get(url) as response:
                size = int(response.headers.get("content-length", 0))
                if size > 0:
                    async for chunk in response.content.iter_chunked(1024 * 512):
                        content.extend(chunk)
                        downloaded += len(chunk)
                        if self._log_fn:
                            self._log_fn(float(downloaded) / size)
                else:
                    if self._log_fn:
                        self._log_fn(0)
                    content = await response.read()
                    if self._log_fn:
                        self._log_fn(1)

            if response.ok:
                # Write to destination
                filename = os.path.basename(url.split("?")[0])
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
                carb.log_error(f"[access denied: {url}")
                ret_value["status"] = omni.client.Result.ERROR_ACCESS_DENIED
        self._is_downloading = False
        return ret_value

    def not_downloading(self):
        return not self._is_downloading