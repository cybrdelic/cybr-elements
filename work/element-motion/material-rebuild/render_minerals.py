"""Keep the existing wave and rigid-body motion; refine resolved mineral detail."""
from pathlib import Path
import sys,os
R=Path(__file__).resolve().parent;D=R.parent/'dynamics';sys.path.insert(0,str(R))
K=sys.argv[sys.argv.index('--kind')+1]
if K=='seismic':
 source=D/'seismic.py';code=source.read_text()
 code=code.replace('from scene import *','from scene import *\nfrom common import setup as quality_setup, finish as quality_finish\nsetup=lambda samples=192:quality_setup(secondary_environment=True)\nfinish=quality_finish')
 code=code.replace('grain_count=22000','grain_count=240000').replace('grain_r=.007+.020*rng.random(grain_count)**5','grain_r=.0024+.012*rng.random(grain_count)**10').replace('light.energy*=.85','light.energy*=.50').replace("b.inputs['Distance'].default_value=.012","b.inputs['Distance'].default_value=.0009")
 # Continuous interpolation removes visible rings caused by rounding every
 # particle onto one of 420 cross-sections of the wave guide.
 code=code.replace("grain_rest=centers[grain_index]+normal[grain_index]", "grain_u=(grain_t-.08)/1.6*(N-1);grain_i=np.minimum(grain_u.astype(int),N-2);grain_a=grain_u-grain_i;grain_centers=centers[grain_i]*(1-grain_a[:,None])+centers[grain_i+1]*grain_a[:,None];grain_normals=normal[grain_i]*(1-grain_a[:,None])+normal[grain_i+1]*grain_a[:,None];grain_rest=grain_centers+grain_normals")
 code=code.replace("gp=grain_rest+normal[grain_index]*np.array(history[f])[grain_index,None]", "wave=np.array(history[f]);displacement=wave[grain_i]*(1-grain_a)+wave[grain_i+1]*grain_a;gp=grain_rest+grain_normals*displacement[:,None]")
 code=code.replace("(R/'seismic-mechanism.json')","(Q/'seismic-mechanism.json')")
 exec(compile(code,str(source),'exec'),{'__file__':str(source),'__name__':'__quality_mineral__','Q':R})
else:
 import bpy
 from common import selected,finish
 source=D.parent/'realism/solids.py';code=source.read_text().split("full='--full' in sys.argv")[0]
 if os.environ.get('CYBR_CPU_PROOF')=='1':
  from cpu_stage import sanitize_legacy_cpu
  code=sanitize_legacy_cpu(code)
 code=code.replace("out=R/'realism'/f'{KIND}-frames'","out=Q/'frames'/KIND")
 ns={'__file__':str(source),'__name__':'__quality_crystal__','Q':R};exec(compile(code,str(source),'exec'),ns)
 s=ns['s'];s.cycles.samples=192;s.cycles.adaptive_threshold=.008;s.cycles.max_bounces=20;s.cycles.transmission_bounces=16;s.render.image_settings.quality=97
 for mat in ns['rockMats'][:2]:
  n=mat.node_tree.nodes;l=mat.node_tree.links;p=n['Principled BSDF'];p.inputs['Roughness'].default_value=.032
  for node in n:
   if node.type=='VOLUME_ABSORPTION' and node.inputs['Density'].default_value>1:node.inputs['Density'].default_value=2.7
  coord=n.new('ShaderNodeTexCoord');map=n.new('ShaderNodeVectorMath');map.operation='MULTIPLY';map.inputs[1].default_value=(1,1,180);l.new(coord.outputs['Generated'],map.inputs[0]);tex=n.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=6;tex.inputs['Detail'].default_value=2;l.new(map.outputs[0],tex.inputs[0]);b=n.new('ShaderNodeBump');b.inputs['Distance'].default_value=.00018;b.inputs['Strength'].default_value=.12;l.new(tex.outputs['Fac'],b.inputs['Height']);l.new(b.outputs[0],p.inputs['Normal'])
 for ob in bpy.data.objects:
  if ob.name.startswith('Layered stone'):
   b=ob.modifiers.new('Minute polished facet edges','BEVEL');b.width=.0025;b.segments=2
 requested=set(selected())
 for f in range(120):
  s.frame_set(f+1)
  if f in requested:finish(s,'crystal',f)
