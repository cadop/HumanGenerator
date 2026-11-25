import os
import tempfile
from typing import Dict, List, Optional

import carb

import omni.kit.commands
import omni.ui as ui
from pxr import Sdf

from siborg.create.human.shared import data_path

from . import styles
from .humaneval import HumanRig, local_image
from .humansync import get_sync

# Preview images extracted from the human's .usdz, which image widgets can't read from directly
PREVIEW_CACHE = os.path.join(tempfile.gettempdir(), "siborg.create.human", "previews")
PREVIEW_WIDTH, PREVIEW_HEIGHT = 64, 32  # MakeHuman's slider images are 128 x 64


class ModifierUI(ui.Frame):
    """Sliders for the selected human's HumanModifier prims, one collapsable section per HumanModifierGroup.

    Sliders author HumanModifier.value only; HumanSync derives blendshape weights and joint translations from it. A
    drag is one undo step (SetHumanModifierValuesCommand). Each slider shows its modifier's preview image (the default
    thumbnail of AssetPreviewsAPI). Modifiers that drive no blendshapes (their targets aren't installed) are left out.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rig: Optional[HumanRig] = None
        self._models: Dict[int, ui.SimpleFloatModel] = {}
        self._syncing = False  # True while models are updated from the stage, so their callbacks don't write back
        self._edit_start = None  # Values when the current slider edit began
        self._sync = get_sync()
        if self._sync:
            self._sync.add_listener(self._on_human_changed)
        self.set_build_fn(self._build_widget)

    # Selection ---------------------------------------------------------------------------------------------------

    def load_values(self, human_path: Optional[str]):
        """Show the human at human_path (any prim of it, see humaneval.find_human), or nothing for None."""
        self.rig = self._sync.get_rig(human_path) if (self._sync and human_path) else None
        self.rebuild()

    def reset(self):
        """Reset every modifier of the shown human to its default value (one undo step)."""
        if not self.rig:
            return
        old = self.rig.read_values()
        self._commit(old, self.rig.default_values())

    # Building ----------------------------------------------------------------------------------------------------

    def _build_widget(self):
        self._models = {}
        rig = self.rig
        with ui.ScrollingFrame(horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_OFF):
            with ui.VStack(spacing=4, height=0):
                if rig is None:
                    ui.Label("No parameters available", height=0, alignment=ui.Alignment.CENTER)
                    return
                values = rig.read_values()
                hidden = 0
                first = True
                for group, _depth in rig.groups():
                    members = [rig.index[c.GetPath()] for c in group.GetChildren()
                               if c.GetPath() in rig.index]
                    active = [i for i in members if rig.modifiers[i].shape_count]
                    hidden += len(members) - len(active)
                    if not active:
                        continue
                    title = group.GetAttribute("label").Get() or group.GetName()
                    with ui.CollapsableFrame(title, collapsed=not first, height=0, style=styles.frame_style):
                        with ui.VStack(name="contents", spacing=6, height=0, style=styles.panel_style):
                            for i in active:
                                self._build_slider(i, values[i])
                    first = False
                if not self._models:
                    ui.Label("No parameters available", height=0, alignment=ui.Alignment.CENTER)
                if hidden:
                    ui.Label(f"{hidden} modifiers hidden: their targets aren't installed in data/targets.",
                             height=0, alignment=ui.Alignment.CENTER, name="hint", style={"color": 0xFF808080})

    def _build_slider(self, i: int, value: float):
        m = self.rig.modifiers[i]
        model = ui.SimpleFloatModel(float(value))
        self._models[i] = model
        with ui.HStack(height=0, spacing=6, style=styles.sliderentry_style):
            image = self._preview(m.image)
            if image:
                ui.Image(image, width=PREVIEW_WIDTH, height=PREVIEW_HEIGHT,
                         fill_policy=ui.FillPolicy.PRESERVE_ASPECT_FIT, tooltip=m.label)
            else:
                ui.Spacer(width=PREVIEW_WIDTH)  # Keep the sliders aligned
            ui.Label(m.label, width=ui.Percent(30), name="label_param", tooltip=m.path.pathString,
                     elided_text=True)
            ui.FloatSlider(model=model, min=m.min, max=m.max, step=0.01, precision=3)
            ui.Button("Reset", width=0, tooltip=f"Reset to {m.default:g}",
                      clicked_fn=lambda i=i: self._reset_one(i))
        model.add_begin_edit_fn(lambda _m: self._begin_edit())
        model.add_value_changed_fn(lambda mdl, i=i: self._on_value_changed(i, mdl.get_value_as_float()))
        model.add_end_edit_fn(lambda _m: self._end_edit())

    @staticmethod
    def _preview(resolved_path: str) -> str:
        try:
            return local_image(resolved_path, PREVIEW_CACHE)
        except Exception as e:  # A missing preview mustn't cost the slider
            carb.log_warn(f"siborg.create.human: preview image {resolved_path}: {e}")
            return ""

    # Editing -----------------------------------------------------------------------------------------------------

    def _begin_edit(self):
        if self.rig and self._edit_start is None:
            self._edit_start = self.rig.read_values()

    def _on_value_changed(self, i: int, value: float):
        if self._syncing or not self.rig:
            return
        current = self.rig.read_values()
        updates = self.rig.normalized(i, value, current)
        self.rig.write_values(updates)
        # Normalization moved other sliders
        self._set_models({j: v for j, v in updates.items() if j != i})
        if self._edit_start is None:  # A change outside a begin/end edit pair (e.g. typed value): its own undo step
            self._commit(current, self.rig.read_values())

    def _end_edit(self):
        if self.rig and self._edit_start is not None:
            start, self._edit_start = self._edit_start, None
            self._commit(start, self.rig.read_values())

    def _reset_one(self, i: int):
        if not self.rig:
            return
        current = self.rig.read_values()
        updates = self.rig.normalized(i, self.rig.modifiers[i].default, current)
        new = current.copy()
        for j, v in updates.items():
            new[j] = v
        self._commit(current, new)

    def _commit(self, old, new):
        """Record the change from old to new values as one undoable command (which also authors new)."""
        changed = [i for i in range(len(new)) if abs(new[i] - old[i]) > 1e-9]
        if not changed:
            return
        paths = [self.rig.modifiers[i].path.pathString for i in changed]
        omni.kit.commands.execute(
            "SetHumanModifierValues",
            new_values={p: float(new[i]) for p, i in zip(paths, changed)},
            old_values={p: float(old[i]) for p, i in zip(paths, changed)},
        )

    # Stage -> UI -------------------------------------------------------------------------------------------------

    def _set_models(self, values: Dict[int, float]):
        self._syncing = True
        try:
            for i, v in values.items():
                model = self._models.get(i)
                if model and abs(model.get_value_as_float() - v) > 1e-6:
                    model.set_value(float(v))
        finally:
            self._syncing = False

    def _on_human_changed(self, root: Sdf.Path):
        """HumanSync re-evaluated a human: refresh the sliders if it's the one shown (undo, property panel, ...)."""
        if self.rig and root == self.rig.path and self._edit_start is None:
            if not self.rig.root.IsValid():
                self.load_values(None)
                return
            values = self.rig.read_values()
            self._set_models({i: values[i] for i in self._models})

    def destroy(self):
        if self._sync:
            self._sync.remove_listener(self._on_human_changed)
            self._sync = None
        self._models = {}
        self.rig = None
        super().destroy()


class NoSelectionNotification:
    """
    When no human selected, show notification.
    """

    def __init__(self):
        self._container = ui.ZStack()
        with self._container:
            ui.Rectangle()
            with ui.VStack(spacing=10):
                ui.Spacer(height=10)
                with ui.HStack(height=0):
                    ui.Spacer()
                    ui.ImageWithProvider(
                        data_path("human_icon.png"),
                        width=192,
                        height=192,
                        fill_policy=ui.IwpFillPolicy.IWP_PRESERVE_ASPECT_FIT,
                    )
                    ui.Spacer()
                self._message_label = ui.Label("No human is current selected.", height=0, alignment=ui.Alignment.CENTER)
                self._suggestion_label = ui.Label(
                    "Select a human prim to see its properties here.", height=0, alignment=ui.Alignment.CENTER
                )

    @property
    def visible(self) -> bool:
        return self._container.visible

    @visible.setter
    def visible(self, value) -> None:
        self._container.visible = value

    def set_message(self, message: str) -> None:
        messages = message.split("\n")
        self._message_label.text = messages[0]
        self._suggestion_label.text = messages[1]
