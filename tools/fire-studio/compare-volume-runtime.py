"""Bounded native evidence: image/field drift and submitted GPU distributions."""
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

Q=Path(__file__).resolve().parents[2]/'work/adaptive-volume-qa'
ap=argparse.ArgumentParser()
ap.add_argument('baseline');ap.add_argument('candidate')
ap.add_argument('--adapter',choices=['integrated','discrete'],default='integrated')
ap.add_argument('--baseline-output');ap.add_argument('--candidate-output')
ap.add_argument('--output',help='New comparison directory name under the QA root')
args=ap.parse_args()
def load(name,output): return json.loads((Q/name/(output or ('native-'+args.adapter))/'report.json').read_text())
baseline,candidate=load(args.baseline,args.baseline_output),load(args.candidate,args.candidate_output)
target=(Q/(args.output or ('compare-'+args.baseline+'-'+args.candidate+'-'+args.adapter))).resolve()
if not target.is_relative_to(Q.resolve()) or target==Q.resolve():ap.error('--output must stay within the QA root.')
target.mkdir(exist_ok=False)
def timings(report):
    frames=[f for f in report['frames'] if isinstance(f['index'],int) and f['index']>=8]
    result={}
    for key in ['gpuMs','completedWallMs']:
        values=[f[key] for f in frames if key in f]
        if values: result[key]={'median':float(np.median(values)),'p95':float(np.percentile(values,95)),'min':min(values),'max':max(values),'count':len(values)}
    stats=[f['stats'] for f in report['frames'] if 'stats' in f]
    if stats:
        result['cfl']={'max':max(s['measuredCFL'] for s in stats),'violations':sum(not s['withinMeasuredCFL'] for s in stats),'limit':1.5}
        result['divergence']={key:{'median':float(np.median([s[key] for s in stats])),'max':max(s[key] for s in stats)} for key in ['preDivergenceMean','postDivergenceMean']}
    result['poolModes']={str(mode):sum(f.get('poolStatus',[None])[0]==mode for f in report['frames']) for mode in [0,1]}
    return result
report={'nativeOnly':True,'adapter':args.adapter,'baseline':args.baseline,'candidate':args.candidate,
    'timingWindow':'Integer frame indices >=8; compilation, evidence readbacks and angle-only frames excluded from GPU distribution',
    'baselinePass':baseline['pass'],'candidatePass':candidate['pass'],'baselineTiming':timings(baseline),'candidateTiming':timings(candidate),'frames':[]}
matched={f['index']:f for f in baseline['frames']}
panels=[]
for cand in candidate['frames']:
    base=matched.get(cand['index']);
    if not base: continue
    frame={'index':cand['index'],'time':cand['time']}
    if 'image' in base and 'image' in cand:
        a,b=Image.open(base['image']['path']).convert('RGB'),Image.open(cand['image']['path']).convert('RGB')
        pa,pb=np.array(a).astype(np.int16),np.array(b).astype(np.int16);difference=np.abs(pa-pb)
        frame['image']={'differentPixels':int(np.count_nonzero(np.any(difference>0,axis=2))),
            'maxCodeError':int(difference.max()),'meanCodeError':float(difference.mean()),'rmsCodeError':float(np.sqrt(np.mean(difference.astype(np.float64)**2)))}
        panels.append((str(cand['index'])+'  '+format(cand['time'],'.3f')+'s',a,b))
    if base.get('chemistry',{}).get('path') and cand.get('chemistry',{}).get('path'):
        a=np.load(base['chemistry']['path'],mmap_mode='r');b=np.load(cand['chemistry']['path'],mmap_mode='r')
        maximum=np.zeros(4);total=np.zeros(4);different=np.zeros(4,np.int64);nonfinite=0
        for z in range(0,256,16):
            old=a[z:z+16].astype(np.float32);new=b[z:z+16].astype(np.float32);error=np.abs(old-new).reshape(-1,4)
            maximum=np.maximum(maximum,error.max(axis=0));total+=error.sum(axis=0,dtype=np.float64);different+=np.count_nonzero(error,axis=0);nonfinite+=np.count_nonzero(~np.isfinite(new))
        baseline_sum=np.array(base['chemistry']['sumByChannel']);candidate_sum=np.array(cand['chemistry']['sumByChannel'])
        frame['chemistry']={'maxErrorByChannel':maximum.tolist(),'meanErrorByChannel':(total/256**3).tolist(),'differentVoxelsByChannel':different.tolist(),
            'relativeL1ByChannel':(total/np.maximum(baseline_sum,1e-30)).tolist(),'relativeSumChangeByChannel':((candidate_sum-baseline_sum)/np.maximum(baseline_sum,1e-30)).tolist(),
            'nonfinite':int(nonfinite),'mode':cand['chemistry']['mode'],'poolStatus':cand['chemistry'].get('poolStatus')}
    report['frames'].append(frame)
# First/middle/last evolution and all angle/smoke views: bounded inspection,
# while all individual snapshots and metrics remain available on disk.
evolution=[p for p in panels if not p[0].startswith('view-')];views=[p for p in panels if p[0].startswith('view-')]
selection=([evolution[0],evolution[len(evolution)//2],evolution[-1]] if len(evolution)>3 else evolution)+views
if selection:
    cell_w,cell_h=640,360;row_h=384
    sheet=Image.new('RGB',(cell_w*2,row_h*len(selection)),(13,15,18));draw=ImageDraw.Draw(sheet)
    for row,(label,a,b) in enumerate(selection):
        draw.text((8,row*row_h+5),label+' | '+args.baseline+' / '+args.candidate,fill=(225,225,225))
        sheet.paste(a.resize((cell_w,cell_h)),(0,row*row_h+24));sheet.paste(b.resize((cell_w,cell_h)),(cell_w,row*row_h+24))
    if max(sheet.size)>1600: sheet.thumbnail((1600,1600))
    contact=target/'comparison.jpg';sheet.save(contact,quality=90);report['contactSheet']={'path':str(contact),'width':sheet.width,'height':sheet.height,'bytes':contact.stat().st_size}
(target/'comparison.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'path':str(target/'comparison.json'),'baselineTiming':report['baselineTiming'],'candidateTiming':report['candidateTiming'],
    'imageCount':sum('image' in f for f in report['frames']),'fieldCount':sum('chemistry' in f for f in report['frames']),
    'contactSheet':report.get('contactSheet')}))
