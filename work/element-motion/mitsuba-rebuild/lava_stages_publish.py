"""Publish only complete, reviewed stage stills and a complete CPU movie."""
from pathlib import Path
import json,shutil,hashlib,zipfile,subprocess,os,sys
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
from PIL import Image,ImageDraw,ImageFont
import numpy as np
R=Path(__file__).resolve().parent;F=R/'lava-focus';P=R.parents[2]/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/lava'
PREPARE='--prepare-only' in sys.argv
if PREPARE:P=F/'stages/review'
STAGES=['magma','lava','cooling','basalt','obsidian']
def checksum(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    rows=[];P.mkdir(exist_ok=True)
    for stage in STAGES:
        spp=64 if stage=='obsidian' else 8
        source=F/f'renders/stage-{stage}-hero-0000-960-{spp}spp.png';receipt=source.with_suffix('.json')
        assert source.exists() and receipt.exists(),source
        im=Image.open(source);im.load();assert im.size==(960,540)
        pixels=np.array(im);assert np.max(pixels[:16,:16])==0 and np.max(pixels[-16:,-16:])==0
        record=json.loads(receipt.read_text());assert record['imageSha256']==checksum(source)
        target=P/f'stage-{stage}.png';shutil.copy2(source,target)
        rows.append({'stage':stage,'image':target.name,'size':im.size,'sha256':checksum(target),'render':record})
    frames=F/'stages/movie';files=sorted(frames.glob('[0-9][0-9][0-9].png'));assert len(files)==32 and [p.stem for p in files]==[f'{i:03}' for i in range(32)]
    for p in files:
        im=Image.open(p);im.load();assert im.size==(480,270)
    video=P/'lava-flow-plume.mp4'
    command=['ffmpeg','-y','-v','error','-framerate','8','-i',str(frames/'%03d.png'),'-c:v','libx264','-threads','2','-preset','slow','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(video)]
    subprocess.run(command,check=True,capture_output=True)
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,nb_read_frames,r_frame_rate:format=duration','-of','json',str(video)],check=True,capture_output=True,text=True).stdout)
    s=probe['streams'][0];assert (s['width'],s['height'],int(s['nb_read_frames']))==(480,270,32) and abs(float(probe['format']['duration'])-4)<.02
    shutil.copy2(files[18],P/'motion-poster.png')
    sheet=Image.new('RGB',(1440,594),'black');draw=ImageDraw.Draw(sheet)
    for k,i in enumerate([0,6,12,18,25,31]):
        x=(k%3)*480;y=(k//3)*297;sheet.paste(Image.open(files[i]),(x,y));draw.text((x+12,y+275),f'{i:02d} / {12*i/31:.1f} simulated seconds',fill='#c8b8a8')
    sheet.save(F/'stages/motion-contact.png')
    contact=Image.new('RGB',(1440,594),'black');draw=ImageDraw.Draw(contact)
    for i,stage in enumerate(STAGES):
        im=Image.open(P/f'stage-{stage}.png');im.thumbnail((480,270));x=i%3*480;y=i//3*297;contact.paste(im,(x,y));draw.text((x+12,y+274),f'{i+1:02d} / {stage.upper()}'+(' — separate glass branch' if stage=='obsidian' else ''),fill='#c8b8a8')
    contact.save(P/'stage-contact.png')
    if PREPARE:
        print(json.dumps({'stageContact':str(P/'stage-contact.png'),'motionContact':str(F/'stages/motion-contact.png'),'video':str(video),'ffprobe':probe}));return
    with zipfile.ZipFile(P/'lava-stage-images.zip','w',zipfile.ZIP_DEFLATED) as z:
        for stage in STAGES:z.write(P/f'stage-{stage}.png',f'cybrdelic-{stage}.png')
    old=P/'basalt-depth.html'
    if not old.exists():shutil.copy2(P/'index.html',old)
    shutil.copy2(R/'lava_stages_page.html',P/'index.html')
    sim=json.loads((F/'stages/motion/simulation.json').read_text())
    report={'stills':rows,'movie':{'file':video.name,'sha256':checksum(video),'ffprobe':probe,'nativeFrames':32,'playbackSpeed':'3x simulated time; 8 rendered frames per second','render':'CPU Mitsuba surfaces plus deterministic CPU single scattering of simulated condensate'},'simulation':sim,'review':'Stills and representative motion frames visually inspected; reduced study with limitations retained below','limits':['Material states are authored views, not a complete simulated crystallization sequence','Obsidian is a separate composition branch','Crust pieces follow the flow one-way without fracture/contact forces','The motion is a small CPU preview, not a production-resolution cinematic render','Plume uses approximate condensation and single scattering']}
    (P/'stages-review.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'page':str(P/'index.html'),'stages':len(rows),'movie':probe,'contact':str(P/'stage-contact.png'),'motionContact':str(F/'stages/motion-contact.png')}))
if __name__=='__main__':main()
