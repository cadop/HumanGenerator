import os
from typing import List
import carb.settings
import omni.kit.commands
import omni.usd
from omni.kit.browser.core import DetailItem
from omni.kit.browser.folder.core import FolderBrowserModel, FileDetailItem, BrowserFile


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


class AssetBrowserModel(FolderBrowserModel):
    """
    Represent asset browser model
    """

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            setting_folders="/exts/omni.kit.browser.asset/folders",
            show_category_subfolders=True,
            hide_file_without_thumbnails=True,
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
            "CreateReferenceCommand", path_to=prim_path, asset_path=item.url, usd_context=omni.usd.get_context()
        )
