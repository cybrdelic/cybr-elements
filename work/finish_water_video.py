from pathlib import Path
from PIL import Image,ImageDraw
import subprocess,json
root=Path(__file__).resolve().parent
frames=root/'water-sans-frames'
expected=[frames/f'{i:04}.png' for i in range(450)]
missing=[p.name for p in expected if not p.exists()]
assert not missing,missing[:10]
assert all(p.stat().st_size>10000 for p in expected)
for i in [0,60,180,240,330,345,375,449]:
    with Image.open(expected[i]) as im: assert im.size==(1920,1080);im.verify()
v=root.parent/'outputs'/'cybrdelic-sans-water.mp4'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate','30','-i',str(frames/'%04d.png'),'-c:v','libx264','-preset','slow','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(v)],check=True)
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(v)]))
s=meta['streams'][0];assert(s['width'],s['height'],s['nb_read_frames'])==(1920,1080,'450')
subprocess.run(['ffmpeg','-v','error','-i',str(v),'-f','null','-'],check=True,capture_output=True)
for name,indices in [('water-sequence-review.jpg',[30,60,120,180,240,315,345,375]),('water-release-review.jpg',[330,336,342,348,354,360,366,390])]:
    sheet=Image.new('RGB',(1536,472),(12,15,18));d=ImageDraw.Draw(sheet)
    for k,i in enumerate(indices):
        im=Image.open(expected[i]).convert('RGB');im.thumbnail((384,216));x=k%4*384;y=k//4*236;sheet.paste(im,(x,y));d.text((x+8,y+220),f'{i/30:.1f}s',fill='white')
    sheet.save(root/name,quality=93)
report={'video':str(v),'metadata':s,'allFramesDecoded':True,'source':'sans_motion.py','waterModel':'Reduced suspended liquid-jet dynamics, axial tension, viscous momentum exchange, cross-sectional volume conservation, breakup threshold, ballistic spray and gravity release. Not original FLIP solver.','renderer':'Blender Cycles OPTIX; 24 samples, refractive IOR 1.333; 1920x1080 native frames','fullViewHoldSeconds':3.55}
(root/'water-sans-verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'video':str(v),'metadata':s,'framesValidated':450,'decode':'passed','review':['water-sequence-review.jpg','water-release-review.jpg']}))
