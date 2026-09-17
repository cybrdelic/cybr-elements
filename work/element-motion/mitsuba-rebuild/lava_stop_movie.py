"""Stop only this workspace's active lava movie render batch and its queue."""
from pathlib import Path
import psutil,json
R=Path(__file__).resolve().parent
targets={};queues={}
for p in psutil.process_iter(['pid','name','cmdline']):
    try:
        args=p.info['cmdline'] or []
        if len(args)<2:continue
        script=Path(args[1]).resolve()
        if script==R/'lava_movie_job.py' or (script==R/'bounded.py' and 'lava_movie_job.py' in args[2:]):
            targets[p.pid]=p
            parent=p.parent()
            if parent and 'powershell' in parent.name().lower():
                command=' '.join(parent.cmdline())
                if 'foreach' in command and 'lava_movie_job.py' in command and 'work/element-motion/mitsuba-rebuild' in command:queues[parent.pid]=parent
    except (psutil.Error,OSError):pass
stopped=[]
for p in list(queues.values())+list(targets.values()):
    try:p.kill();stopped.append(p.pid)
    except psutil.NoSuchProcess:pass
print(json.dumps({'stoppedOwnedRenderProcesses':stopped,'completedImagesAndSimulationCachesPreserved':True}))
