from typing import Collection, Optional
from omni.kit.browser.core import OptionMenuDescription, OptionsMenu
from omni.kit.browser.folder.core.models.folder_browser_item import FolderCollectionItem
from .download import Downloader

class FolderOptionsMenu(OptionsMenu):
    """
    Represent options menu used in material browser. 
    """

    def __init__(self, dl : Downloader):
        super().__init__()
        self.dl = dl

        self._download_menu_desc = OptionMenuDescription(
            "Download Assets",
            clicked_fn=self._on_download_assets,
            visible_fn=lambda: self.dl is not None,
            get_text_fn=self._get_menu_item_text,
        )
        self.append_menu_item(self._download_menu_desc)

    def destroy(self) -> None:
        super().destroy()

    def _get_menu_item_text(self) -> str:
        # Show download state if download starts
        collection_item = self._browser_widget.collection_selection
        if collection_item:
            state = self._predownload_helper.get_download_state(collection_item.url)
            if state is not None:
                return "Download - " + state

        return "Download Assets"

    def _on_download_assets(self) -> None:
        pass
