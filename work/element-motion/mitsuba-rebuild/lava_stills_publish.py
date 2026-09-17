"""Expose the completed stills while the independently playable clip renders."""
from pathlib import Path
import json,shutil,zipfile,re,hashlib
from PIL import Image,ImageDraw
import numpy as np
R=Path(__file__).resolve().parent;F=R/'lava-focus';P=R.parents[2]/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/lava';rows=[]
for stage in ['magma','lava','cooling','basalt','obsidian']:
    spp=64 if stage=='obsidian' else 8;source=F/f'renders/stage-{stage}-hero-0000-960-{spp}spp.png';im=Image.open(source);im.load();assert im.size==(960,540)
    record=json.loads(source.with_suffix('.json').read_text());assert record['imageSha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    assert np.array(im)[:16,:16].max()==0
    shutil.copy2(source,P/f'stage-{stage}.png');rows.append({'stage':stage,'image':f'stage-{stage}.png','render':record})
sheet=Image.new('RGB',(1440,594),'black');draw=ImageDraw.Draw(sheet)
for i,row in enumerate(rows):
    im=Image.open(P/row['image']);im.thumbnail((480,270));x=i%3*480;y=i//3*297;sheet.paste(im,(x,y));draw.text((x+12,y+274),f'{i+1:02d} / {row["stage"].upper()}',fill='#c8b8a8')
sheet.save(P/'stage-contact.png')
with zipfile.ZipFile(P/'lava-stage-images.zip','w',zipfile.ZIP_DEFLATED) as z:
    for row in rows:z.write(P/row['image'],'cybrdelic-'+row['stage']+'.png')
old=P/'basalt-depth.html'
if not old.exists():shutil.copy2(P/'index.html',old)
html=(R/'lava_stages_page.html').read_text(encoding='utf-8');html=re.sub(r'<section class="motion".*?</section>','',html,flags=re.S);html=html.replace('<a href="#motion">Flow & plume</a>','')
temp=P/'index.stage-ready.tmp';temp.write_text(html,encoding='utf-8');temp.replace(P/'index.html')
(P/'stages-review.json').write_text(json.dumps({'stills':rows,'motionStatus':'Simulation complete; CPU movie rendering in progress','limits':'Authored matched material states; motion is a reduced numerical study; obsidian is a separate composition branch'},indent=2))
print(json.dumps({'url':'http://127.0.0.1:8767/elements/motion/subelements/dynamics/lava/?v=stages','stills':5,'contact':str(P/'stage-contact.png')}))
