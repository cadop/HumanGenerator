import omni.ui as ui
from collections import defaultdict
import omni.kit
import os
import json
from pxr import Tf

class Modifier:
    """A class holding the data and methods for a modifier

    Attributes
    ----------
    label: str
        A label for the parameter
    full_name: str
        The original, full name of the modifier
    blend: str
        The base name of the blendshape(s) to modify
    image: str, optional
        The path to the image to use for labeling. By default None
    min_blend: str, optional
        Suffix (appended to `blendshape`) naming the blendshape for decreasing the value. Empty string by default.
    max_blend: str, optional
        Suffix (appended to `blendshape`) naming the blendshape for increasing the value. Empty string by default.
    min: float, optional
        The minimum value for the parameter. By default -1
    max: float, optional
        The maximum value for the parameter. By default 1
    value : ui.SimpleFloatModel
        The model to track the current value of the parameter. By default None
    """
    def __init__(self, group, modifier_data: dict):

        self.group = group

        # Not handling macros yet
        if "target" not in modifier_data:
            return None
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

        # Blendshapes are named based on the modifier name
        self.blend = Tf.MakeValidIdentifier(modifier_data["target"])
        
        self.max_val = 1
        self.default_val = 0

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

        self.value_model = ui.SimpleFloatModel(self.default_val)

        self.fn = self.get_modifier_fn()

    def get_modifier_fn(self):
        # Return a method to list modified blendshapes and their weights
        def modifier_fn(model: ui.SimpleFloatModel):
            value = model.get_value_as_float()
            if self.max_blend and self.min_blend:
                if value > 0:
                    return {self.max_blend: value, self.min_blend: 0}
                else:
                    return {self.max_blend: 0, self.min_blend: -value}
            else:
                return {self.blend: value}
        return modifier_fn


def parse_modifiers():
    """Parses modifiers from a json file for use in the UI"""
    manager = omni.kit.app.get_app().get_extension_manager()
    ext_id = manager.get_enabled_extension_id("siborg.create.human")
    ext_path = manager.get_extension_path(ext_id)
    json_path = os.path.join(ext_path, "data", "modifiers", "modeling_modifiers.json")

    groups = defaultdict(list)
    modifiers = []

    with open(json_path, "r") as f:
        data = json.load(f)
        for group in data:
            groupname = group["group"].capitalize()
            for modifier_data in group["modifiers"]:
                if "target" not in modifier_data:
                    continue
                # Create an object for the modifier
                modifier = Modifier(groupname, modifier_data)
                # Add the modifier to the group
                groups[groupname].append(modifier)
                # Add the modifier to the list of all modifiers (for tracking changes)
                modifiers.append(modifier)

    return groups, modifiers