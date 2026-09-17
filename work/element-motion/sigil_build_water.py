"""Adapt the verified v5 surface/optical renderer; retain original sources."""
from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'bending-mesh-v5.py').read_text(encoding='utf-8')
s=s.replace("B=R/'bending-rebuild-v5';source=B/'water-particles';out=B/'water-mesh-calibrated'", "variant=sys.argv[1];assert variant in ['01','02'];B=R/f'sigil-v1/water-{variant}';source=B/'particles';out=B/'meshes'")
s=s.replace("full='--full' in sys.argv;frames=range(120) if full else [42]", "full=True;frames=range(300)")
s=s.replace(">=5:time.sleep(.5)", ">=3:time.sleep(.5)")
s=s.replace("print('MESH',f,'verts'", "(source/f'{f:04}.gz').unlink()\n print('MESH',f,'verts'")
s=s.replace("assert np.isfinite(verts).all() and np.isfinite(vv).all()", "assert np.isfinite(verts).all() and np.isfinite(vv).all() and np.isfinite(p).all() and np.isfinite(v).all()")
(R/'sigil_mesh.py').write_text(s,encoding='utf-8')
s=(R/'bending-water-render-v5.py').read_text(encoding='utf-8')
start=s.index("R=Path(__file__)");end=s.index("\ns=bpy.context.scene",start)
s=s[:start]+"R=Path(__file__).resolve().parent;args=sys.argv[sys.argv.index('--')+1:];variant=args[0];assert variant in ['01','02'];B=R/f'sigil-v1/water-{variant}';cache=B/'meshes';out=B/'frames';out.mkdir(exist_ok=True)\nwhile not (cache/'manifest.json').exists():time.sleep(.5)\nmanifest=json.loads((cache/'manifest.json').read_text())"+s[end:]
s=s.replace("(0,0,1.8)","(0,0,2.95)")
s=s.replace("location=(2.8,-13,3.3)","location=(.45,-18,3.10)")
s=s.replace("(0,0,1.903125)","(0,0,2.95)").replace("cam.data.lens=45", "cam.data.lens=57")
s=s.replace("frames=range(120) if '--full' in args else [42]", "frames=range(300)")
s=s.replace("if '--full' in args and", "if")
s=s.replace("if '--full' in args:", "if True:")
# Every run reconstructs the spray history from its first frame.
s=s.replace("s.render.use_motion_blur=True;", "t=f/30;zoom=max(0,min(1,(t-2.4)/1));zoom=zoom*zoom*(3-2*zoom);cam.data.lens=57*(1.08-.08*zoom)\n s.render.use_motion_blur=True;")
s=s.replace("print('COMPLETE',flush=True)", "print('COMPLETE',flush=True)")
gate="\n if f==120 and '--ungated' not in args:\n  print('REVIEW GATE water '+variant,flush=True)\n  while not (R/f'sigil-v1/continue-water-{variant}').exists():time.sleep(.5)\n"
s=s.replace("print('COMPLETE',flush=True)",gate+"print('COMPLETE',flush=True)")
(R/'sigil_water_render.py').write_text(s,encoding='utf-8')
print('Prepared water mesh and optical render adapters.')
