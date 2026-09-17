import bpy,sys,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=bpy.context.scene
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX';prefs.get_devices()
for dev in prefs.devices:dev.use=dev.type=='OPTIX'
s.cycles.device='GPU'
frames=[int(sys.argv[sys.argv.index('--frame')+1])] if '--frame' in sys.argv else [24,60,96,132] if '--pilot' in sys.argv else range(1,145)
out=ROOT/'frames';out.mkdir(exist_ok=True);start=time.monotonic()
for frame in frames:
 if '--pilot' not in sys.argv and '--frame' not in sys.argv:
  ready=ROOT/'cache-v2/mesh'/f'fluid_mesh_{frame+1:04}.bobj.gz' if frame<144 else ROOT/'bake-report.json'
  while not ready.exists():time.sleep(1)
 s.frame_set(frame);s.render.filepath=str(out/f'{frame:04}.png');bpy.ops.render.render(write_still=True)
 print('STUDY_FRAME',frame,round(time.monotonic()-start,2),flush=True)
