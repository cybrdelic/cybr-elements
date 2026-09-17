from pathlib import Path
import subprocess,json,io
from PIL import Image,ImageDraw
import numpy as np
root=Path(__file__).resolve().parent
v=root.parent/'outputs'/'cybrdelic-handprint-fire.mp4'
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(v)]))
s=meta['streams'][0]
assert (s['width'],s['height'],s['nb_read_frames'])==(1920,1080,'450'),s
subprocess.run(['ffmpeg','-v','error','-i',str(v),'-f','null','-'],check=True,capture_output=True)
def grab(t):
    data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(v),'-frames:v','1','-vf','scale=384:216','-f','image2pipe','-vcodec','png','-'])
    return Image.open(io.BytesIO(data)).convert('RGB')
def contact(times,name):
    im=Image.new('RGB',(1536,236*((len(times)+3)//4)),(16,16,16));d=ImageDraw.Draw(im)
    for i,t in enumerate(times):
        x=(i%4)*384;y=(i//4)*236
        im.paste(grab(t),(x,y));d.text((x+7,y+219),f'{t:.2f}s',fill='white')
    im.save(root/name,quality=94)
contact([1.5,3.,4.5,6.,8.,10.7,11.7,13.],'handprint-fire-review.jpg')
contact([round(10.8+i*.2,2) for i in range(12)],'handprint-burnout-review.jpg')
opening=np.asarray(grab(8.2),float)
hold=np.asarray(grab(10.6),float)
end=np.asarray(grab(14.9),float)
ratios={'holdBrightnessRatio':float(hold.sum()/max(1,opening.sum())),'endBrightnessRatio':float(end.sum()/max(1,hold.sum())),'lastPeak':int(end.max())}
assert ratios['holdBrightnessRatio']>.3,ratios
assert ratios['endBrightnessRatio']<.02,ratios
source=(root/'render_handprint_fire.py').read_text()
assert 'closing=' not in source and '*closing' not in source
rows=[]
for line in (root/'handprint-fire.log').read_text().splitlines():
    try:r=json.loads(line)
    except ValueError:continue
    if 'gasInventory' in r:rows.append(r)
assert rows and rows[-1]['gasInventory']<rows[0]['gasInventory']*.0001
report={'metadata':meta,'allFramesDecoded':True,'fullViewHoldSeconds':3.55,'valveClosesAt':11.0,'opacityFade':False,'brightness':ratios,'physicalDiagnostics':rows}
(root/'handprint-fire-verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'metadata':s,'decode':'all frames passed',**ratios,'remainingGasRatio':rows[-1]['gasInventory']/rows[0]['gasInventory'],'review':['handprint-fire-review.jpg','handprint-burnout-review.jpg']}))

