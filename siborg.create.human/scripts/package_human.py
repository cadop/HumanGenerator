"""Package the human into data/human.usdz, the single file the extension adds to the scene.

The last step of scripts/build_human.py. human_base_separated.usd sublayers human_base.usd, and the modifier preview
images (AssetPreviewsAPI thumbnails, see HumanModifier in schema/schema.usda) are loose files under data/targets. This
flattens the layer stack into one layer, keeping asset paths relative so they stay anchored to data/, then lets
UsdUtils.CreateNewUsdzPackage collect that layer and every image it refers to into one usdz.

Flattening the layer stack rather than packaging both layers drops the offsets separate_skeltargets.py overrode,
which roughly halves the package (55 MB rather than 83 MB with all target groups installed).
"""

import os
import sys
import zipfile

from pxr import Usd, UsdUtils

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SOURCE = os.path.join(DATA, "human_base_separated.usd")
PACKAGE = os.path.join(DATA, "human.usdz")
# Written next to the sources so their relative asset paths resolve, and removed once packaged. Its name is the name
# of the package's root layer.
FLAT = os.path.join(DATA, "human.usdc")


def main() -> int:
    stage = Usd.Stage.Open(SOURCE)
    # Keep asset paths as authored: both source layers live in data/, as does FLAT
    layer = UsdUtils.FlattenLayerStack(stage, resolveAssetPathFn=lambda _layer, path: path)
    if not layer.Export(FLAT):
        print(f"package_human: could not write {FLAT}", file=sys.stderr)
        return 1
    try:
        if os.path.exists(PACKAGE):
            os.remove(PACKAGE)
        if not UsdUtils.CreateNewUsdzPackage(FLAT, PACKAGE):
            print(f"package_human: could not package {PACKAGE}", file=sys.stderr)
            return 1
    finally:
        os.remove(FLAT)
    with zipfile.ZipFile(PACKAGE) as z:
        images = sum(1 for n in z.namelist() if n.lower().endswith(".png"))
    print(f"package_human: wrote {PACKAGE} ({os.path.getsize(PACKAGE) >> 20} MB, {images} preview images)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
