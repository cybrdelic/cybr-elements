from pathlib import Path
R=Path(__file__).resolve().parent
p=R/'foam.py';s=p.read_text(encoding='utf-8')
s=s.replace('if "--resume" in args and f<94:continue','if "--resume" in args and (out/f"{f:04}.jpg").exists():continue')
s=s.replace("frames=range(120) if '--full' in args else [42]", "frames=range(120) if '--full' in args else [20,42,90]")
s=s.replace('radius=min(.045,.012/(1-u*.97)**.5);centers.append(np.array(pos)+np.array(normal)*radius*.65);rs.append(radius)', '''radius=min(.044,.013/(1-u*.97)**.5)
    # Submerged cells enter continuously; film drainage is deterministic per cell.
    exposed=np.clip((.075-distance)/.028,0,1);exposed=exposed*exposed*(3-2*exposed)
    drain=np.clip((f/30-2.1-u*1.6)/.24,0,1)
    radius*=exposed*(1-.82*drain);centers.append(np.array(pos)+np.array(normal)*radius*.58);rs.append(radius)''')
s=s.replace('bv=(iv[None]*br[:,None,None]+bp[:,None]).reshape(-1,3);bf=', '''# Weighted contact planes flatten shared faces into packed cells.
  from mathutils.kdtree import KDTree
  kd=KDTree(len(bp))
  for bi,pt in enumerate(bp):kd.insert(Vector(pt),bi)
  kd.balance();packed=iv[None]*br[:,None,None]
  for bi,pt in enumerate(bp):
   if br[bi]<.001:continue
   for nb,bj,dist in kd.find_n(Vector(pt),9):
    if bj==bi or dist<1e-5 or dist>br[bi]+br[bj]:continue
    normal=(bp[bj]-pt)/dist;plane=max(.32*br[bi],(dist*dist+br[bi]**2-br[bj]**2)/(2*dist))
    penetration=np.maximum(0,packed[bi]@normal-plane)
    packed[bi]-=penetration[:,None]*normal
  bv=(packed+bp[:,None]).reshape(-1,3);bf=''')
s=s.replace('inner=(iv[None]*(br*.997)[:,None,None]+bp[:,None]).reshape(-1,3)', 'inner=(packed*.996+bp[:,None]).reshape(-1,3)')
p.write_text(s,encoding='utf-8')
# Retain the two mostly-good fluids and improve only their surface scale.
orig=(R.parent/'photo-foam.py').read_text(encoding='utf-8')
orig=orig.replace('R=Path(__file__).resolve().parent;', 'R=Path(__file__).resolve().parent.parent;')
orig=orig.replace("out=R/'subelements'/f'photo-{KIND}-frames'", "out=R/'realism'/f'{KIND}-frames'")
orig=orig.replace('s.cycles.samples=48','s.cycles.samples=96').replace('s.cycles.adaptive_threshold=.06','s.cycles.adaptive_threshold=.025')
orig=orig.replace('if "--resume" in args and f<94:continue','if "--resume" in args and (out/f"{f:04}.jpg").exists():continue')
orig=orig.replace('bump.inputs[\'Distance\'].default_value=.028', 'bump.inputs[\'Distance\'].default_value=.008')
orig=orig.replace("p.inputs['Roughness'].default_value=.21", "p.inputs['Roughness'].default_value=.16")
orig=orig.replace("frames=range(120) if '--full' in args else [40]", "frames=range(120) if '--full' in args else [42,90]")
(R/'fluids.py').write_text(orig,encoding='utf-8')
print('Patched packed foam and restrained fluid refinements')
