import os

import carb
from pxr import Plug

# Register the humanGenerator schema plugin, generated from schema/schema.usda by scripts/generate_schema.py during
# `repo build`. This must run before anything builds the USD schema registry, or the schemas are ignored until restart.
_plugin_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "plugins", "humanGenerator"))
if os.path.isfile(os.path.join(_plugin_dir, "plugInfo.json")):
    _plugins = Plug.Registry().RegisterPlugins(_plugin_dir)
    carb.log_info(f"siborg.create.human registered schema plugins: {[p.name for p in _plugins]}")
else:
    carb.log_warn(f"siborg.create.human: no schema plugin at {_plugin_dir}; run scripts/generate_schema.py "
                  "(or `repo build` in kit-app-template). Human data stays readable as plain attributes.")

from .extension import *
