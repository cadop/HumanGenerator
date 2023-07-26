from pathlib import Path
import os
from typing import Callable
import carb
import aiohttp
import omni.client
import os, zipfile
from omni.kit import pipapi
import asyncio

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
        self.tasks = []
        self.task_progresses = []

    def make_progress_fn(self, i : int):
        """Create a progress function that reports the total progress of each task"""        
        def total_progress_fn(progress):
            self.task_progresses[i] = progress

        return total_progress_fn

    async def report_total_progress(self):
        while any(task_progress < 1 for task_progress in self.task_progresses):
            self._log_fn(sum(self.task_progresses) / (len(self.task_progresses) or 1))
            await asyncio.sleep(1)

    async def run_tasks(self):
        asyncio.ensure_future(self.report_total_progress())
        task_coroutines = [
            task(self.make_progress_fn(i)) for i, task in enumerate(self.tasks)
        ]
        return await asyncio.gather(*task_coroutines)

    async def download(self, url : str, dest_url : str, unzip = True, log_fn = None) -> None:
        """Download a given url to disk and unzip it

        Parameters
        ----------
        url : str
            Remote URL to fetch
        dest_url : str
            Local path at which to write and then unzip the downloaded files
        unzip : bool, optional
            Whether to attempt to unzip the downloaded files, by default True
        log_func : Callable[[float], None], optional
            Function to which to pass progress. Recieves a proportion that represents the amount downloaded
            uses the default log function if not provided

        Returns
        -------
        dict of  str, Union[omni.client.Result, str]
            Error message and location on disk
        """

        
        log_fn = log_fn or self._log_fn

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
                        if log_fn:
                            log_fn(float(downloaded) / size)
                else:
                    if log_fn:
                        log_fn(0)
                    content = await response.read()
                    if log_fn:
                        log_fn(1)

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

    async def pip_install(self, url:str, package:str = None, log_fn=None, **kwargs):
        """Install a package from a given url using pip

        Parameters
        ----------
        url : str
            URL to fetch
        package : str, optional
            Name of the package to install, by default None
        """

        log_fn = log_fn or self._log_fn

        # Let the user know we're installing
        log_fn(0.10)
        ret_value = pipapi.install(url, package, **kwargs)
        log_fn(1)
        return  ret_value
    
    def enqueue_download(self, url : str, dest_url : str, unzip = True):
        """Enqueue a download task

        Parameters
        ----------
        url : str
            Remote URL to fetch
        dest_url : str
            Local path at which to write and then unzip the downloaded files
        unzip : bool, optional
            Whether to attempt to unzip the downloaded files, by default True
        """
        self.tasks.append(lambda log_fn: self.download(url, dest_url, unzip, log_fn=log_fn))
        self.task_progresses.append(0)

    def enqueue_install(self, url: str, **kwargs):
        """Enqueue a pip install task

        Parameters
        ----------
        url : str
            URL to fetch
        """
        self.tasks.append(lambda log_fn: self.pip_install(url, log_fn=log_fn,
                                                          ignore_cache=False,
                                                          use_online_index=True,
                                                          **kwargs))
        self.task_progresses.append(0)

    def not_downloading(self):
        return not self._is_downloading