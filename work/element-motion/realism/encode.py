from pathlib import Path
import subprocess,sys,json,hashlib
from PIL import Image
R=Path(__file__).resolve().parent;O=R.parents[2]/'outputs/cybrdelic-type/elements/motion/subelements'
records=[]
for K in sys.argv[1:]:
 folder=R/f'{K}-frames';ext='png' if K in ['metal','plants','healing'] else 'jpg';files=[folder/f'{f:04}.{ext}' for f in range(120)]
 assert all(p.exists() and p.stat().st_size>300 for p in files),(K,'incomplete')
 for p in files:
  with Image.open(p) as im:assert im.size==(1920,1080),(K,p.name,im.size);im.load()
 output=O/f'rebuild-{K}-v4.mp4';subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate','30','-i',str(folder/f'%04d.{ext}'),'-frames:v','120','-c:v','libx264','-threads','2','-preset','slow','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(output)],check=True)
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,nb_frames,duration','-of','json',str(output)],text=True))['streams'][0]
 assert (probe['width'],probe['height'],probe['avg_frame_rate'],probe['nb_frames'])==(1920,1080,'30/1','120')
 posterFrame=53 if K in ['lightning','combustion'] else 42;Image.open(files[posterFrame]).save(O/f'rebuild-{K}-v4.jpg',quality=94)
 sourceDigest=hashlib.sha256(''.join(hashlib.sha256(p.read_bytes()).hexdigest() for p in files).encode()).hexdigest()
 row={'id':K,'file':output.name,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'sourceFrameDigest':sourceDigest,'bytes':output.stat().st_size,**probe};records.append(row);(R/f'{K}-integrity.json').write_text(json.dumps(row,indent=2),encoding='utf-8');print(K,output.stat().st_size,'bytes, 120 frames verified',flush=True)
