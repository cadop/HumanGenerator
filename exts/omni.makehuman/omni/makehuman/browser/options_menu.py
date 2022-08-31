from typing import Collection, Optional
from omni.kit.browser.core import OptionMenuDescription, OptionsMenu
from omni.kit.browser.folder.core.models.folder_browser_item import FolderCollectionItem
from .predownload import PredownloadHelper


class FolderOptionsMenu(OptionsMenu):
    """
    Represent options menu used in material browser. 
    Args:
        predownload_folder (Optional[str]): Folder to predownload files and sub folders. Predownload is used to download items from remote folder to local when startup.
            Default None means no predowndload.
    """

    def __init__(self, predownload_folder: Optional[str]):
        super().__init__()

        self._predownload_helper = PredownloadHelper(predownload_folder) if predownload_folder else None
        self._refresh_collection_menu_desc = OptionMenuDescription(
            "Refresh Current Collection",
            clicked_fn=self._on_refresh_collection,
            visible_fn=self._is_refresh_collection_visible,
        )
        self.append_menu_item(self._refresh_collection_menu_desc)

        self._download_menu_desc = OptionMenuDescription(
            "Download Current Collection",
            clicked_fn=self._on_download_collection,
            enabled_fn=self._is_download_collection_enable,
            visible_fn=lambda: self._predownload_helper is not None,
            get_text_fn=self._get_menu_item_text,
        )

        self.append_menu_item(OptionMenuDescription("", visible_fn=lambda: self._predownload_helper is not None))
        self.append_menu_item(self._download_menu_desc)

    def destroy(self) -> None:
        super().destroy()
        if self._predownload_helper:
            self._predownload_helper.destroy()

    def _on_refresh_collection(self):
        collection_item: FolderCollectionItem = self._browser_widget.collection_selection
        if collection_item:
            if collection_item.folder.has_timeout:
                collection_item.folder._timeout = 10
                collection_item.folder.start_traverse()

    def _is_refresh_collection_visible(self) -> bool:
        collection_item: FolderCollectionItem = self._browser_widget.collection_selection
        if collection_item:
            if collection_item.folder.has_timeout:
                return True
        return False

    def _is_download_collection_enable(self):
        collection_item = self._browser_widget.collection_selection
        if collection_item:
            if self._is_remote_folder(collection_item.url):
                state = self._predownload_helper.get_download_state(collection_item.url)
                if state is None:
                    return True
                else:
                    # Disable if already start downloading
                    return False
            else:
                return False
        else:
            return False

    def _get_menu_item_text(self) -> str:
        # Show download state if download starts
        collection_item = self._browser_widget.collection_selection
        if collection_item:
            state = self._predownload_helper.get_download_state(collection_item.url)
            if state is not None:
                return "Download - " + state

        return "Download Current Collection"

    def _on_download_collection(self) -> None:
        collection_item = self._browser_widget.collection_selection
        if collection_item:
            self._predownload_helper.append_folder(collection_item.url)

    def _is_remote_folder(self, url):
        url = url.lower()
        return url.startswith("omniverse://") or url.startswith("http://") or url.startswith("https://")
