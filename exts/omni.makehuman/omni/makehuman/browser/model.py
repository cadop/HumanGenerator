import os
from typing import List, Union
import carb.settings
import omni.kit.commands
import omni.usd
from omni.kit.browser.core import DetailItem
from omni.kit.browser.folder.core import (
    FolderBrowserModel,
    FileDetailItem,
    BrowserFile,
)


class AssetDetailItem(FileDetailItem):
    """
    Represent material detail item
    Args:
        file (BrowserFile): BrowserFile object to create detail item
    """

    def __init__(self, file: BrowserFile):
        dirs = file.url.split("/")
        name = dirs[-1]
        super().__init__(name, file.url, file, file.thumbnail)


class MHAssetBrowserModel(FolderBrowserModel):
    """
    Represent asset browser model
    """

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            setting_folders="/exts/omni.makehuman.browser.asset/folders",
            show_category_subfolders=True,
            hide_file_without_thumbnails=False,
            **kwargs,
        )

    def execute(self, item: DetailItem) -> None:
        # Create a Reference of the Props in the stage
        stage = omni.usd.get_context().get_stage()
        if not stage:
            return

        name = item.name_model.as_string.split(".")[0]

        prim_path = omni.usd.get_stage_next_free_path(stage, "/" + name, True)

        omni.kit.commands.execute(
            "CreateReferenceCommand",
            path_to=prim_path,
            asset_path=item.url,
            usd_context=omni.usd.get_context(),
        )

    # Overwrite parent function to add thumbnails
    def create_detail_item(
        self, file: BrowserFile
    ) -> Union[FileDetailItem, List[FileDetailItem]]:
        """
        Create detail item(s) from a file.
        A file may includs multi detail items.
        Args:
            file (BrowserFile): File object to create detail item(s)
        """
        dirs = file.url.split("/")
        name = dirs[-1]

        filename_noext = os.path.splitext(file.url)[0]
        thumb = filename_noext + ".thumb"
        thumb_png = filename_noext + ".png"

        if os.path.exists(thumb_png):
            thumb = thumb_png
        elif os.path.exists(thumb):
            os.rename(thumb, thumb_png)
            thumb = thumb_png
        else:
            thumb = None

        return FileDetailItem(name, file.url, file, thumb)
