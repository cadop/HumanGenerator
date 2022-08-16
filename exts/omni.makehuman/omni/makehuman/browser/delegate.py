import carb
import omni.ui as ui
import omni.kit.app
from omni.kit.browser.core import get_legacy_viewport_interface
from omni.kit.browser.folder.core import FolderDetailDelegate
from .model import MHAssetBrowserModel, AssetDetailItem

import asyncio
from pathlib import Path
from typing import Optional

CURRENT_PATH = Path(__file__).parent
ICON_PATH = CURRENT_PATH.parent.parent.parent.parent.joinpath("icons")


class AssetDetailDelegate(FolderDetailDelegate):
    """
    Delegate to show asset item in detail view
    Args:
        model (AssetBrowserModel): Asset browser model
    """

    def __init__(self, model: MHAssetBrowserModel):
        super().__init__(model=model)

        self._dragging_url = None
        self._settings = carb.settings.get_settings()
        self._context_menu: Optional[ui.Menu] = None
        self._action_item: Optional[AssetDetailItem] = None

        self._instanceable_categories = self._settings.get(
            "/exts/omni.makehuman.browser.asset/instanceable"
        )
        if self._instanceable_categories:
            self._viewport = get_legacy_viewport_interface()
            if self._viewport and hasattr(self._viewport, "create_drop_helper"):
                self._drop_helper = self._viewport.create_drop_helper(
                    pickable=True,
                    add_outline=True,
                    on_drop_accepted_fn=self._on_drop_accepted,
                    on_drop_fn=self._on_drop,
                )
            else:
                self._viewport = None
                self._drop_helper = None

    def destroy(self):
        self._viewport = None
        self._drop_helper = None
        super().destroy()

    def get_thumbnail(self, item) -> str:
        """Set default sky thumbnail if thumbnail is None"""
        if item.thumbnail is None:
            return f"{ICON_PATH}/usd_stage_256.png"
        else:
            return item.thumbnail

    def on_drag(self, item: AssetDetailItem) -> str:
        """Could be dragged to viewport window"""
        thumbnail = self.get_thumbnail(item)
        icon_size = 128
        with ui.VStack(width=icon_size):
            if thumbnail:
                ui.Spacer(height=2)
                with ui.HStack():
                    ui.Spacer()
                    ui.ImageWithProvider(
                        thumbnail, width=icon_size, height=icon_size
                    )
                    ui.Spacer()
            ui.Label(
                item.name,
                word_wrap=False,
                elided_text=True,
                skip_draw_when_clipped=True,
                alignment=ui.Alignment.TOP,
                style_type_name_override="GridView.Item",
            )

        self._dragging_url = None
        if self._instanceable_categories:
            # For required categories, need to set instanceable after dropped
            url = item.url
            pos = url.rfind("/")
            if pos > 0:
                url = url[:pos]
            for category in self._instanceable_categories:
                if category in url:
                    self._dragging_url = item.url
                    break
        return item.url

    def _on_drop_accepted(self, url):
        # Only hanlder dragging from asset browser
        return url == self._dragging_url

    def _on_drop(self, url, target, viewport_name, context_name):
        saved_instanceable = self._settings.get(
            "/persistent/app/stage/instanceableOnCreatingReference"
        )
        if not saved_instanceable and url == self._dragging_url:
            # Enable instanceable for viewport asset drop handler
            self._settings.set_bool(
                "/persistent/app/stage/instanceableOnCreatingReference", True
            )

            async def __restore_instanceable_flag():
                # Waiting for viewport asset dropper handler completed
                await omni.kit.app.get_app().next_update_async()
                self._settings.set(
                    "/persistent/app/stage/instanceableOnCreatingReference",
                    saved_instanceable,
                )

            asyncio.ensure_future(__restore_instanceable_flag())

        self._dragging_url = None
        # Let viewport do asset dropping
        return None

    def on_right_click(self, item: AssetDetailItem) -> None:
        """Show context menu"""
        self._action_item = item
        if self._context_menu is None:
            try:
                import omni.kit.tool.collect

                self._context_menu = ui.Menu("Asset browser context menu")
                with self._context_menu:
                    ui.MenuItem("Collect", triggered_fn=self._collect)
            except ImportError:
                carb.log_warn(
                    "Plese enable omni.kit.tool.collect first to collect."
                )

        if self._context_menu:
            self._context_menu.show()

    def _collect(self):
        try:
            import omni.kit.tool.collect

            collect_instance = omni.kit.tool.collect.get_instance()
            collect_instance.collect(self._action_item.url)
            collect_instance = None
        except ImportError:
            carb.log_warn(
                "Failed to import collect module (omni.kit.tool.collect). Please enable it first."
            )
        except AttributeError:
            carb.log_warn("Require omni.kit.tool.collect v2.0.5 or later!")
