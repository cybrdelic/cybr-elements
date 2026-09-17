from pathlib import Path
import gzip,struct,sys,json
import numpy as np
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent;P=R.parent
birth=np.full(200000,999);seen=0;rest_density=np.zeros(200000)
out=R/'lava-fields';out.mkdir(exist_ok=True)
for f in range(120):
 raw=gzip.decompress((P/'viscous-cache'/f'{f:04}.gz').read_bytes());count=len(raw)//24;pos=np.frombuffer(raw,'<f4',count*3).reshape(-1,3);birth[seen:count]=f
 if not count:np.savez_compressed(out/f'{f:04}.npz',heat=np.zeros(0),strain=np.zeros(0));continue
 # Number density supplies a persistent estimate of local surface stretch.
 kd=cKDTree(pos);dist,_=kd.query(pos,k=min(13,count));density=1/np.maximum(.001,dist[:,-1])**3
 rest_density[seen:count]=density[seen:count];seen=count;strain=np.clip(1-density/np.maximum(1e-5,rest_density[:count]),0,1)
 age=(f-birth[:count])/30;surface=np.clip(dist[:,-1]/.035-.65,0,1);heat=850+750*np.exp(-age*(.20+.24*surface))
 np.savez_compressed(out/f'{f:04}.npz',heat=heat.astype('f4'),strain=strain.astype('f4'))
print('120 temperature/stretch fields cached')
s=(P/'photo-lava-refined.py').read_text(encoding='utf-8')
s=s.replace('R=Path(__file__).resolve().parent;', 'R=Path(__file__).resolve().parent.parent;')
s=s.replace("out=R/'subelements'/f'refined-{KIND}-frames'", "out=R/'realism'/f'{KIND}-frames'")
s=s.replace('s.cycles.samples=48','s.cycles.samples=96').replace('s.cycles.adaptive_threshold=.06','s.cycles.adaptive_threshold=.025')
s=s.replace("frames=range(120) if '--full' in args else [50]", "frames=range(120) if '--full' in args else [20,42,75,105]")
s=s.replace("tempattr=me.attributes.new('Temperature','FLOAT','POINT')", "thermal=np.load(R/'realism/lava-fields'/f'{f:04}.npz');tempattr=me.attributes.new('Temperature','FLOAT','POINT');stretch=me.attributes.new('Stretch','FLOAT','POINT')")
s=s.replace("tempattr.data[vi].value=800+650*np.exp(-age*.65)", "tempattr.data[vi].value=float(thermal['heat'][pid]);stretch.data[vi].value=float(thermal['strain'][pid])")
s=s.replace("rad=rng.uniform(.018,.052)*min(1,age/.18)", "rad=rng.uniform(.032,.078)*min(1,age/.25)*(1-.55*float(thermal['strain'][pid]))")
s=s.replace("if age<.025:continue", "if age<.12:continue")
s=s.replace("if q is None or dist>.06:continue", "if q is None or dist>.06 or thermal['strain'][pid]>.65:continue")
# Add scanned pitted basalt scale and localized reheating where the skin stretches.
marker="elif KIND=='mud':"
injection="""
 tex=cn.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(R/'realism/assets/rock_boulder_cracked_nor_gl_2k.jpg'));tex.image.colorspace_settings.name='Non-Color';tex.projection='BOX';tex.projection_blend=.3;nm=cn.new('ShaderNodeNormalMap');nm.inputs['Strength'].default_value=.55;cl.new(tex.outputs[0],nm.inputs['Color']);cl.new(nm.outputs[0],cp.inputs['Normal'])
 atstrain=n.new('ShaderNodeAttribute');atstrain.attribute_name='Stretch';stgain=n.new('ShaderNodeMath');stgain.operation='MULTIPLY';stgain.inputs[1].default_value=1.2;l.new(atstrain.outputs['Fac'],stgain.inputs[0]);l.new(stgain.outputs[0],mask.inputs[1]);gain.inputs[1].default_value=2.1
"""
s=s.replace(marker,injection+'\n'+marker,1)
(R/'lava.py').write_text(s,encoding='utf-8')
print('Lava renderer written')
