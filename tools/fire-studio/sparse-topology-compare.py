"""Compare old and revised allocation results on the native GPU, without a browser.

Only topology is dispatched. Requested pages, copied page tables, generation
counters, free lists, migration flags and indirect commands must match exactly.
"""
import argparse,json,sys,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'work/smoke-shapes-qa/vendor'))
import wgpu
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--adapter',choices=['discrete','integrated'],default='discrete');ap.add_argument('--out',required=True)
ap.add_argument('--baseline',default='work/sparse-startup-qa/rc16-d3d12-fxc',help='Baseline sparse-pipeline-qa export directory')
ap.add_argument('--candidate',help='Candidate sparse-pipeline-qa export directory; defaults to this adapter final FXC output')
args=ap.parse_args()
out=(root/args.out).resolve();assert out.is_relative_to(root/'work');out.mkdir(parents=True,exist_ok=False)
old=root/args.baseline;new=root/(args.candidate or 'work/sparse-startup-qa/final-'+args.adapter+'-fxc')
adapter=wgpu.gpu.request_adapter_sync(power_preference='high-performance' if args.adapter=='discrete' else 'low-power');device=adapter.request_device_sync();queue=device.queue
report={'nativeOnly':True,'adapter':dict(adapter.info),'comparisons':[],'pass':False}
try:
 for brick,capacity in [(16,1024),(16,512),(16,4),(32,64)]:
  pages=(256//brick)**3;count=16+capacity*6;prefix=f'{brick}-{capacity}-topology.wgsl'
  pipelines=[]
  for folder in [old,new]:
   code=(folder/prefix).read_text();module=device.create_shader_module(code=code,label=str(folder.name)+'-'+prefix)
   pipelines.append(device.create_compute_pipeline(layout='auto',compute={'module':module,'entry_point':'main'}))
  fixtures=['empty','new','retained-and-recycled','stale-generation','generation-limit','capacity-fallback','already-dense','cross-lane-pages']
  for name in fixtures:
   requested=np.zeros(pages,np.uint32);current=np.zeros((pages,2),np.uint32);meta=np.zeros(count,np.uint32);commands=np.zeros(21,np.uint32);meta[4]=capacity
   if name=='new':requested[3]=1
   if name=='retained-and-recycled':
    requested[[3,4,12]]=1;current[3]=[1,7];current[5]=[2,9];meta[16]=4;meta[16+capacity]=7;meta[17]=6;meta[17+capacity]=9
   if name=='stale-generation':requested[3]=1;current[3]=[1,6];meta[16]=4;meta[16+capacity]=7
   if name=='generation-limit':requested[3]=1;meta[16+capacity]=0xffffffff
   if name=='capacity-fallback':requested[:capacity+1]=1;current[5]=[1,7];meta[16]=6;meta[16+capacity]=7
   if name=='already-dense':
    resident=min(capacity,14);meta[:8]=[1,57,resident,0,capacity-resident,3,19,1];commands[:]=np.arange(21,dtype=np.uint32);current[3]=[1,7];meta[16]=4;meta[16+capacity]=7;requested[3]=1
   if name=='cross-lane-pages':requested[[0,15,16,pages//2,pages-1]]=1
   initial=[requested,current,np.zeros_like(current),meta,commands];results=[]
   for pipeline in pipelines:
    buffers=[device.create_buffer_with_data(data=v.tobytes(),usage=wgpu.BufferUsage.STORAGE|wgpu.BufferUsage.COPY_SRC) for v in initial]
    try:
     group=device.create_bind_group(layout=pipeline.get_bind_group_layout(0),entries=[{'binding':i,'resource':{'buffer':b}} for i,b in enumerate(buffers)])
     encoder=device.create_command_encoder();p=encoder.begin_compute_pass();p.set_pipeline(pipeline);p.set_bind_group(0,group);p.dispatch_workgroups(1);p.end();queue.submit([encoder.finish()])
     results.append([bytes(queue.read_buffer(b)) for b in buffers])
    finally:
     for b in buffers:b.destroy()
   matches=[a==b for a,b in zip(*results)];assert all(matches),f'{brick}/{capacity}/{name}: allocator outputs differ'
   state=np.frombuffer(results[1][3],np.uint32)
   report['comparisons'].append({'brick':brick,'capacity':capacity,'fixture':name,'exactBufferMatches':matches,'mode':int(state[0]),'resident':int(state[2]),'overflow':int(state[5]),'migration':int(state[7]),'sha256':[hashlib.sha256(b).hexdigest() for b in results[1]]})
 report['pass']=len(report['comparisons'])==32
finally:
 device.destroy();(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'report':str(out/'report.json'),'pass':report['pass'],'comparisons':len(report['comparisons'])}))
