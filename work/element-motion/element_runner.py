"""Shared simulation clock, checkpoint lineage and movie I/O for ELEMENTS scenes.

Domain source/reaction and optics stay in their owners; no simulation lives in
entry scripts. PNGs are actual per-step renders, not synthesized temporal frames.
"""
import argparse,hashlib,importlib,json,os,shutil,subprocess,tempfile,time
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import torch
from PIL import Image
from element_scenes import SCENES
from element_session import ElementSession
from element_receipts import state_digest

ROOT=Path(__file__).resolve().parent
CONTRACT_FIELDS=('size','fps','substeps','padded_domain','gesture_version','control','control_strength','wind')

def parser(name):
    p=argparse.ArgumentParser(description=f'{name}: shared ELEMENTS runtime')
    p.add_argument('--name',default=name);p.add_argument('--size',type=int,nargs=3,default=[896,56,504] if SCENES[name].source_asset else [128,80,160])
    p.add_argument('--seconds',type=float,default=None);p.add_argument('--fps',type=int,default=24)
    p.add_argument('--substeps',type=int,default=3);p.add_argument('--wind',type=float,default=0.)
    p.add_argument('--control',choices=['none','directed','orbit','choreographed'],default='none')
    p.add_argument('--gesture-version',choices=['19','20','20b','21','21b','22','22b','23'],default='19')
    p.add_argument('--control-strength',type=float,default=1.);p.add_argument('--padded-domain',action='store_true')
    p.add_argument('--check-inputs',action='store_true',help='Report genuine input/backend availability without allocating simulation state')
    p.add_argument('--pilot',action='store_true');p.add_argument('--device',choices=['auto','cpu','cuda'],default='auto')
    p.add_argument('--output',type=Path);p.add_argument('--resume',nargs='?',const='latest')
    p.add_argument('--checkpoint-every',type=float,default=2.);p.add_argument('--threads',type=int,default=2)
    # Retained historical flags never controlled the legacy movie loop; do not
    # invent new physics for them during consolidation.
    p.add_argument('--warmup',type=float,default=4.);p.add_argument('--move',default='sweep')
    p.add_argument('--orbit-period',type=float,default=5.);p.add_argument('--pulse',action='store_true')
    p.add_argument('--pulse-duration',type=float,default=2.85);p.add_argument('--save-every',type=int,default=1)
    return p

def resolve_device(requested):
    """Select once before allocation; never retry a failed CUDA run on CPU."""
    if requested == 'auto':return 'cuda' if torch.cuda.is_available() else 'cpu'
    if requested == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA explicitly requested but unavailable; no automatic CPU retry')
    if requested not in ('cpu','cuda'):raise ValueError('Unknown device selection')
    return requested

def contract(session):
    if hasattr(session,"frozen_contract"):return session.frozen_contract
    if not session.motion_identity:raise ValueError("Injected motion requires an explicit identity before checkpointing")
    values={k:getattr(session.a,k) for k in CONTRACT_FIELDS};values['size']=list(values['size'])
    files=['element_flow.py','fire_dynamics.py','air_dynamics.py','dust_dynamics.py','element_choreography.py','element_optics.py','element_session.py','element_scenes.py','element_receipts.py','element_runner.py',(session.spec.motion+'.py') if session.spec.motion else session.spec.source_asset]
    if session.spec.source_asset:files.append(session.spec.source_asset)
    files+=dict(shared_motion=['shared-trail.json'],sigil_native_motion=['sigil-native/c-stroke.npz']).get(session.spec.motion,[])
    if session.a.gesture_version.startswith('21'):files+=['bending_fire_choreography_v'+session.a.gesture_version+'.py']
    if session.a.gesture_version=='22b':files+=['bending_fire_moves_v22b.py']
    hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files if (ROOT/name).exists()}
    return dict(schema=1,scene=session.spec.name,parameters=values,source_sha256=hashes,motion_identity=session.motion_identity,torch_version=str(torch.__version__),device=str(session.device))

def save_checkpoint(session,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise FileExistsError(f'Checkpoint history already exists: {path}')
    data=dict(contract=contract(session),next_frame=session.next_frame,state=session.state.detach().cpu(),
        reservoir=None if session.reservoir is None else session.reservoir.detach().cpu(),
        control_cache=[(k,v.detach().cpu()) for k,v in session.control_cache.items()],rng=torch.get_rng_state())
    fd,tmp=tempfile.mkstemp(prefix='.checkpoint-',dir=path.parent);os.close(fd)
    try:
        with open(tmp,'wb') as handle:torch.save(data,handle)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return path

def load_checkpoint(session,path):
    data=torch.load(path,map_location='cpu',weights_only=True)
    if data.get('contract')!=contract(session):raise ValueError('Checkpoint scene/configuration/source mismatch')
    state=data['state'];frame=data['next_frame'];reservoir=data['reservoir']
    if state.shape!=session.state.shape or state.dtype!=session.state.dtype or not torch.isfinite(state).all():raise ValueError('Invalid checkpoint state')
    if type(frame) is not int or frame<0:raise ValueError('Invalid checkpoint sample index')
    if (reservoir is None)!=(session.reservoir is None):raise ValueError('Checkpoint reservoir mismatch')
    if reservoir is not None and (reservoir.shape!=session.reservoir.shape or reservoir.dtype!=session.reservoir.dtype or not torch.isfinite(reservoir).all()):raise ValueError('Invalid checkpoint reservoir')
    # Validate every field before mutating the active session.
    cache=data['control_cache']
    if len(cache)>3 or any(type(k)is not int or not torch.isfinite(v).all() for k,v in cache):raise ValueError('Invalid control cache')
    session.state=state.to(session.device);session.next_frame=frame
    session.reservoir=None if reservoir is None else reservoir.to(session.device)
    session.control_cache.clear();session.control_cache.update((k,v.to(session.device)) for k,v in cache)
    torch.set_rng_state(data['rng'])
    return frame

def encode_frames(directory,video,count,fps,crf=17):
    if count<1 or fps<=0:raise ValueError('Positive frame count and cadence required')
    # Input cadence is the sample cadence. ffmpeg never invents intermediate
    # frames; frame count, stream duration and actual PNG count must agree.
    command=['ffmpeg','-hide_banner','-loglevel','error','-n','-framerate',str(fps),'-start_number','0',
        '-i',str(Path(directory)/'%06d.png'),'-frames:v',str(count),'-an','-c:v','libx264','-threads','2',
        '-preset','fast','-crf',str(crf),'-pix_fmt','yuv420p','-movflags','+faststart',str(video)]
    subprocess.run(command,check=True)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
        '-show_entries','stream=nb_frames,width,height,duration,avg_frame_rate','-of','json',str(video)]))['streams'][0]
    if int(probe['nb_frames'])!=count or abs(float(probe['duration'])-count/fps)>1e-5:raise RuntimeError('Encoded movie clock mismatch')
    return probe

def main(name,argv=None):
    args=parser(name).parse_args(argv);spec=SCENES[name]
    from element_availability import recipe_availability
    availability=recipe_availability(name,args.gesture_version,args.control)
    if args.check_inputs:
        print(json.dumps(availability,indent=2));return availability
    if not availability['inputs_ready']:
        raise FileNotFoundError('Recipe inputs unavailable: '+json.dumps(dict(missing=availability['missing'],data_errors=availability['data_errors'])))
    for warning in availability['warnings']:print('Warning: '+warning,flush=True)
    if args.fps<=0:raise ValueError('Positive cadence required')
    if args.seconds is None:args.seconds=spec.default_native_frames/args.fps if spec.default_native_frames else spec.default_seconds
    if not np.isfinite([args.seconds,args.wind,args.control_strength,args.checkpoint_every]).all() or args.seconds<=0 or args.checkpoint_every<=0 or args.threads<1:raise ValueError('Invalid duration or runtime budget')
    args.device=resolve_device(args.device)
    torch.set_num_threads(args.threads);torch.set_grad_enabled(False)
    session=ElementSession(spec,args,args.device)
    session.frozen_contract=contract(session)
    if session.TOTAL<1:raise ValueError('Duration must include at least one native sample')
    out=args.output or spec.frames;out.mkdir(parents=True,exist_ok=True);session.out=out
    if shutil.disk_usage(out).free<1024**3:raise RuntimeError('Original 1GiB streaming render reserve required')
    frames=out/'frames';frames.mkdir(exist_ok=True)
    video=(out/(name+'.mp4')) if args.output else spec.video
    if args.pilot:video=video.with_name(video.stem+'-pilot.mp4')
    video.parent.mkdir(parents=True,exist_ok=True)
    if (out/'complete.json').exists():raise FileExistsError('Completed output preserved; choose another --output')
    if video.exists() and not args.resume:raise FileExistsError('Existing movie preserved; use --resume or choose another --output')
    if args.resume:
        available=sorted(out.glob('checkpoint-*.pt'))
        if args.resume=='latest' and not available:raise ValueError('No checkpoint history available to resume')
        path=available[-1] if args.resume=='latest' else Path(args.resume)
        load_checkpoint(session,path)
        if any(not (frames/f'{i:06d}.png').is_file() for i in range(session.next_frame)):raise ValueError('Resume is missing rendered sample history')
    elif any(frames.iterdir()):raise FileExistsError('Existing frame history requires --resume or a new output')
    if video.exists():video.rename(video.with_name(video.name+f'.incomplete-{time.time_ns()}'))
    cadence=max(1,round(args.checkpoint_every*args.fps));started=time.monotonic()
    with (out/'samples.jsonl').open('a') as log:
        while session.next_frame<session.TOTAL:
            if spec.review_gate is not None and session.next_frame==spec.review_gate+1 and not spec.continue_path.exists():
                checkpoint=out/f'checkpoint-{session.next_frame:06d}.pt'
                if not checkpoint.exists():save_checkpoint(session,checkpoint)
                (out/'review-required.json').write_text(json.dumps(dict(frame=spec.review_gate,continue_path=str(spec.continue_path),checkpoint=str(checkpoint))))
                raise SystemExit('Review gate preserved: inspect frame135 and authorize continuation; no complete receipt written')
            frame,div=session.advance_frame();pixels=session.pixels(frame);path=frames/f'{frame:06d}.png'
            if path.exists():
                if not np.array_equal(np.asarray(Image.open(path)),pixels):raise RuntimeError('Uncommitted frame differs from resumed state')
            else:Image.fromarray(pixels).save(path)
            row=dict(frame=frame,time=(frame+1)/args.fps,state_sha256=state_digest(session.state),pixel_sha256=hashlib.sha256(pixels.tobytes()).hexdigest(),divergence=div)
            log.write(json.dumps(row)+'\n');log.flush()
            if session.next_frame%cadence==0 or session.next_frame==session.TOTAL:save_checkpoint(session,out/f'checkpoint-{session.next_frame:06d}.pt')
            if frame%args.fps==0:print(json.dumps(row),flush=True)
    probe=encode_frames(frames,video,session.TOTAL,args.fps,spec.crf)
    receipt=dict(contract=contract(session),native_frames=session.TOTAL,simulation_seconds=session.TOTAL/args.fps,encoded_seconds=float(probe['duration']),stream=probe,elapsed_seconds=time.monotonic()-started,video_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),synthetic_frames=False)
    (out/'complete.json').write_text(json.dumps(receipt,indent=2));print(str(video),flush=True)
    return receipt
