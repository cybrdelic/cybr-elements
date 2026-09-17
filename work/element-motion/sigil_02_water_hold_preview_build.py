from pathlib import Path
r=Path(__file__).resolve().parent
s=(r/'sigil_02_water_hold_render.py').read_text()
s=s.replace("cache=R/'sigil-02-water-hold/mesh'", "cache=R/'sigil-02-water-hold/preview-mesh'")
s=s.replace("out=R/('sigil-02-water-hold/frames' if '--full' in sys.argv else 'sigil-02-water-hold/pilot')", "out=R/'sigil-02-water-hold/preview-frames'")
s=s.replace("s.cycles.device='GPU' if '--full' in sys.argv else 'CPU'", "s.cycles.device='GPU'")
s=s.replace("s.cycles.samples=96 if '--full' in sys.argv else 24", "s.cycles.samples=24")
s=s.replace("s.render.resolution_x=1920 if '--full' in sys.argv else 1280", "s.render.resolution_x=960")
s=s.replace("s.render.resolution_y=1080 if '--full' in sys.argv else 720", "s.render.resolution_y=540")
s=s.replace("frames=range(300) if '--full' in args else [45,75,120,165]", "frames=range(60,166,3)")
s=s.replace("if '--full' in args:\n  vectors.close()", "if True:\n  vectors.close()")
(r/'sigil_02_water_hold_preview_render.py').write_text(s)
print('Preview renderer ready: 36 frames, 960x540, OptiX, 24 samples')
