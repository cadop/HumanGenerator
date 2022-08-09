def absolute_path(path):
    """Returns the absolute path of a path given relative to "exts/<omni.ext>/"

    Parameters
    ----------
    path : str
        Relative path

    Returns
    -------
    str
        Absolute path
    """
    return str(Path(__file__).parents[2]) + path
