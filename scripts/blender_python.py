#!/usr/bin/env python3
"""Run Blender scripts with the genuine pinned bpy wheel on headless Linux.

Accepts the offline subset --background --python SCRIPT -- SCRIPT_ARGS.
Use a real Blender executable instead when one is available.
"""
import os
from pathlib import Path
import runpy
import sys
import traceback


def main():
    import bpy
    if bpy.app.version != (4, 5, 3):
        raise RuntimeError(f'Expected Blender 4.5.3; found {bpy.app.version_string}')
    if '--version' in sys.argv:
        print(f'Blender {bpy.app.version_string} (headless Python wheel)')
        return
    if '--python' not in sys.argv:
        raise ValueError('Expected --python SCRIPT [-- SCRIPT_ARGS]')
    script = Path(sys.argv[sys.argv.index('--python') + 1]).resolve(strict=True)
    sys.path.insert(0, str(script.parent))
    runpy.run_path(str(script), run_name='__main__')


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
    sys.stdout.flush()
    sys.stderr.flush()
    # Rendering and report writes are synchronous. Bypass the Python wheel's
    # scene-destruction path after the offline script has completed.
    os._exit(0)
