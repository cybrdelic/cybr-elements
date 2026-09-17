from pathlib import Path
import json,subprocess,hashlib
R=Path(__file__).resolve().parent;O=R.parent.parent/'outputs/cybrdelic-type/elements/motion/subelements'
notes={'lava':'Hot flow breaks through a cooling basalt crust.','ice':'Clear ice with trapped air, fractures, and rough patches.','glass':'Thin panes with fractured, beveled edges.','crystal':'Intergrown mineral clusters with violet interiors.','foam':'Fine wet foam with varied bubble sizes.','mud':'Wet earth with fine grit and subdued highlights.','metal':'Brushed steel with rolled edges.','plants':'Curved leaves with translucent edges and growing vines.','blood':'Dark fluid with wet surface highlights.','healing':'Broken fibers reconnect behind a traveling restoration front.','spirit':'A tangled structure reorganizes into coherent luminous filaments.','sand':'Fine mineral grains disperse and settle.','snow':'Light powder disperses slowly.','combustion':'A focused source followed by turbulent ignition.','blue-fire':'Blue flame sheets curl and break apart.','steam':'Backlit vapor with fine rolling structure.','smoke':'Dense smoke scatters and absorbs light.','energy':'Opposing amber and blue fields exchange along the gesture.','flight':'A fine air wake disperses behind the shared gesture.','spirit-projection':'A translucent luminous wake.','heat':'Heat shimmer against a lit backdrop.','lightning':'Branching discharges with a narrow luminous core.','lightning-redirection':'Branching discharges travel back through the gesture.'}
photo={'lava','ice','glass','crystal','foam','mud','blood','metal','plants','lightning','lightning-redirection'}
core=O.parent;accepted=json.loads((core/'material-review.json').read_text(encoding='utf-8'))['acceptedMaterialVideos'];coreChecks={}
for key,asset in accepted.items():
 actual=hashlib.sha256((core/asset['file']).read_bytes()).hexdigest();assert actual==asset['sha256'],key+' accepted clip changed';coreChecks[key]=actual
(O/'accepted-core-integrity.json').write_text(json.dumps(coreChecks,indent=2),encoding='utf-8')
logNames=['optical-final-ice.log','optical-final-glass.log','rebuild-crystal-refine.log','refined-lava-full.log','photo-lightning-full.log']+[f'finish-{k}.log' for k in ['foam','mud','blood','metal','plants','sand','snow','lightning-redirection']]+['finish-healing.log','finish-spirit.log','finish-energy.log','rebuild-gas.log','rebuild-blue-fire.log','rebuild-combustion.log']
for name in logNames:
 contents=(R/'subelements'/name).read_text(encoding='utf-8',errors='replace');assert 'Traceback (most recent call last)' not in contents,name
data=json.loads((O/'studies.json').read_text(encoding='utf-8'));checks=[]
for d in data:
 ident=d['id'];file=('refined-lava' if ident=='lava' else 'field-'+ident if ident in {'healing','spirit','energy'} else 'photo-'+ident if ident in photo else 'combustion-volume' if ident=='combustion' else ident)+'.mp4';p=O/file
 result=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,r_frame_rate,duration','-of','json',str(p)],capture_output=True,text=True,check=True);v=json.loads(result.stdout)['streams'][0]
 assert v['width']==1920 and v['height']==1080 and v['nb_frames']=='120' and v['r_frame_rate']=='30/1',(ident,v)
 poster=p.with_suffix('.jpg');subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',('1.7' if ident=='combustion' else '1.4'),'-i',str(p),'-frames:v','1','-vf','scale=1280:-1',str(poster)],check=True)
 version=hashlib.sha256(p.read_bytes()).hexdigest()[:10]
 d.update(video=file+'?v='+version,poster=poster.name+'?v='+version,note=notes.get(ident,d['note']))
 if (ident in photo and ident!='crystal') or ident in {'healing','spirit','energy'}:d['previous']=ident+'.mp4'
 checks.append({'id':ident,'file':file,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),**v})
backup=O/'studies-before-final.json'
if not backup.exists():backup.write_text((O/'studies.json').read_text(encoding='utf-8'),encoding='utf-8')
for name in ['studies.json','revised.json']:(O/name).write_text(json.dumps(data,indent=2),encoding='utf-8')
(O/'video-integrity.json').write_text(json.dumps(checks,indent=2),encoding='utf-8');print('Verified and linked',len(checks),'videos')
