"""Build data/human.usdz, the human the extension adds to the scene, by way of data/human_base.usd and
data/human_base_separated.usd.

Runs scripts/buildusd/buildusd.py, scripts/separate_skeltargets.py, scripts/evaluate_human.py (which authors the
blendshape weights and joint translations for the default modifier values), then scripts/package_human.py (which
packages the human with its modifier preview images), with kit-app-template's USD build and
numpy (see generate_schema.kit_build_env). Run automatically by `repo build` in kit-app-template after generate_schema.py
(see [repo_build.pre_build] in kit-app-template/repo.toml). Both outputs are generated, so they aren't tracked in git.

Skipped when both outputs are newer than every input (the data folder, the build scripts and schema.usda). Takes
about 30 seconds when it does run (all target groups installed).

Usage: python build_human.py [kit-app-template root] [--force]
"""

import argparse
import subprocess
import sys
from pathlib import Path

from generate_schema import DEFAULT_KIT_ROOT, EXT_ROOT, SCHEMA_SRC, kit_build_env

SCRIPTS = Path(__file__).resolve().parent
DATA = EXT_ROOT / "data"
OUTPUTS = (DATA / "human_base.usd", DATA / "human_base_separated.usd", DATA / "human.usdz")
# Run in order; each is run from its own folder because buildusd.py imports its sibling modules by name.
STEPS = (SCRIPTS / "buildusd" / "buildusd.py", SCRIPTS / "separate_skeltargets.py", SCRIPTS / "evaluate_human.py",
         SCRIPTS / "package_human.py")


def _inputs():
    yield SCHEMA_SRC
    yield from (SCRIPTS / "buildusd").glob("*.py")
    yield from STEPS[1:]
    yield EXT_ROOT / "siborg" / "create" / "human" / "humaneval.py"
    yield from (p for p in DATA.rglob("*") if p.is_file() and p not in OUTPUTS)


def up_to_date() -> bool:
    if not all(p.exists() for p in OUTPUTS):
        return False
    oldest_output = min(p.stat().st_mtime for p in OUTPUTS)
    return all(p.stat().st_mtime <= oldest_output for p in _inputs())


def main(kit_root: Path, force: bool = False) -> int:
    if not force and up_to_date():
        print("build_human: human USD is up to date")
        return 0

    env = kit_build_env(kit_root)
    if env is None:
        return 1

    for script in STEPS:
        print(f"build_human: running {script.name}")
        result = subprocess.run([sys.executable, str(script)], cwd=script.parent, env=env, check=False,
                                stdout=subprocess.DEVNULL)  # Per-target progress lines; errors still go to stderr
        if result.returncode != 0:
            print(f"build_human: {script.name} failed with exit code {result.returncode}", file=sys.stderr)
            return result.returncode
    print(f"build_human: wrote {', '.join(p.name for p in OUTPUTS)}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("kit_root", nargs="?", default=DEFAULT_KIT_ROOT, type=Path,
                        help="kit-app-template root (passed by repo_build)")
    parser.add_argument("--force", action="store_true", help="rebuild even if the outputs are up to date")
    args = parser.parse_args()
    sys.exit(main(args.kit_root.resolve(), args.force))
