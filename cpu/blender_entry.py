"""Blender-side entry point; kept separate so Blender cannot reinterpret CLI flags."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from flow import main
arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
raise SystemExit(main(['_blender-worker', *arguments]))
