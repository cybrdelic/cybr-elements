from pathlib import Path
import subprocess,json,shutil,time
from PIL import Image,ImageDraw
import psutil
ROOT=Path(__file__).parent
OUT=ROOT.parent/'outputs/cybrdelic-elements'
WEB=ROOT.parent/'outputs/cybrdelic-type/elements'
BLENDER='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
psutil.Process().nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
state=json.loads((OUT/'status.json').read_text())
assert len(state['completed'])==6 and state['status']=='complete'
def publish():
 for folder in [OUT,WEB]:(folder/'status.json').write_text(json.dumps(state,indent=2))
try:
 for variant in ['01','02']:
  state['status']='polishing';state['current']={'element':'water','variant':variant,'frame':232};publish()
  reportfile=ROOT/f'water-brand-{variant}-report.json';original=json.loads(reportfile.read_text())
  with (ROOT/f'water-{variant}-exit-refinement.log').open('w') as log:
   p=subprocess.Popen([BLENDER,'-b','--factory-startup','-t','4','--python',str(ROOT/'render_element_mark.py'),'--','water',variant,'--start-frame','232','--end-frame','253'],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
   psutil.Process(p.pid).nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
   assert p.wait()==0,'Water exit refinement failed'
  partial=json.loads(reportfile.read_text());original['streamExitRefinement']={'frames':[232,252],'elapsed':partial['elapsed'],'hideAfterSeconds':8.4};reportfile.write_text(json.dumps(original,indent=2))
  folder=ROOT/f'water-brand-{variant}-frames';video=OUT/f'cybrdelic-water-{variant}-final.mp4'
  with (ROOT/f'water-{variant}-final-encode.log').open('w') as log:
   subprocess.run(['ffmpeg','-v','error','-y','-framerate','30','-i',str(folder/'%04d.png'),'-frames:v','450','-an','-c:v','libx264','-threads','4','-preset','medium','-crf','15','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],stdout=log,stderr=subprocess.STDOUT,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
  info=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,nb_read_frames,duration,r_frame_rate','-of','json',str(video)]))['streams'][0]
  assert info['nb_read_frames']=='450' and info['width']==3840 and info['height']==2160 and info['r_frame_rate']=='30/1'
  sheet=Image.new('RGB',(1536,472));draw=ImageDraw.Draw(sheet)
  for j,f in enumerate([45,90,150,210,240,315,360,449]):
   with Image.open(folder/f'{f:04}.png') as im:thumb=im.convert('RGB').resize((384,216),Image.Resampling.LANCZOS)
   x=j%4*384;y=j//4*236;sheet.paste(thumb,(x,y));draw.text((x+8,y+219),f'{f/30:.1f}s',fill='white')
  sheet.save(OUT/f'water-{variant}-review.jpg',quality=94)
  with Image.open(folder/'0270.png') as im:
   im.thumbnail((1600,1600));im.save(OUT/f'water-{variant}-poster.jpg',quality=94)
  (OUT/f'water-{variant}-verification.json').write_text(json.dumps({'metadata':info,'frameSequenceComplete':all((folder/f'{i:04}.png').exists() for i in range(450)),'render':original},indent=2))
  shutil.copy2(video,WEB/video.name);shutil.copy2(OUT/f'water-{variant}-poster.jpg',WEB/f'water-{variant}-poster.jpg')
  for c in state['completed']:
   if c['element']=='water' and c['variant']==variant:c['video']=video.name
  publish();print('REFINED water '+variant,flush=True)
 state['status']='complete';state['current']=None;publish()
except Exception as e:
 state['status']='error';state['error']=str(e);publish();raise
