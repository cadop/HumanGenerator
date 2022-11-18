from mhapp import MHApp

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
