"""Small CPU-only diagnostic images; never substitutes for production frames."""
from pathlib import Path
import bpy,numpy as np,os,json,time,hashlib
from mathutils import Vector
R=Path(__file__).resolve().parent

def configure(s):
 s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=int(os.environ.get('CYBR_CPU_SAMPLES','24'));s.cycles.adaptive_threshold=.04;s.cycles.adaptive_min_samples=8
 s.cycles.use_denoising=True;s.cycles.denoiser='OPENIMAGEDENOISE'
 if hasattr(s.cycles,'denoising_use_gpu'):s.cycles.denoising_use_gpu=False
 s.cycles.max_bounces=12;s.cycles.transmission_bounces=10;s.cycles.glossy_bounces=6;s.cycles.diffuse_bounces=2;s.cycles.volume_bounces=1
 s.render.threads_mode='FIXED';s.render.threads=2;s.render.use_persistent_data=False;s.render.resolution_x=512;s.render.resolution_y=384;s.render.resolution_percentage=100
 s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.color_depth='8';s.render.fps=30
 s.render.use_compositing=True
 if hasattr(s.render,'compositor_device'):s.render.compositor_device='CPU'
 assert s.cycles.device=='CPU'
 return s

def setup(samples=24):
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);s=configure(bpy.context.scene)
 s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast'
 w=bpy.data.worlds.new('CPU black optical stage');w.use_nodes=True;w.node_tree.nodes['Background'].inputs[0].default_value=(0,0,0,1);w.node_tree.nodes['Background'].inputs[1].default_value=0;s.world=w
 for name,loc,power,width,height,col in [('Broad neutral key',(-2,-4,5),1600,5,1.8,(1,.94,.84)),('Cool narrow rim',(2,1.6,3.8),1900,1.4,4,(.78,.89,1)),('Low strip',(-1,-1.5,-.1),500,4,.3,(1,1,1))]:
  d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='RECTANGLE';d.size=width;d.size_y=height;d.color=col;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.9))-o.location).to_track_quat('-Z','Y').to_euler()
 bpy.ops.object.camera_add(location=(.45,-15,1.90));cam=bpy.context.object;cam.rotation_euler=(Vector((.45,0,1.90))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=5.5;s.camera=cam
 return s

def finish(s,k,f):
 configure(s)
 if s.camera:
  center=float(os.environ.get('CYBR_CPU_VIEW_CENTER_X','.45'));s.camera.data.ortho_scale=float(os.environ.get('CYBR_CPU_VIEW_WIDTH','5.5'));s.camera.location=(center,-15,1.9);s.camera.rotation_euler=(Vector((center,0,1.9))-s.camera.location).to_track_quat('-Z','Y').to_euler()
 folder=Path(os.environ['CYBR_CPU_OUTPUT']);folder.mkdir(parents=True,exist_ok=True);file=folder/f'{k}-{f:04}.png';s.frame_set(f+1);s.render.filepath=str(file)
 start=time.time();bpy.ops.render.render(write_still=True)
 result={'kind':k,'frame':f,'device':s.cycles.device,'denoiser':s.cycles.denoiser,'denoisingGPU':getattr(s.cycles,'denoising_use_gpu',False),'threads':s.render.threads,'samples':s.cycles.samples,'size':[s.render.resolution_x,s.render.resolution_y],'seconds':round(time.time()-start,3),'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'purpose':'CPU diagnostic still, not production acceptance'}
 assert result['device']=='CPU' and not result['denoisingGPU'];file.with_suffix('.json').write_text(json.dumps(result,indent=2));print('CPU_IMAGE',k,f,result['seconds'],flush=True)

def visible_grains(p,r,scale=None):
 """Preview-only opaque surface culling at the actual image footprint.

 Retain the nearest two centers in each half-pixel column. Grain size and
 identity are unchanged; interior occluded grains are omitted from this view.
 Never apply to refractive or participating media.
 """
 if len(p)<90000:return np.arange(len(p))
 x=np.floor((p[:,0]-.45)/5.5*1024+512).astype('i4');z=np.floor((p[:,2]-1.9)/5.5*1024+384).astype('i4');key=x.astype('i8')+z.astype('i8')*4096;order=np.lexsort((p[:,1]-r,key));kk=key[order];start=np.r_[True,kk[1:]!=kk[:-1]];rank=np.arange(len(kk))-np.maximum.accumulate(np.where(start,np.arange(len(kk)),0));return order[rank<2]

def sanitize_legacy_cpu(code):
 """Remove GPU preference initialization before executing legacy scene setup."""
 code=code.replace("s.cycles.device='GPU'","s.cycles.device='CPU'").replace('s.cycles.denoiser="OPTIX"','s.cycles.denoiser="OPENIMAGEDENOISE"').replace("s.cycles.denoiser='OPTIX'","s.cycles.denoiser='OPENIMAGEDENOISE'")
 lines=[]
 for line in code.splitlines():
  if "preferences.addons['cycles'].preferences" in line or 'for dev in prefs.devices:' in line:continue
  lines.append(line)
 code='\n'.join(lines)
 assert not any(x in code for x in ['get_devices(',"compute_device_type",'OPTIX',"device='GPU'"]),'Unsafe legacy CPU scene'
 return code
