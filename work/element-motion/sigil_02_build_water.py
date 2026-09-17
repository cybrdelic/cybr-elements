from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'bending-mesh-v5.py').read_text()
s=s.replace("B=R/'bending-rebuild-v5';source=B/'water-particles';out=B/'water-mesh-calibrated'","B=R/'sigil-02-elements';source=B/'water-particles';out=B/'water-mesh'")
s=s.replace("full='--full' in sys.argv;frames=range(120) if full else [42]","full=True;frames=range(294)")
s=s.replace('>=5:time.sleep(.5)','>=4:time.sleep(.5)')
s=s.replace(" print('MESH',f", " (source/f'{f:04}.gz').unlink()\n print('MESH',f")
(R/'sigil_02_water_mesh.py').write_text(s)
s=(R/'bending-water-render-v5.py').read_text()
s=s.replace("cache=R/'bending-rebuild-v5/water-mesh-calibrated';manifest=json.loads((cache/'manifest.json').read_text());out=R/'bending-rebuild-v5/water-final-frames';out.mkdir(exist_ok=True)","cache=R/'sigil-02-elements/water-mesh';out=R/'sigil-02-elements/water-frames';out.mkdir(exist_ok=True)\nwhile not (cache/'manifest.json').exists():time.sleep(.5)\nmanifest=json.loads((cache/'manifest.json').read_text())")
s=s.replace('resolution_x=2560','resolution_x=1920').replace('resolution_y=1440','resolution_y=1080')
s=s.replace('location=(2.8,-13,3.3)','location=(.85,-17,3.04)').replace('(0,0,1.903125)','(0,0,2.8875)').replace('cam.data.lens=45','cam.data.lens=44')
s=s.replace("frames=range(120) if '--full' in args else [42]","frames=range(294)")
s=s.replace("if '--full' in args and",'if').replace("if '--full' in args:",'if True:')
# Camera sees the same 14m wide framing as fire, with a slight view of depth.
s=s.replace("print('COMPLETE',flush=True)"," if f==135:\n  print('WATER REVIEW GATE',flush=True)\n  while not (R/'sigil-02-elements/continue-water').exists():time.sleep(.5)\nprint('COMPLETE',flush=True)")
(R/'sigil_02_water_render.py').write_text(s)
compile(s,'water-render','exec');print('Water stream and optical renderer prepared.')
