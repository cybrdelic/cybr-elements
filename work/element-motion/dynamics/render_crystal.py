"""Retain the stronger Bullet crystal construction; refine its optics only."""
import sys,json,hashlib
from pathlib import Path
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from scene import frames
source=R.parent/'realism/solids.py';code=source.read_text(encoding='utf-8').split("full='--full' in sys.argv")[0]
code=code.replace("out=R/'realism'/f'{KIND}-frames'","out=R/'dynamics/frames'/KIND")
namespace={'__file__':str(source),'__name__':'__crystal_scene__'};exec(compile(code,str(source),'exec'),namespace)
import bpy
s=namespace['s'];s.cycles.diffuse_bounces=2;s.cycles.samples=96
for mat in namespace['rockMats']:
    p=mat.node_tree.nodes.get('Principled BSDF')
    if p:p.inputs['Roughness'].default_value=.045
selected=set(frames());out=R/'frames/crystal';out.mkdir(parents=True,exist_ok=True)
for f in range(120):
    s.frame_set(f+1)
    if f in selected:s.render.filepath=str(out/f'{f:04}.jpg');bpy.ops.render.render(write_still=True)
(R/'crystal-mechanism.json').write_text(json.dumps({'source':str(source),'sourceHash':hashlib.sha256(source.read_bytes()).hexdigest(),'change':'Retain Bullet geometry and contacts; reduce polished perfect facets with restrained optical roughness','frames':sorted(selected)},indent=2),encoding='utf-8')
