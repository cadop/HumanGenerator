import os
from typing import List, Union
import carb.settings
import omni.kit.commands
from omni.makehuman.mhcaller import MHCaller
from omni.makehuman.ui_widgets import DropList
import omni.usd
from omni.kit.browser.core import DetailItem
from omni.kit.browser.folder.core import (
    FolderBrowserModel,
    FileDetailItem,
    BrowserFile,
)
from omni.makehuman.shared import data_path


class AssetDetailItem(FileDetailItem):
    """
    Represents Makehuman asset detail item
    """

    def __init__(self, file: BrowserFile):
        """Constructor for AssetDetailItem

        Parameters
        ----------
        file : BrowserFile
            BrowserFile object to create detail item
        """
        dirs = file.url.split("/")
        name = dirs[-1]
        super().__init__(name, file.url, file, file.thumbnail)


class MHAssetBrowserModel(FolderBrowserModel):
    """
    Represents Makehuman asset browser model
    """

    def __init__(self, mhcaller: MHCaller, list_widget: DropList, *args, **kwargs):
        """Constructor for MHAssetBrowserModel

        Parameters
        ----------
        mhcaller : MHCaller
            Wrapper class for Makehuman functions
        list_widget : DropList
            The widget in which to reflect changes when assets are added to the
            human
        """
        self.mhcaller = mhcaller
        self.list_widget = list_widget
        super().__init__(
            *args,
            show_category_subfolders=True,
            hide_file_without_thumbnails=False,
            **kwargs,
        )
        # Add the data path as the root folder from which to build a collection
        super().append_root_folder(data_path(""), name="MakeHuman")
        # TODO make it so that the default collection cannot be removed

    # Overwrite parent function to add thumbnails
    def create_detail_item(
        self, file: BrowserFile
    ) -> Union[FileDetailItem, List[FileDetailItem]]:
        """Create detail item(s) from a file.
        A file may include multiple detail items.

        Parameters
        ----------
        file : BrowserFile
            File object to create detail item(s)

        Returns
        -------
        Union[FileDetailItem, List[FileDetailItem]]
            FileDetailItem or list of items created from file
        """

        dirs = file.url.split("/")
        name = dirs[-1]

        # Get the file name without the extension
        filename_noext = os.path.splitext(file.url)[0]

        thumb = filename_noext + ".thumb"
        thumb_png = filename_noext + ".png"

        # If there is already a PNG, get it. If not, rename the thumb file to a PNG
        # (They are the same format just with different extensions). This lets us
        # use Makehuman's asset thumbnails
        if os.path.exists(thumb_png):
            thumb = thumb_png
        elif os.path.exists(thumb):
            os.rename(thumb, thumb_png)
            thumb = thumb_png
        else:
            thumb = None

        return FileDetailItem(name, file.url, file, thumb)
