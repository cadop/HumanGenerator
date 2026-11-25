"""Keeps every human's derived state (blendshape weights, joint translations) in step with its modifier values.

HumanModifier.value is the only state the UI writes. Whatever changes a value (a slider, undo/redo, the property
panel, a script), HumanSync notices it through Usd.Notice.ObjectsChanged and, on the next app update, re-evaluates that
human with humaneval.HumanRig and writes the result to its SkelAnimation. Listeners (the modifier panel) are told which
human changed so they can refresh.

Writing is deferred to the next update because the stage must not be edited from inside a change notice.
"""

from typing import Callable, Dict, List, Optional, Set

import carb
import omni.kit.app
import omni.kit.commands
import omni.usd
from pxr import Sdf, Tf, Usd

from .humaneval import HumanRig, find_human

_instance: Optional["HumanSync"] = None


def get_sync() -> Optional["HumanSync"]:
    """The extension's HumanSync, or None while the extension is shut down."""
    return _instance


class HumanSync:
    def __init__(self, usd_context_name: str = ""):
        global _instance
        self._context = omni.usd.get_context(usd_context_name)
        self._rigs: Dict[Sdf.Path, HumanRig] = {}
        self._dirty: Set[Sdf.Path] = set()
        self._listeners: List[Callable[[Sdf.Path], None]] = []
        self._notice = None
        self._stage_sub = self._context.get_stage_event_stream().create_subscription_to_pop(
            self._on_stage_event, name="siborg.create.human sync stage events")
        self._update_sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
            self._on_update, name="siborg.create.human sync update")
        self._attach(self._context.get_stage())
        _instance = self

    def destroy(self):
        global _instance
        self._detach()
        self._stage_sub = None
        self._update_sub = None
        self._listeners.clear()
        if _instance is self:
            _instance = None

    # Humans ------------------------------------------------------------------------------------------------------

    def get_rig(self, path) -> Optional[HumanRig]:
        """The rig for the human at or around path (see humaneval.find_human), built on first use."""
        stage = self._context.get_stage()
        if not stage or not path:
            return None
        root = find_human(stage.GetPrimAtPath(Sdf.Path(str(path))))
        if root is None:
            return None
        rig = self._rigs.get(root.GetPath())
        if rig is None or not rig.root.IsValid():
            try:
                rig = HumanRig(root)
            except ValueError as e:
                carb.log_warn(f"siborg.create.human: can't evaluate {root.GetPath()}: {e}")
                return None
            self._rigs[root.GetPath()] = rig
        return rig

    def add_listener(self, fn: Callable[[Sdf.Path], None]) -> None:
        self._listeners.append(fn)

    def remove_listener(self, fn: Callable[[Sdf.Path], None]) -> None:
        if fn in self._listeners:
            self._listeners.remove(fn)

    # Stage tracking ----------------------------------------------------------------------------------------------

    def _attach(self, stage: Optional[Usd.Stage]):
        self._detach()
        if stage:
            self._notice = Tf.Notice.Register(Usd.Notice.ObjectsChanged, self._on_objects_changed, stage)

    def _detach(self):
        if self._notice:
            self._notice.Revoke()
            self._notice = None
        self._rigs.clear()
        self._dirty.clear()

    def _on_stage_event(self, event):
        if event.type == int(omni.usd.StageEventType.OPENED):
            self._attach(self._context.get_stage())
        elif event.type == int(omni.usd.StageEventType.CLOSING):
            self._detach()

    def _on_objects_changed(self, notice, stage):
        resynced = notice.GetResyncedPaths()
        # Prims added, removed or recomposed under a human invalidate its rig (modifier set, bindings, ...)
        for path in resynced:
            if path.IsPrimPath() or path.IsAbsoluteRootPath():
                for root in [r for r in self._rigs if r.HasPrefix(path) or path.HasPrefix(r)]:
                    del self._rigs[root]
        # A value authored for the first time shows up as a property resync, later edits as info-only changes
        for path in list(resynced) + list(notice.GetChangedInfoOnlyPaths()):
            if not path.IsPropertyPath() or path.name != "value":
                continue
            prim = stage.GetPrimAtPath(path.GetPrimPath())
            if prim and prim.GetTypeName() == "HumanModifier":
                root = find_human(prim, search_depth=0)
                if root:
                    self._dirty.add(root.GetPath())

    def _on_update(self, _event):
        if not self._dirty:
            return
        dirty, self._dirty = self._dirty, set()
        for root in dirty:
            rig = self.get_rig(root)
            if rig is None:
                continue
            try:
                rig.apply()
            except Exception as e:  # Keep the update loop alive whatever a malformed human does
                carb.log_error(f"siborg.create.human: evaluating {root} failed: {e}")
                continue
            for fn in list(self._listeners):
                fn(root)


class SetHumanModifierValuesCommand(omni.kit.commands.Command):
    """Set HumanModifier values, undoably. Weights and joints follow through HumanSync.

    Parameters
    ----------
    new_values, old_values : dict
        Modifier prim path (str) -> value. old_values is what undo restores.
    """

    def __init__(self, new_values: Dict[str, float], old_values: Dict[str, float], usd_context_name: str = ""):
        self._new = dict(new_values)
        self._old = dict(old_values)
        self._context_name = usd_context_name

    def _set(self, values: Dict[str, float]):
        stage = omni.usd.get_context(self._context_name).get_stage()
        if not stage:
            return
        for path, value in values.items():
            attr = stage.GetAttributeAtPath(Sdf.Path(path).AppendProperty("value"))
            if attr:
                attr.Set(float(value))

    def do(self):
        self._set(self._new)

    def undo(self):
        self._set(self._old)
