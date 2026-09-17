from pathlib import Path
import subprocess,json,time,hashlib,shutil,os
from PIL import Image,ImageDraw
ROOT=Path(__file__).parent;OUT=ROOT.parent/'outputs/cybrdelic-elements';OUT.mkdir(exist_ok=True)
WEB=ROOT.parent/'outputs/cybrdelic-type/elements';WEB.mkdir(exist_ok=True)
BLENDER='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
try:
 import psutil
 psutil.Process().nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
except Exception:pass
state={'started':time.time(),'status':'rendering','current':None,'completed':[]}
previous=OUT/'status.json'
if previous.exists():
 old=json.loads(previous.read_text())
 state['completed']=[c for c in old.get('completed',[]) if (OUT/c['video']).exists() and (OUT/f"{c['element']}-{c['variant']}-verification.json").exists()]
def publish():
 text=json.dumps(state,indent=2);(OUT/'status.json').write_text(text);(WEB/'status.json').write_text(text)
def verify(element,variant,folder,video):
 files=[folder/f'{i:04}.png' for i in range(450)];assert all(p.exists() for p in files),'Missing frames'
 info=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,nb_read_frames,duration,r_frame_rate','-of','json',str(video)]))['streams'][0]
 assert info['nb_read_frames']=='450' and info['r_frame_rate']=='30/1',info
 assert info['width']==(3840 if element=='water' else 2560),info
 sheet=Image.new('RGB',(1536,472),(12,12,12));draw=ImageDraw.Draw(sheet)
 for j,f in enumerate([45,90,150,210,240,315,360,449]):
  with Image.open(files[f]) as im:thumb=im.convert('RGB').resize((384,216),Image.Resampling.LANCZOS)
  x=j%4*384;y=j//4*236;sheet.paste(thumb,(x,y));draw.text((x+8,y+219),f'{f/30:.1f}s',fill='white')
 sheet.save(OUT/f'{element}-{variant}-review.jpg',quality=94)
 with Image.open(files[240]) as im:
  im.thumbnail((1600,1600));im.save(OUT/f'{element}-{variant}-poster.jpg',quality=94)
 report={'metadata':info,'frameSequenceComplete':True,'render':json.loads((ROOT/f'{element}-brand-{variant}-report.json').read_text())}
 (OUT/f'{element}-{variant}-verification.json').write_text(json.dumps(report,indent=2))
 return info
try:
 for element,variant in [('water','01'),('air','01'),('earth','01'),('water','02'),('air','02'),('earth','02')]:
  if any(c['element']==element and c['variant']==variant for c in state['completed']):continue
  state['current']={'element':element,'variant':variant,'frame':0};publish()
  log=ROOT/f'{element}-brand-{variant}-production.log'
  with log.open('w',encoding='utf8') as out:
   p=subprocess.Popen([BLENDER,'-b','--factory-startup','-t','4','--python',str(ROOT/'render_element_mark.py'),'--',element,variant],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
   try:psutil.Process(p.pid).nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
   except Exception:pass
   for line in p.stdout:
    out.write(line)
    if 'ELEMENT_PROGRESS ' in line:
     row=json.loads(line.split('ELEMENT_PROGRESS ',1)[1]);state['current']=row;publish()
     if row['frame']%30==0:print(json.dumps(row),flush=True)
   if p.wait()!=0:raise RuntimeError(f'{element} {variant} render failed; see {log}')
  folder=ROOT/f'{element}-brand-{variant}-frames';video=OUT/f'cybrdelic-{element}-{variant}.mp4'
  subprocess.run(['ffmpeg','-v','error','-y','-framerate','30','-i',str(folder/'%04d.png'),'-frames:v','450','-an','-c:v','libx264','-threads','4','-preset','medium','-crf','15','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],check=True,stdout=subprocess.DEVNULL,stderr=open(ROOT/f'{element}-{variant}-encode.log','w'),creationflags=subprocess.CREATE_NO_WINDOW)
  info=verify(element,variant,folder,video)
  for path in [video,OUT/f'{element}-{variant}-poster.jpg']:shutil.copy2(path,WEB/path.name)
  state['completed'].append({'element':element,'variant':variant,'video':video.name,'poster':f'{element}-{variant}-poster.jpg','width':info['width'],'height':info['height']});publish()
  print('COMPLETE '+element+' '+variant,flush=True)
 state['status']='complete';state['current']=None;publish()
except Exception as e:
 state['status']='error';state['error']=str(e);publish();raise
