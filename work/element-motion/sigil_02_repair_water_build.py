from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'sigil_02_water_mesh.py').read_text().replace("B=R/'sigil-02-elements'","B=R/'sigil-02-repair'").replace('frames=range(294)','frames=range(192)')
# Stream all exact states; pilot only reconstructs selected frames, retaining
# their particle caches for rerendering. CPU silhouette sheets cover every state.
s=s.replace('from scipy.spatial import cKDTree','from scipy.spatial import cKDTree\nfrom PIL import Image,ImageDraw\nimport cv2')
s=s.replace("if full:\n  while len(list(out.glob('*.mesh.gz')))>=4:time.sleep(.5)","pilot=not (B/'water-continue').exists()\n if full and not pilot:\n  while len(list(out.glob('*.mesh.gz')))>=4:time.sleep(.5)")
s=s.replace(" if n>4:\n  origin=",''' if n:
  # CPU depth/speed preview is an explicit diagnostic, not the final render.
  xy=np.column_stack(((p[:,0]-m['origin'][0])/m['spaceScale'],(p[:,1]-m['origin'][1])/m['spaceScale']))
  uv=np.column_stack(((xy[:,0]/10.5+.5)*960,(.5-(xy[:,1]-1.8)/5.90625)*540)).astype(int)
  canvas=np.zeros((540,960,3),np.uint8);valid=(uv[:,0]>=0)&(uv[:,0]<960)&(uv[:,1]>=0)&(uv[:,1]<540)
  depth=p[:,2];order=np.argsort(depth)[::-1];col=np.column_stack((80+80*np.clip(depth/1.512,0,1),150+80*np.clip(depth/1.512,0,1),np.full(n,230))).astype(np.uint8)
  for i in order[valid[order]]:canvas[uv[i,1],uv[i,0]]=col[i]
  (B/'water-cpu').mkdir(exist_ok=True);Image.fromarray(canvas).save(B/'water-cpu'/f'{f:04}.jpg',quality=90)
 if pilot and f not in [24,45,66,87]:
  (source/f'{f:04}.gz').unlink();continue
 if n>4:
  origin=''')
s=s.replace("'meshSmoothingPasses':12","'meshSmoothingPasses':6").replace("'fieldSigma':.68","'fieldSigma':.48")
# Skip the hidden floor in reconstruction while keeping it in the simulation.
# Apply this only after release, away from the framing by > one world unit.
s=s.replace(" if n>4:\n  origin=", " if f>135 and n>4:\n  visible=p[:,1]>.48;p=p[visible];v=v[visible];n=len(p);isolated=np.empty(0,bool)\n if n>4:\n  origin=")
s=s.replace(" (source/f'{f:04}.gz').unlink()"," if not pilot:(source/f'{f:04}.gz').unlink()")
# The replacement above also modified the diagnostic skip; that skip must always consume.
s=s.replace("  if not pilot:(source/f'{f:04}.gz').unlink();continue","  (source/f'{f:04}.gz').unlink();continue")
(R/'sigil_02_repair_water_mesh.py').write_text(s)
s=(R/'sigil_02_water_render.py').read_text().replace('sigil-02-elements/','sigil-02-repair/').replace('frames=range(294)',"frames=range(192) if '--full' in args else [24,45,66,87]")
s=s.replace("s.cycles.device='GPU'","s.cycles.device='GPU' if '--full' in sys.argv else 'CPU'").replace('s.cycles.samples=96','s.cycles.samples=96 if \'--full\' in sys.argv else 24')
s=s.replace('s.render.resolution_x=1920;s.render.resolution_y=1080','s.render.resolution_x=1920 if \'--full\' in sys.argv else 1280;s.render.resolution_y=1080 if \'--full\' in sys.argv else 720')
s=s.replace("out=R/'sigil-02-repair/water-frames'","out=R/('sigil-02-repair/water-frames' if '--full' in sys.argv else 'sigil-02-repair/water-pilot')")
s=s.replace("location=(.85,-17,3.04)","location=(.65,-13.0,3.05)").replace('Vector((0,0,2.8875))','Vector((0,0,1.8))').replace('cam.data.lens=44','cam.data.lens=44')
s=s.replace(" if '--full' in args:"," if '--full' in args:")
(R/'sigil_02_repair_water_render.py').write_text(s)
print('Built isolated water meshing and render scripts.')
