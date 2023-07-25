from pathlib import Path
import os
from typing import Callable
import carb
import aiohttp
import omni.client
import os, zipfile

# Shared methods that are useful to several modules


def data_path(path):
    """Returns the absolute path of a path given relative to "exts/<omni.ext>/data"

    Parameters
    ----------
    path : str
        Relative path

    Returns
    -------
    str
        Absolute path
    """
    # Uses an absolute path, and then works its way up the folder directory to find the data folder
    data = os.path.join(str(Path(__file__).parents[3]), "data", path)
    return data


def sanitize(s: str):
    """Sanitize strings for use a prim names. Strips and replaces illegal
    characters.

    Parameters
    ----------
    s : str
        Input string

    Returns
    -------
    s : str
        Primpath-safe output string
    """
    # List of illegal characters
    # TODO create more comprehensive list
    # TODO switch from blacklisting illegal characters to whitelisting valid ones
    illegal = (".", "-")
    for c in illegal:
        # Replace illegal characters with underscores
        s = s.replace(c, "_")
    return s

class Downloader:
    """Downloads and unzips remote files and tracks download status/progress"""
    def __init__(self, log_fn : Callable[[float], None]) -> None:
        """Construct an instance of Downloader. Assigns the logging function and sets initial is_downloading status

        Parameters
        ----------
        log_fn : Callable[[float], None]
            Function to which to pass progress. Recieves a proportion that represents the amount downloaded
        """
        self._is_downloading = False
        self._log_fn = log_fn

    async def download(self, url : str, dest_url : str, unzip = True) -> None:
        """Download a given url to disk and unzip it

        Parameters
        ----------
        url : str
            Remote URL to fetch
        dest_url : str
            Local path at which to write and then unzip the downloaded files
        unzip : bool, optional
            Whether to attempt to unzip the downloaded files, by default True

        Returns
        -------
        dict of  str, Union[omni.client.Result, str]
            Error message and location on disk
        """

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
                dest_url = f"{dest_url}/{filename}"
                (result, list_entry) = await omni.client.stat_async(dest_url)
                ret_value["status"] = await omni.client.write_file_async(dest_url, content)
                ret_value["url"] = dest_url
                if  ret_value["status"] == omni.client.Result.OK:
                    # TODO handle file already exists
                    pass
                if unzip:
                    z = zipfile.ZipFile(dest_url, 'r')
                    z.extractall(os.path.dirname(dest_url))
            else:
                carb.log_error(f"[access denied: {url}")
                ret_value["status"] = omni.client.Result.ERROR_ACCESS_DENIED
        self._is_downloading = False
        return ret_value

    def not_downloading(self):
        return not self._is_downloading