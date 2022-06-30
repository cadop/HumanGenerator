import omni.ext
import omni.ui as ui
from . import mhcaller

# Any class derived from `omni.ext.IExt` in top level module (defined in `python.modules` of `extension.toml`) will be
# instantiated when extension gets enabled and `on_startup(ext_id)` will be called. Later when extension gets disabled
# on_shutdown() is called.
class MyExtension(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.

    def on_startup(self, ext_id):
        print("[omni.makehuman] MyExtension startup")

        # Create instance of manager class
        mh_call = mhcaller.MHCaller()
        mh_call.filepath = 'D:/human.obj'

        self._window = ui.Window("My Window", width=300, height=300)
        with self._window.frame:
            with ui.VStack():
                ui.Button("Save Human", clicked_fn=lambda: mh_call.store_obj())
                with ui.HStack():
                    field = ui.FloatField()
                    field.model.add_value_changed_fn(lambda m:mh_call.set_age(m.get_value_as_int()))


    def on_shutdown(self):
        print("[omni.makehuman] MyExtension shutdown")
