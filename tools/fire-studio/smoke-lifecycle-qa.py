"""Execute actual production soot chemistry at multiple CFL substep counts.

This is an isolated stationary-field numerical lifecycle gate, not browser FPS
or a visual-quality substitute. Run only in an assigned native GPU window.
"""
import argparse,hashlib,json,sys,time,traceback
from pathlib import Path

repo=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(repo/'work/smoke-shapes-qa/vendor'))
import numpy as np
import wgpu

ap=argparse.ArgumentParser()
ap.add_argument('--adapter',choices=['integrated','discrete'],default='integrated')
ap.add_argument('--fixture',default=str(repo/'work/fuel-studio-qa/smoke-lifecycle-fixture.json'))
ap.add_argument('--output')
args=ap.parse_args()
fixture=Path(args.fixture);data=json.loads(fixture.read_text())
output=Path(args.output) if args.output else fixture.parent/('smoke-lifecycle-'+args.adapter+'.json')
adapter=wgpu.gpu.request_adapter_sync(power_preference='low-power' if args.adapter=='integrated' else 'high-performance')
dev=adapter.request_device_sync();queue=dev.queue
report={'nativeOnly':True,'scope':'actual N8/D8 production correctScalar; stationary isolated soot; no visual/FPS claim','adapter':dict(adapter.info),'threshold':data['threshold'],
 'shaderSha256':{k:hashlib.sha256(data[k].encode()).hexdigest() for k in ('actual','legacy')},'cases':[],'pass':False}
resources=[]
def tex(size,format='rgba16float',dimension='3d'):
 texture=dev.create_texture(size=size,dimension=dimension,format=format,usage=wgpu.TextureUsage.TEXTURE_BINDING|wgpu.TextureUsage.STORAGE_BINDING|wgpu.TextureUsage.COPY_SRC|wgpu.TextureUsage.COPY_DST)
 resources.append(texture);return texture
def buf(values,usage):
 b=dev.create_buffer_with_data(data=values,usage=usage);resources.append(b);return b
def binding(slot,value):return {'binding':slot,'resource':{'buffer':value} if isinstance(value,wgpu.GPUBuffer) else value}
try:
 shaders={key:dev.create_shader_module(code=data[key],label='production-soot-'+key) for key in ('actual','legacy')}
 pipelines={key:dev.create_compute_pipeline(layout='auto',compute={'module':module,'entry_point':'main'}) for key,module in shaders.items()}
 sampler=dev.create_sampler(min_filter='linear',mag_filter='linear')
 velocity=tex((9,9,9));fields=[tex((8,8,8)),tex((8,8,8))]
 solid=tex((1,1,1));skin=tex((1,1,1));sigil=tex((1,1,1),'rgba8unorm','2d');floor=tex((1,1,1),'rgba32float','2d')
 object=buf(np.array([0,1,0,1,0,0,0,0,1,1,1,0],np.float32),wgpu.BufferUsage.UNIFORM)
 params=buf(np.zeros(28,np.float32),wgpu.BufferUsage.UNIFORM|wgpu.BufferUsage.COPY_DST)
 bricks=buf(np.array([0,0,0,0],np.uint32),wgpu.BufferUsage.STORAGE)
 occupancy=buf(np.zeros(1,np.uint32),wgpu.BufferUsage.STORAGE|wgpu.BufferUsage.COPY_DST|wgpu.BufferUsage.COPY_SRC)
 optical=buf(np.zeros(1,np.uint32),wgpu.BufferUsage.STORAGE|wgpu.BufferUsage.COPY_DST|wgpu.BufferUsage.COPY_SRC)
 groups={}
 for name,pipe in pipelines.items():
  for current in (0,1):
   entries=[binding(slot,value) for slot,value in [(0,params),(1,sampler),(2,velocity.create_view()),(3,fields[current].create_view()),(4,fields[current].create_view()),(5,fields[1-current].create_view()),(6,bricks),(7,occupancy),(8,sigil.create_view()),(10,optical),(11,solid.create_view()),(12,skin.create_view()),(13,object),(32,floor.create_view())]]
   groups[name,current]=dev.create_bind_group(layout=pipe.get_bind_group_layout(0),entries=entries)
 def read(current):return np.frombuffer(queue.read_texture({'texture':fields[current]},{'bytes_per_row':64,'rows_per_image':8},(8,8,8)),np.float16).reshape(8,8,8,4).copy()
 started=time.perf_counter()
 for case in data['scenarios']:
  initial=np.zeros((8,8,8,4),np.float16);initial[...,0]=case['density']
  queue.write_texture({'texture':fields[0]},initial,{'bytes_per_row':64,'rows_per_image':8},(8,8,8))
  current=0;first=None;first_clear=None
  for i,(dt,t,decay) in enumerate(case['schedule']):
   values=np.array([dt,t,.5,1,0,1,0,0,2,0,.35,0,0,1,.085,1,.45,.12,1.5,.55,1.2,1.15,1.2,1.6,decay,0,0,0],np.float32)
   queue.write_buffer(params,0,values)
   encoder=dev.create_command_encoder();encoder.clear_buffer(occupancy);encoder.clear_buffer(optical)
   p=encoder.begin_compute_pass();p.set_pipeline(pipelines[case['shader']]);p.set_bind_group(0,groups[case['shader'],current]);p.dispatch_workgroups(1,2,4);p.end();queue.submit([encoder.finish()]);current=1-current
   if i+1==case['substeps']:first=float(read(current)[0,0,0,0])
   if (i+1)%(case['substeps']*60)==0:
    density=float(read(current)[0,0,0,0])
    if first_clear is None and density==0:first_clear=(i+1)*dt
  result=read(current);density=float(result[0,0,0,0]);original=float(initial[0,0,0,0])
  entry={k:case[k] for k in ('kind','shader','substeps','seconds','decayTotal')}
  entry.update({'initial':original,'afterFirstFrame':first,'final':density,'analyticFinal':original*np.exp(-.045*case['seconds']),
   'uniformAcrossField':bool(np.all(result[...,0]==result[0,0,0,0])),'finite':bool(np.all(np.isfinite(result))),
   'otherChannelsZero':bool(np.count_nonzero(result[...,1:])==0),'firstWholeSecondClear':first_clear,
   'occupied':int(np.frombuffer(queue.read_buffer(occupancy),np.uint32)[0]),'optical':int(np.frombuffer(queue.read_buffer(optical),np.uint32)[0])})
  if case['kind']=='normal':passed=.85*original<density<.97*original and first>=.99*original
  elif case['kind'] in ('tail','tiny'):passed=density==0 and entry['occupied']==0 and entry['optical']==0
  elif case['kind']=='fresh':passed=density>=.99*original
  # Float16 texture writes may use an implementation rounding mode that
  # differs from the CPU nearest-even reference. The previous update can
  # stall OR over-decay. Its control gate checks substep dependence below.
  else:passed=0<=density<=original
  entry['pass']=bool(passed and entry['finite'] and entry['uniformAcrossField'] and entry['otherChannelsZero']);report['cases'].append(entry)
 report['wallSeconds']=time.perf_counter()-started
 for kind in ('normal','tail','fresh','tiny'):
  results=[case['final'] for case in report['cases'] if case['kind']==kind]
  report.setdefault('substepAgreement',{})[kind]={'maxAbs':max(results)-min(results),'values':results}
 legacy=[case['final'] for case in report['cases'] if case['kind']=='legacy-normal']
 report['legacySubstepDependence']={'values':legacy,'maxAbs':max(legacy)-min(legacy),'detected':max(legacy)-min(legacy)>.0004}
 report['pass']=all(case['pass'] for case in report['cases']) and all(result['maxAbs']==0 for result in report['substepAgreement'].values()) and report['legacySubstepDependence']['detected']
except Exception as error:
 report['error']={'type':type(error).__name__,'message':str(error)[:12000]};output.with_suffix('.log').write_text(traceback.format_exc())
finally:
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2));dev.destroy()
print(json.dumps({'path':str(output),'pass':report['pass'],'cases':len(report['cases']),'agreement':report.get('substepAgreement'),'error':report.get('error')}))
if not report['pass']:sys.exit(1)
