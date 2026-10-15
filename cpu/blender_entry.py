"""Blender-side entry point, with CPU enforcement and fresh frame isolation."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_runtime import main
arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
raise SystemExit(main(arguments))
