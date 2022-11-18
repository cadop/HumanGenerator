class Human:
    def __init__(self, name='human', **kwargs):
        self.default_name = name
        self.reset_human()

    def reset_human(self):
        """Resets the human object to its initial state. This involves setting the
        human's name to its default, resetting all modifications, and resetting all
        proxies. Does not reset the skeleton. Also flags the human as having been
        reset so that the new name can be created when adding to the Usd stage.
        """
        self.is_reset = True
        self.name = self.default_name
        self.human.resetMeshValues()
        # Restore eyes
        # self.add_proxy(data_path("eyes/high-poly/high-poly.mhpxy"), "eyes")
        # Remove skeleton
        self.human.skeleton = None
        # HACK Set the age to itself to force an update of targets
        self.human.setAge(self.human.getAge())

    @property
    def objects(self):
        """List of objects attached to the human.

        Returns
        -------
        list of: guiCommon.Object
            All 3D objects included in the human. This includes the human
            itself, as well as any proxies
        """
        # Make sure proxies are up-to-date
        self.update()
        return self.human.getObjects()

    def add_to_scene(self):
        """Adds the human to the scene. Creates a prim for the human with custom attributes
        to hold modifiers and proxies. Also creates a prim for each proxy and attaches it to
        the human prim."""
