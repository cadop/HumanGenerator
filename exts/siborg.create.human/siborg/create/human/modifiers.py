import omni.ui as ui
from collections import defaultdict
import omni.kit
import os
import json
from pxr import Tf
from typing import Callable, Dict

class Modifier:
    """A class holding the data and methods for a modifier

    Attributes
    ----------
    full_name: str
        The original, full name of the modifier
    min: float, optional
        The minimum value for the parameter. By default 0
    max: float, optional
        The maximum value for the parameter. By default 1
    value : ui.SimpleFloatModel
        The model to track the current value of the parameter. By default None
    """
    def __init__(self, group, modifier_data: dict):

        self.group = group

        # TODO: Separate class for target modifiers and macrovar modifiers

        # Blendshapes are named based on the modifier name
        self.blend = Tf.MakeValidIdentifier(modifier_data["target"])
        
        self.max_val = 1
        self.min_val = 0
        self.default_val = 0

        self.value_model = ui.SimpleFloatModel(self.default_val)

        self.fn = self.get_modifier_fn()

    def get_modifier_fn(self, model: ui.SimpleFloatModel) -> Callable:
        """Return a method to list modified blendshapes and their weights

        Parameters
        ----------
        model : ui.SimpleFloatModel
            The model to get the value from
        
        Returns
        -------
        dict
            A dictionary of blendshape names and weights
        """
        raise NotImplementedError

class TargetModifier(Modifier):
    """ A class holding the data and methods for a modifier that targets specific blendshapes.
    blend: str
        The base name of the blendshape(s) to modify
    min_blend: str, optional
        Suffix (appended to `blendshape`) naming the blendshape for decreasing the value. Empty string by default.
    max_blend: str, optional
        Suffix (appended to `blendshape`) naming the blendshape for increasing the value. Empty string by default.
    image: str, optional
        The path to the image to use for labeling. By default None
    label: str, optional
        The label to use for the modifier. By default None
    """
    def __init__(self, group, modifier_data: dict):
        if "target" in modifier_data:
            tlabel = modifier_data["target"].split("-")
            if "|" in tlabel[len(tlabel) - 1]:
                tlabel = tlabel[:-1]
            if len(tlabel) > 1 and tlabel[0] == group:
                label = tlabel[1:]
            else:
                label = tlabel
            self.label = " ".join([word.capitalize() for word in label])
            # Guess a suitable image path from modifier name
            tlabel = modifier_data["target"].replace("|", "-").split("-")
            # image = modifier_image(("%s.png" % "-".join(tlabel)).lower())
            self.image = None
        else:
            print(f"No target for modifier {self.full_name}. Is this a macrovar modifier?")
            return
        
        self.min_blend = None
        self.max_blend = None
        if "min" in modifier_data and "max" in modifier_data:
            # Some modifiers adress two blendshapes in either direction
            self.min_blend = Tf.MakeValidIdentifier(f"{self.blend}_{modifier_data['min']}")
            self.max_blend = Tf.MakeValidIdentifier(f"{self.blend}_{modifier_data['max']}")
            self.blend = None
            self.min_val = -1
        else:
            # Some modifiers only adress one blendshape
            self.min_val = 0

        # Initialize superclass after checking data (prevent unused value model and fn)
        super().__init__(group, modifier_data)

    def get_modifier_fn(self) -> dict:
        def modifier_fn(self, model: ui.SimpleFloatModel) -> dict:
            """Simple range-based function for target modifiers"""
            value = model.get_value_as_float()
            if self.max_blend and self.min_blend:
                if value > 0:
                    return {self.max_blend: value, self.min_blend: 0}
                else:
                    return {self.max_blend: 0, self.min_blend: -value}
            else:
                return {self.blend: value}
        return modifier_fn

class MacroModifier(Modifier):
    """More complicated modifier that changes a variable set of targets based on a macrovar.

    Attributes
    ----------
    macrovar: str
        The name of the macrovar to use
    """
    _macro_map = None
    
    @property
    def macro_map():
        if not MacroModifier._macro_map:
            manager = omni.kit.app.get_app().get_extension_manager()
            ext_id = manager.get_enabled_extension_id("siborg.create.human")
            ext_path = manager.get_extension_path(ext_id)
            path = os.path.join(ext_path, "data", "modifiers", "macro.json")
            with open(path, "r") as f:
                MacroModifier._macro_map = json.load(f)
        return MacroModifier._macro_map

    def __init__(self, group, modifier_data: dict):
        if "macrovar" not in modifier_data:
            print(f"No macrovar for modifier {self.full_name}. Is this a target modifier?")
            return
        self.macrovar = modifier_data["macrovar"]

        # Initialize superclass after checking data (prevent unused value model and fn)
        super().__init__(group, modifier_data)
    def get_modifier_fn(self) -> Callable:
        def modifier_fn(self, model: ui.SimpleFloatModel, macrovars: Dict{str, float}) -> dict:
            """Calculate blendshape weights based on modifier value and all macrovars"""
            value = model.get_value_as_float()
            

def interpolate(x, x1, y1, x2, y2):
    return y1 + (x - x1) * (y2 - y1) / (x2 - x1)

def parse_modifiers():
    """Parses modifiers from a json file for use in the UI"""
    manager = omni.kit.app.get_app().get_extension_manager()
    ext_id = manager.get_enabled_extension_id("siborg.create.human")
    ext_path = manager.get_extension_path(ext_id)

    files = ["modeling_modifiers.json", "bodyshapes_modifiers.json", "measurement_modifiers.json"]

    json_paths = [os.path.join(ext_path, "data", "modifiers", f) for f in files]

    groups = defaultdict(list)
    modifiers = []

    for path in json_paths:
        with open(path, "r") as f:
            data = json.load(f)
            for group in data:
                groupname = group["group"].capitalize()
                for modifier_data in group["modifiers"]:
                    if "target" not in modifier_data:
                        # TODO Handle macrovar modifiers
                        continue
                    # Create an object for the modifier
                    modifier = Modifier(groupname, modifier_data)
                    # Add the modifier to the group
                    groups[groupname].append(modifier)
                    # Add the modifier to the list of all modifiers (for tracking changes)
                    modifiers.append(modifier)

    return groups, modifiers

def parse_macro_json