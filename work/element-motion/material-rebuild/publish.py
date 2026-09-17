"""Replace only individually reviewed materials in the existing gallery."""
from pathlib import Path
import json,sys,hashlib,shutil
R=Path(__file__).resolve().parent;SITE=R.parents[2]/'outputs/cybrdelic-type/elements/motion/subelements/dynamics'
reviews=json.loads((R/'reviews.json').read_text());manifest=json.loads((SITE/'studies.json').read_text())
for kind in sys.argv[1:]:
 proof=json.loads((R/'media'/f'{kind}.json').read_text());review=reviews[kind];movie=R/'media'/f'{kind}.mp4'
 assert proof['decodedFrames']==120 and proof['width']==1920 and proof['height']==1080
 digest=hashlib.sha256(movie.read_bytes()).hexdigest();assert digest==proof['sha256']==review['sha256'] and review['decision']=='keep' and review['observations']
 row=next(x for x in manifest if x['id']==kind);stem=kind+'-quality-'+digest[:10]
 for ext in ['mp4','jpg']:shutil.copyfile(R/'media'/f'{kind}.{ext}',SITE/f'{stem}.{ext}')
 if row['video']!=stem+'.mp4':
  row.setdefault('versions',[]).append({'video':row['video'],'poster':row['poster'],'note':row.get('note','')});row['previous']=row['video']
 row.update(video=stem+'.mp4',poster=stem+'.jpg',note=review['note'],rebuild='material-quality')
(SITE/'studies.json').write_text(json.dumps(manifest,indent=2))
print('Published reviewed replacements:',', '.join(sys.argv[1:]))
