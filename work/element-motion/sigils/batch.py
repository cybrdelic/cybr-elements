"""Run a bounded local render queue with resumable per-frame checkpoints."""
from pathlib import Path
import subprocess,sys,time,json
import psutil
R=Path(__file__).resolve().parent
if (R/'quality-hold.json').exists():raise SystemExit('Batch stopped: material quality was rejected. Read quality-hold.json before starting new renders.')
kinds=['metal','glass','sand','ice','plants','lava','snow','crystal','energy','foam','spirit','mud','lightning','blood','lightning-redirection','healing','spirit-projection','seismic','flight']
pending=[f'{k}-{v}' for k in kinds for v in ['01','02']];active=[];done=[];failed=[];tries={};pressure_since=None;capacity=2
def stop_owned(job):
    try:
        p=psutil.Process(job['process'].pid);args=p.cmdline();assert any(x.replace('\\','/').endswith('/sigils/run.py') for x in args)
        children=p.children(recursive=True);p.terminate()
        for child in children:
            try:child.terminate()
            except psutil.NoSuchProcess:pass
    except psutil.NoSuchProcess:pass
def vram():
    try:return int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],timeout=5).decode().strip().splitlines()[0])
    except:return 0
while pending or active:
    available=psutil.virtual_memory().available/1e9;gpu=vram()
    pressured=available<.85 or gpu>7600
    pressure_since=(pressure_since or time.time()) if pressured else None
    if pressure_since and time.time()-pressure_since>15 and len(active)>1:
        job=active.pop();stop_owned(job);job['stream'].close();pending.insert(0,job['key']);capacity=1;print('MEMORY PAUSE',job['key'],flush=True);pressure_since=None
    for job in list(active):
        code=job['process'].poll()
        if code is None:continue
        active.remove(job);job['stream'].close()
        if code==0:done.append(job['key']);print('COMPLETE',job['key'],len(done),'/ 38',flush=True)
        elif tries[job['key']]<2:pending.append(job['key']);print('RETRY',job['key'],flush=True)
        else:failed.append(job['key']);print('FAILED',job['key'],flush=True)
    if capacity==1 and available>4 and gpu<4500:capacity=2
    while pending and len(active)<capacity:
        available=psutil.virtual_memory().available/1e9
        if available<(3.0 if active else 1.8) or (active and gpu>5500):break
        key=pending.pop(0);tries[key]=tries.get(key,0)+1;stream=(R/f'queue-{key}.log').open('w',encoding='utf-8');proc=subprocess.Popen([sys.executable,str(R/'run.py'),key],stdout=stream,stderr=subprocess.STDOUT)
        active.append({'key':key,'process':proc,'stream':stream,'started':time.time()});print('START',key,'pid',proc.pid,flush=True)
        # Give a renderer time to reserve its buffers before starting another.
        break
    rows=[]
    for job in active:
        file=R/'progress'/f"{job['key']}.json"
        try:count=len(json.loads(file.read_text())['frames'])
        except:count=0
        rows.append({'key':job['key'],'pid':job['process'].pid,'frames':count,'elapsed':round(time.time()-job['started'])})
    (R/'batch-state.json').write_text(json.dumps({'active':rows,'pending':pending,'done':done,'failed':failed,'freeRamGB':round(available,2),'vramMiB':gpu},indent=2),encoding='utf-8')
    if active or pending:time.sleep(10)
if failed:raise SystemExit('Incomplete renders: '+', '.join(failed))
print('All 38 surface/channel sigil films complete',flush=True)
