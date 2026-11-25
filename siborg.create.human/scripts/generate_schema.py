"""Regenerate the humanGenerator schema plugin from schema/schema.usda.

Run automatically by `repo build` in kit-app-template (see [repo_build.pre_build] in kit-app-template/repo.toml).
kit-app-template is expected to be checked out next to this repo; its .kit app loads siborg.create.human from here.

The schema is codeless (skipCodeGeneration = true), so usdGenSchema only writes generatedSchema.usda and plugInfo.json
into plugins/humanGenerator, which the extension registers on import (see siborg/create/human/__init__.py).

usdGenSchema comes from Kit's USD build, pulled into _build/target-deps/usd/release by
tools/deps/kit-sdk-deps.packman.xml. Its Python dependencies (jinja2, plus numpy for build_human.py) are
pip-installed into _build/host-deps/humangenerator-build by tools/deps/pip.toml.

Usage: python generate_schema.py [kit-app-template root]
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

EXT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_SRC = EXT_ROOT / "schema" / "schema.usda"
# Must match libraryName in schema.usda's GLOBAL prim.
OUTPUT_DIR = EXT_ROOT / "plugins" / "humanGenerator"
# Fallback when no kit-app-template root is given: kit-app-template checked out next to this repo.
DEFAULT_KIT_ROOT = EXT_ROOT.parent.parent / "kit-app-template"


def usd_root(kit_root: Path) -> Path:
    return kit_root / "_build" / "target-deps" / "usd" / "release"


def kit_build_env(kit_root: Path) -> Optional[Dict[str, str]]:
    """Environment for running USD Python tools with kit-app-template's build deps, or None if they're missing."""
    usd = usd_root(kit_root)
    tools = kit_root / "_build" / "host-deps" / "humangenerator-build"
    for required in (usd / "lib" / "python" / "pxr", tools / "jinja2", tools / "numpy"):
        if not required.exists():
            print(f"{required} not found; run `repo build` in {kit_root} to fetch it.", file=sys.stderr)
            return None

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(usd / "lib" / "python"), str(tools)])
    env["PATH"] = os.pathsep.join([str(usd / "lib"), str(usd / "bin"), env.get("PATH", "")])
    # Keep a previously generated copy of the plugin out of the way while regenerating it.
    env.pop("PXR_PLUGINPATH_NAME", None)
    return env


def main(kit_root: Path) -> int:
    env = kit_build_env(kit_root)
    if env is None:
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(usd_root(kit_root) / "bin" / "usdGenSchema"), str(SCHEMA_SRC), str(OUTPUT_DIR)]
    print(f"generate_schema: {' '.join(cmd)}")
    returncode = subprocess.run(cmd, env=env, check=False).returncode
    if returncode == 0:
        _resolve_plug_info(OUTPUT_DIR / "plugInfo.json")
    return returncode


# usdGenSchema leaves these placeholders for CMake to fill in. A codeless schema has no library, and its resources
# (generatedSchema.usda) sit next to plugInfo.json.
PLUG_INFO_PLACEHOLDERS = {
    "@PLUG_INFO_LIBRARY_PATH@": "",
    "@PLUG_INFO_RESOURCE_PATH@": ".",
    "@PLUG_INFO_ROOT@": ".",
}


def _resolve_plug_info(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for placeholder, value in PLUG_INFO_PLACEHOLDERS.items():
        text = text.replace(placeholder, value)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    # kit-app-template root is passed by repo_build.
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_KIT_ROOT
    sys.exit(main(root.resolve()))
