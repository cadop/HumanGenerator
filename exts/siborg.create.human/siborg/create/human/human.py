from mhapp import MHApp
import omni.kit
import omni.usd
from pxr import Gf, Sdf, Usd, UsdGeom


class Human:
    def __init__(self, name='human', **kwargs):
        """Constructs an instance of Human.

        Parameters
        ----------
        name : str
            Name of the human. Defaults to 'human'
        """

        self.name = name

        # Create or get instance of interface to Makehuman app
        self.mhapp = MHApp()

        # Set the human in makehuman to default values
        self.mhapp.reset_human()

    @property
    def objects(self):
        """List of objects attached to the human. Fetched from the makehuman app"""
        return self.mhapp.objects

    def add_to_scene(self):
        """Adds the human to the scene. Creates a prim for the human with custom attributes
        to hold modifiers and proxies. Also creates a prim for each proxy and attaches it to
        the human prim."""

        # Get the current stage
        stage = omni.usd.get_context().get_stage()

        root_path = "/"

        # Get default prim.
        default_prim = stage.GetDefaultPrim()
        if default_prim.IsValid():
            # Set the rootpath under the stage's default prim, if the default prim is valid
            root_path = default_prim.GetPath().pathString

        # Create a path for the next available prim
        prim_path = omni.usd.get_stage_next_free_path(root_path + "/" + self.name, False)

        UsdGeom.Xform.Define(stage, prim_path)

        # Write the properties of the human to the prim
        self.write_properties(prim_path, stage)

    def write_properties(self, prim_path: str, stage: Usd.Stage):
        """Writes the properties of the human to the human prim. This includes modifiers and
        proxies. This is called when the human is added to the scene, and when the human is
        updated

        Parameters
        ----------
        prim_path : str
            Path to the human prim
        stage : Usd.Stage
            Stage to write to
        """

        prim = stage.GetPrimAtPath(prim_path)

        # Get the modifiers of the human in MHApp
        modifiers = self.mhapp.modifiers

        for m in modifiers:
            # Add the modifier to the prim as custom data by key
            # NOTE for USD, keyname can be a ':'-separated path identifying a value
            # in a subdictionary
            prim.SetCustomDataByKey("modifiers:" + m.fullName, m.getValue())

        # Get the proxies of the human in MHApp
        proxies = self.mhapp.proxies

        for p in proxies:
            # Add the proxy to the prim as custom data by key, specifying type
            # proxy type should be "Proxies" if type cannot be determined from the
            # proxy.type property
            type = p.type if p.type else "Proxies"
            prim.SetCustomDataByKey(type + ":" + p.name, p.getUuid())
