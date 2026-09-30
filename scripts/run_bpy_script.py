"""Run one Blender Python script in a bpy wheel worker, with a clean OS exit.

The wheel can fault during interpreter shutdown after a successful render.
Explicitly flushing and exiting after the completed script avoids that teardown;
exceptions retain their traceback and nonzero status. Native Blender CLI users
do not need this worker.
"""
from __future__ import annotations

import os
from pathlib import Path
import runpy
import sys
import traceback


def main() -> int:
    if len(sys.argv) < 2:
        print('Usage: python scripts/run_bpy_script.py SCRIPT -- SCRIPT_ARGS', file=sys.stderr)
        return 2
    script = Path(sys.argv[1]).resolve()
    sys.argv = [str(script), *sys.argv[2:]]
    sys.path.insert(0, str(script.parent))
    try:
        runpy.run_path(str(script), run_name='__main__')
        return 0
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 0 if error.code is None else 1
    except BaseException:
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    status = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(status)
