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

        # Get the properties of the human in MHApp
        properties = self.mhapp.properties


        prim = stage.GetPrimAtPath(prim_path)

        prim.SetCustomDataByKey("swni", "sing")

        # keyname can be a ':'-separated path identifying a value in subdictionaries
        prim.SetCustomDataByKey("swn:anid", 622)
        print(prim.GetCustomDataByKey("swn:anid"))  # prints 622

        prim.SetCustomDataByKey("ui:nodegraph:node:previewState:open", "loop")