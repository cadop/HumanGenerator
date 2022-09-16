import omni.ext
import siborg.human.generator
from .ext_ui import MHWindow
import omni


# from . import assetconverter

# Any class derived from `omni.ext.IExt` in top level module (defined in `python.modules` of `extension.toml`) will be
# instantiated when extension gets enabled and `on_startup(ext_id)` will be called. Later when extension gets disabled
# on_shutdown() is called.


class MakeHumanExtension(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.

    def on_startup(self, ext_id):
        print("[siborg.human.generator] HumanGeneratorExtension startup")
        self._window = MHWindow("Human Generator")

    def on_shutdown(self):
        print("[siborg.human.generator] HumanGenerator shutdown")
        self._window.destroy()
        self._window = None
