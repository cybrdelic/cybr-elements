"""Replay recorded production JS commands offscreen, without a browser.

Only COPY_SRC usage is added for evidence readback. Pipeline layouts, bound
resources, shaders, dispatches, pass boundaries and submission order are the
recorded production values. This does not measure browser FPS or RAF pacing.
"""
import argparse, hashlib, json, re, sys, time, traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
Q = REPO / 'work/adaptive-volume-qa'
ap = argparse.ArgumentParser()
ap.add_argument('recording')
ap.add_argument('--adapter', choices=['integrated', 'discrete'], default='integrated')
ap.add_argument('--profile', action='store_true', help='Calibrated native timestamps per recorded submission')
ap.add_argument('--save-fields', action='store_true', help='Save full snapshot RGBA16F fields as .npy evidence')
ap.add_argument('--output', help='New output subdirectory under the recording; preserves previous evidence')
args = ap.parse_args()
source = Path(args.recording)
if not source.is_absolute(): source = Q / source
if source.is_dir(): source = source / 'commands.json'
data = json.loads(source.read_text())
folder = (source.parent / (args.output or ('native-' + args.adapter))).resolve()
if not folder.is_relative_to(source.parent.resolve()) or folder == source.parent.resolve():
    ap.error('--output must stay within the recording directory.')
folder.mkdir(exist_ok=False)
# Existing local QA dependencies are optional; ordinary installed packages work.
sys.path.insert(0, str(REPO / 'work/smoke-shapes-qa/vendor'))
import wgpu
import numpy as np
from PIL import Image

adapter = wgpu.gpu.request_adapter_sync(power_preference='low-power' if args.adapter == 'integrated' else 'high-performance')
dev = adapter.request_device_sync(required_features=['timestamp-query'] if args.profile else [])
queue = dev.queue
objects, descriptions = {}, {r['id']: r for r in data['resources']}
report = {'nativeOnly': True, 'recording': str(source), 'options': data.get('options'), 'adapter': dict(adapter.info),
    'textureCopySrcReadbackUsageAdded': True, 'resourceCount': len(data['resources']), 'submissions': [], 'frames': [], 'pass': False}
location = {}
pending_submissions = []

def snake(key): return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', key).lower()
def resolve(value):
    if isinstance(value, list): return [resolve(v) for v in value]
    if isinstance(value, dict):
        if '$ref' in value: return objects[value['$ref']]
        return {snake(k): resolve(v) for k, v in value.items()}
    return value
def size3(size):
    if isinstance(size, dict): return (size['width'], size.get('height',1), size.get('depthOrArrayLayers',size.get('depth_or_array_layers',1)))
    return tuple(size) + (1,) * (3-len(size))
def create(item):
    global location
    location = {'resource': item['id'], 'kind': item['kind'], 'label': item['desc'].get('label')}
    kind, desc = item['kind'], resolve(item['desc'])
    if kind == 'texture': desc['usage'] |= wgpu.TextureUsage.COPY_SRC;return dev.create_texture(**desc)
    if kind == 'view': texture = desc.pop('texture');return texture.create_view(**desc)
    if kind == 'buffer': return dev.create_buffer(**desc)
    if kind == 'sampler': return dev.create_sampler(**desc)
    if kind == 'module': return dev.create_shader_module(**desc)
    if kind == 'computePipeline': return dev.create_compute_pipeline(**desc)
    if kind == 'renderPipeline': return dev.create_render_pipeline(**desc)
    if kind == 'bindGroup':
        layout = desc['layout'];desc['layout'] = layout['pipeline'].get_bind_group_layout(layout['index'])
        return dev.create_bind_group(**desc)
    raise RuntimeError('Unsupported recorded resource: ' + kind)

def command(encoder, record, ordinal):
    global location
    location = {'command': ordinal, 'kind': record['kind']}
    kind = record['kind']
    if kind == 'clearBuffer':
        encoder.clear_buffer(objects[record['buffer']], record['offset'], record.get('size'));return
    if kind == 'copyBuffer':
        encoder.copy_buffer_to_buffer(objects[record['src']],record['srcOffset'],objects[record['dst']],record['dstOffset'],record['size']);return
    if kind not in ('compute','render'): raise RuntimeError('Unsupported recorded command: ' + kind)
    desc = resolve(record['desc'])
    p = encoder.begin_compute_pass(**desc) if kind == 'compute' else encoder.begin_render_pass(**desc)
    pipeline = None
    for sub_index, sub in enumerate(record['commands']):
        location = {'command': ordinal, 'kind': kind, 'subCommand': sub_index, 'operation': sub['kind'], 'pipeline': pipeline}
        if sub['kind'] == 'pipeline': pipeline = sub['id'];p.set_pipeline(objects[pipeline])
        elif sub['kind'] == 'group': p.set_bind_group(sub['index'],objects[sub['id']])
        elif sub['kind'] == 'dispatch': p.dispatch_workgroups(*sub['work'])
        elif sub['kind'] == 'indirect': p.dispatch_workgroups_indirect(objects[sub['buffer']],sub['offset'])
        elif sub['kind'] == 'draw': p.draw(*sub['work'])
        else: raise RuntimeError('Unsupported recorded pass operation: ' + sub['kind'])
    p.end()

def read_image(texture_id, name):
    desc = descriptions[texture_id]['desc'];width,height,depth=size3(desc['size'])
    if desc['format'] not in ('rgba8unorm','bgra8unorm'): raise RuntimeError('Unsupported snapshot format: '+desc['format'])
    raw = queue.read_texture({'texture':objects[texture_id]}, {'bytes_per_row':width*4,'rows_per_image':height},(width,height,depth))
    pixels=np.frombuffer(raw,np.uint8).reshape(depth,height,width,4)[0].copy()
    if desc['format']=='bgra8unorm': pixels=pixels[:,:,[2,1,0,3]]
    target=folder/(name+'.png');Image.fromarray(pixels,'RGBA').save(target)
    return {'path':str(target),'width':width,'height':height,'sha256':hashlib.sha256(raw).hexdigest(),
        'nonzeroRGB':int(np.count_nonzero(pixels[:,:,:3])),'meanRGB':pixels[:,:,:3].mean(axis=(0,1)).tolist()}

def read_chemistry(frame):
    pool=frame.get('pool');state=None;stale=0
    if pool:
        state=np.frombuffer(queue.read_buffer(objects[pool['metadata']]),np.uint32).copy()
    if not pool or state[0]==1:
        raw=queue.read_texture({'texture':objects[frame['dense']]},{'bytes_per_row':256*8,'rows_per_image':256},(256,256,256))
        values=np.frombuffer(raw,np.float16).reshape(256,256,256,4).copy()
    else:
        plan=pool['plan'];brick=plan['brick'];tx,ty,tz=plan['tiles'];ax,ay,az=plan['atlasSize'];axis=plan['pagesAxis'];offset=plan['offsets']
        pages=np.frombuffer(queue.read_buffer(objects[pool['pages']]),np.uint32).reshape(-1,2)
        raw=queue.read_texture({'texture':objects[pool['atlas']]},{'bytes_per_row':ax*8,'rows_per_image':ay},(ax,ay,az))
        atlas=np.frombuffer(raw,np.float16).reshape(az,ay,ax,4)
        values=np.zeros((256,256,256,4),np.float16)
        for logical,(mapped,generation) in enumerate(pages):
            if mapped==0: continue
            slot=int(mapped)-1
            if slot>=plan['capacity'] or generation!=state[offset['generation']+slot] or state[offset['owner']+slot]!=logical+1:
                stale+=1;continue
            px,py,pz=logical%axis,(logical//axis)%axis,logical//(axis*axis)
            sx,sy,sz=slot%tx,(slot//tx)%ty,slot//(tx*ty)
            values[pz*brick:(pz+1)*brick,py*brick:(py+1)*brick,px*brick:(px+1)*brick]=atlas[sz*brick:(sz+1)*brick,sy*brick:(sy+1)*brick,sx*brick:(sx+1)*brick]
    flat=values.reshape(-1,4);finite=np.isfinite(flat);result={'mode':'sparse' if pool and state[0]==0 else 'dense','staleMappings':stale,
        'sha256':hashlib.sha256(values).hexdigest(),'nonFinite':int(np.count_nonzero(~finite)),
        'nonzeroByChannel':np.count_nonzero(flat,axis=0).tolist(),'sumByChannel':flat.sum(axis=0,dtype=np.float64).tolist(),
        'maxByChannel':flat.max(axis=0).astype(float).tolist(),'minByChannel':flat.min(axis=0).astype(float).tolist()}
    if pool: result['poolStatus']={name:int(state[i]) for i,name in enumerate(['mode','requested','resident','allocated','free','overflow','epoch','migration'])}
    if args.save_fields and frame.get('saveField', True):
        target=folder/('chemistry-'+str(frame['index'])+'.npy');np.save(target,values);result['path']=str(target)
    return result

try:
    started=time.perf_counter()
    for resource in data['resources']: objects[resource['id']]=create(resource)
    report['compileAndResourcesSeconds']=time.perf_counter()-started
    if args.profile:
        from wgpu.backends.wgpu_native._api import libf
        period=float(libf.wgpuQueueGetTimestampPeriod(queue._internal));report['timestampPeriodNs']=period
        query=dev.create_query_set(type='timestamp',count=2)
        resolved=dev.create_buffer(size=16,usage=wgpu.BufferUsage.QUERY_RESOLVE|wgpu.BufferUsage.COPY_SRC)
    for operation_index, operation in enumerate(data['operations']):
        location={'operation':operation_index,'kind':operation['kind']}
        kind=operation['kind']
        if kind=='writeBuffer': queue.write_buffer(objects[operation['buffer']],operation['offset'],(source.parent/operation['file']).read_bytes())
        elif kind=='writeTexture': queue.write_texture(resolve(operation['target']),(source.parent/operation['file']).read_bytes(),resolve(operation['layout']),operation['size'])
        elif kind=='submit':
            started=time.perf_counter();encoder=dev.create_command_encoder()
            if args.profile:
                p=encoder.begin_compute_pass(timestamp_writes={'query_set':query,'beginning_of_pass_write_index':0});p.end()
            for command_index, record in enumerate(operation['commands']): command(encoder,record,command_index)
            if args.profile:
                p=encoder.begin_compute_pass(timestamp_writes={'query_set':query,'beginning_of_pass_write_index':1});p.end();encoder.resolve_query_set(query,0,2,resolved,0)
            queue.submit([encoder.finish()]);timing={'operation':operation_index,'commands':len(operation['commands'])}
            if args.profile:
                ticks=np.frombuffer(queue.read_buffer(resolved),np.uint64);timing['gpuMs']=float(ticks[1]-ticks[0])*period/1e6
                timing['completedWallMs']=(time.perf_counter()-started)*1000
            report['submissions'].append(timing)
            pending_submissions.append(timing)
        elif kind=='frame':
            result={'index':operation['index'],'time':operation['time'], 'submissionCount':len(pending_submissions)}
            if args.profile:
                result['gpuMs']=sum(s['gpuMs'] for s in pending_submissions)
                result['completedWallMs']=sum(s['completedWallMs'] for s in pending_submissions)
            pending_submissions.clear()
            if 'stats' in operation:
                stats=np.frombuffer(queue.read_buffer(objects[operation['stats']]),np.float32).copy()
                substeps=operation['substeps'];step_dt=operation['dt']/max(1,substeps)
                result['stats']={'maxSpeed':float(stats[0]),'preDivergenceMean':float(stats[1]/max(1,stats[3])),
                    'postDivergenceMean':float(stats[2]/max(1,stats[3])),'cellCount':float(stats[3]),'substeps':substeps,'stepDt':step_dt,
                    'measuredCFL':float(stats[0])*step_dt/(6/128),'cflLimit':1.5,'withinMeasuredCFL':bool(stats[0]*step_dt<=1.5*6/128)}
                if not np.all(np.isfinite(stats)) or not result['stats']['withinMeasuredCFL']:
                    report['frames'].append(result)
                    raise RuntimeError('Recorded telemetry fixture is unsafe at frame '+str(operation['index'])+
                        ': measured CFL='+str(result['stats']['measuredCFL'])+'. No performance acceptance is valid beyond this point.')
            if operation.get('snapshot'):
                result['image']=read_image(operation['output'],'frame-'+str(operation['index']))
                if 'dense' in operation and operation.get('saveField', True):
                    result['chemistry']=read_chemistry(operation)
                    if result['chemistry']['nonFinite'] or result['chemistry']['staleMappings']:
                        report['frames'].append(result)
                        raise RuntimeError('Non-finite chemistry or stale page ownership at frame '+str(operation['index']))
            if operation.get('pool'):
                state=np.frombuffer(queue.read_buffer(objects[operation['pool']['metadata']]),np.uint32)
                result['poolStatus']=state[:8].tolist()
            report['frames'].append(result)
            (folder/'progress.json').write_text(json.dumps({'frames':len(report['frames']),'last':result},indent=2))
        else: raise RuntimeError('Unsupported recorded operation: '+kind)
    report['pass']=True
except Exception as error:
    report['error']={'location':location,'type':type(error).__name__,'message':str(error)[:12000]}
    (folder/'error.log').write_text(traceback.format_exc())
finally:
    (folder/'report.json').write_text(json.dumps(report,indent=2));dev.destroy()
print(json.dumps({'path':str(folder/'report.json'),'pass':report['pass'],'frames':len(report['frames']),
    'error':report.get('error'),'imageCount':sum('image' in f for f in report['frames'])}))
if not report['pass']: sys.exit(1)
