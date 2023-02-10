from pathlib import Path
import os

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
    # Uses an absolute path, and then works its way up the folder directory to find the data folder
    data = os.path.join(str(Path(__file__).parents[3]), "data", path)
    return data


def sanitize(s: str):
    """Sanitize strings for use a prim names. Strips and replaces illegal
    characters.

    Parameters
    ----------
    s : str
        Input string

    Returns
    -------
    s : str
        Primpath-safe output string
    """
    # List of illegal characters
    # TODO create more comprehensive list
    # TODO switch from blacklisting illegal characters to whitelisting valid ones
    illegal = (".", "-")
    for c in illegal:
        # Replace illegal characters with underscores
        s = s.replace(c, "_")
    return s
