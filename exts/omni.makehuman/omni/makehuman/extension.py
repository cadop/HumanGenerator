import omni.ext
import omni.ui as ui
from . import mhcaller
import omni

# from . import assetconverter

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
        mh_call.filepath = "D:/human.obj"

        primpath = "/World/human"

        self._window = ui.Window("Makehuman", width=300, height=300)
        with self._window.frame:
            with ui.VStack():
                with ui.CollapsableFrame("Phenotype"):
                    with ui.HStack():
                        ui.Label("Age", height=15, width=50)
                        field = ui.FloatField(height=15, width=50)
                        ui.FloatSlider(min=1, max=89, step=0.25, model=field.model)
                        field.model.add_value_changed_fn(lambda m: mh_call.set_age(m.get_value_as_int()))

                with ui.HStack():
                    ui.Button(
                        "add_to_scene",
                        clicked_fn=lambda: self.add_to_scene(mh_call.filepath, primpath),
                    )
                    ui.Button("Save Human", clicked_fn=lambda: mh_call.store_obj())

    def on_shutdown(self):
        print("[omni.makehuman] makehuman shutdown")

    def add_to_scene(self, input_obj, primpath):

        usd_context = omni.usd.get_context()

        omni.kit.commands.execute(
            "CreateReferenceCommand",
            usd_context=usd_context,
            path_to=primpath,
            asset_path=input_obj,
            instanceable=True,
        )
