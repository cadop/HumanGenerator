"""Author the human's derived state for its default modifier values: blendshape weights and joint translations.

The last step of scripts/build_human.py. buildusd.py and separate_skeltargets.py leave every blendshape weight at 0,
which doesn't match the modifiers' default values (gender 0.5, race 1/3 each, ...), so a freshly added human would show
the bare base mesh until a slider moved. This evaluates the defaults with the extension's own evaluator
(siborg/create/human/humaneval.py) and writes the result into data/human_base_separated.usd.
"""

import importlib.util
import os
import sys

from pxr import Usd

EXT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HUMAN_USD = os.path.join(EXT_ROOT, "data", "human_base_separated.usd")

# Load humaneval by path: importing the siborg.create.human package would pull in Kit
_spec = importlib.util.spec_from_file_location(
    "humaneval", os.path.join(EXT_ROOT, "siborg", "create", "human", "humaneval.py"))
humaneval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(humaneval)


def main() -> int:
    stage = Usd.Stage.Open(HUMAN_USD)
    root = humaneval.find_human(stage.GetDefaultPrim())
    if root is None:
        print(f"evaluate_human: no human SkelRoot in {HUMAN_USD}", file=sys.stderr)
        return 1
    rig = humaneval.HumanRig(root)
    weights, _ = rig.apply(rig.default_values())
    stage.GetRootLayer().Save()
    print(f"evaluate_human: {int((weights > 0).sum())} of {len(weights)} blendshapes weighted at default values")
    return 0


if __name__ == "__main__":
    sys.exit(main())
