"""A bounded Mantaflow motion test driven by the original sigil nozzle path.

This uses native liquid transport, pressure and meshing. The black-stage bending
support is authored through gravity timing. No fixed letter surface is rendered.
"""
from pathlib import Path
import bpy,numpy as np,json,time,sys,hashlib
R=Path(__file__).resolve().parent;V='01';out=R/f'native-liquid-{V}-v2';out.mkdir(exist_ok=True)
data=np.load(R.parent/'sigils'/f'source-{V}.npz')
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.frame_start=1;s.frame_end=90;s.render.fps=30;s.gravity=(0,0,0)
for frame,gravity in [(1,(0,0,0)),(69,(0,0,0)),(78,(0,0,-2.8)),(90,(0,0,-2.8))]:
    s.gravity=gravity;s.keyframe_insert(data_path='gravity',frame=frame)
bpy.ops.mesh.primitive_cube_add(location=(0,0,2.2));domain=bpy.context.object;domain.name='Native liquid simulation';domain.dimensions=(10.8,1.8,6.4);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
mod=domain.modifiers.new('FLIP liquid','FLUID');mod.fluid_type='DOMAIN';d=mod.domain_settings;d.domain_type='LIQUID';d.resolution_max=384;d.cache_frame_start=1;d.cache_frame_end=90;d.cache_directory=str(out/'cache');d.cache_type='MODULAR';d.cache_data_format='UNI';d.cache_mesh_format='BOBJECT';d.cache_resumable=True;d.timesteps_min=1;d.timesteps_max=16;d.time_scale=1;d.use_diffusion=True;d.viscosity_base=5;d.viscosity_exponent=6;d.surface_tension=.045;d.use_mesh=True;d.mesh_scale=2;d.mesh_particle_radius=1.65;d.mesh_generator='IMPROVED';d.mesh_smoothen_pos=2;d.mesh_smoothen_neg=2
for direction in ['front','back','right','left','top','bottom']:setattr(d,'use_collision_border_'+direction,False)
bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=1);emitter=bpy.context.object;emitter.name='Original sigil drawing source'
flow=emitter.modifiers.new('Moving liquid source','FLUID');flow.fluid_type='FLOW';f=flow.flow_settings;f.flow_type='LIQUID';f.flow_behavior='INFLOW';f.flow_source='MESH';f.use_initial_velocity=True;f.velocity_factor=.015;f.velocity_normal=0;f.subframes=8;emitter.hide_render=True
for frame in np.arange(1.,90.001,.125):
    t=(frame-1)/30;at=min(t*3.4,6.827);p=np.array([np.interp(at,data['times'],data['points'][:,i]) for i in range(2)]);p0=np.array([np.interp(max(0,at-.025),data['times'],data['points'][:,i]) for i in range(2)]);p1=np.array([np.interp(min(6.827,at+.025),data['times'],data['points'][:,i]) for i in range(2)]);direction=(p1-p0)/max(np.linalg.norm(p1-p0),1e-8)
    ix=int(np.clip(round((p[0]+5.25)/10.5*511),0,511));iz=int(np.clip(round(p[1]/5.8*319),0,319));radius=float(np.clip(data['sdf'][iz,ix]*.80,.075,.19))
    emitter.location=(float(p[0]),0,float(p[1]));emitter.scale=(radius,radius*.72,radius)
    fresh=abs(float(data['arrival'][iz,ix])-at)<.18;f.use_inflow=bool(t<2.01 and fresh);f.velocity_coord=(float(direction[0]*.09),0,float(direction[1]*.09))
    emitter.keyframe_insert(data_path='location',frame=frame);emitter.keyframe_insert(data_path='scale',frame=frame);f.keyframe_insert(data_path='use_inflow',frame=frame);f.keyframe_insert(data_path='velocity_coord',frame=frame)
for action in bpy.data.actions:
    for fc in getattr(action,'fcurves',[]):
        for k in fc.keyframe_points:k.interpolation='LINEAR' if fc.data_path!='use_inflow' else 'CONSTANT'
s.frame_set(1);bpy.context.view_layer.objects.active=domain;bpy.ops.object.select_all(action='DESELECT');domain.select_set(True)
s.render.threads_mode='FIXED';s.render.threads=4;bpy.ops.wm.save_as_mainfile(filepath=str(out/'native-liquid.blend'))
start=time.time();print('BAKE DATA: 384-cell domain, 90-frame motion test',flush=True);bpy.ops.fluid.bake_data();assert d.has_cache_baked_data,'Native liquid data did not bake'
print('BAKE MESH',flush=True);bpy.ops.fluid.bake_mesh();assert d.has_cache_baked_mesh,'Native liquid mesh did not bake'
bpy.ops.wm.save_as_mainfile(filepath=str(out/'native-liquid.blend'))
report={'variant':V,'frames':90,'fps':30,'testSeconds':3,'resolution':384,'meshUpscale':2,'seconds':time.time()-start,'sourceSha256':hashlib.sha256((R.parent/'sigils'/f'source-{V}.npz').read_bytes()).hexdigest(),'solver':'Blender Mantaflow FLIP liquid','support':'Authored zero-gravity formation; gravity introduced on release','sourceSamplingHz':240,'status':'Native motion cache; requires visual review, not a final 15-second intro'}
(out/'report.json').write_text(json.dumps(report,indent=2));print('NATIVE MOTION CACHE COMPLETE',flush=True)
