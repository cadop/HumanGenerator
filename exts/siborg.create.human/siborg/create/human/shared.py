from pathlib import Path

# Shared methods that are useful to several modules
def data_path(path):
    """Returns the absolute path of a path given relative to "exts/<omni.ext>/data"

    Parameters
    ----------
    path : str
        Relative path

    Returns
    -------
    str
        Absolute path
    """
    return str(Path(__file__).parents[2]) + "/data/" + path
