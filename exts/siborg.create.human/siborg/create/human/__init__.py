from .extension import *
try:
    import makehuman
except ModuleNotFoundError:
    print("MakeHuman not found. API disabled. API will be enabled once MakeHuman is installed.")
else:
    from .human import Human
