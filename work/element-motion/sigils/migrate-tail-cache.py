"""One-time migration of unchanged metal frames before the tail-writer fix."""
from pathlib import Path
from PIL import Image
import hashlib,json,difflib
R=Path(__file__).resolve().parent
Image.new('RGB',(1920,1080)).save(R/'black-frame.jpg',quality=97)
old=(R/'render-before-tail-fix.py').read_text();new=(R/'render.py').read_text()
diff=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True)))
assert new==old.replace('pos[:,0]+=1.8*release;','pos[:,0]+=1.8*release+.6*release**2;').replace("from PIL import Image\n        Image.new('RGB',(1920,1080)).save(out/f'{f:04}.jpg',quality=97)","shutil.copyfile(R/'black-frame.jpg',out/f'{f:04}.jpg')")
rows=[]
for v in ['01','02']:
    key='metal-'+v;file=R/'progress'/f'{key}.json';p=json.loads(file.read_text())
    deps=['render.py','materials.py','motion.py','botanical.py','channels.py',f'source-{v}.npz']
    suffix=(key.replace('-','')+'FalseFalse').encode()
    before=hashlib.sha256(b''.join((R/('render-before-tail-fix.py' if n=='render.py' else n)).read_bytes() for n in deps)+suffix).hexdigest()
    after=hashlib.sha256(b''.join((R/n).read_bytes() for n in deps)+suffix).hexdigest()
    assert p['configuration']==before and set(p['frames'])==set(range(405))
    p['configuration']=after;file.write_text(json.dumps(p),encoding='utf-8')
    rows.append({'key':key,'before':before,'after':after,'retainedFrames':405,'reason':'Only flight motion and black tail writer after frame 405 changed; rendered metal frames 0 through 404 are unchanged.'})
(R/'tail-cache-migration.json').write_text(json.dumps({'changes':diff,'migrations':rows},indent=2),encoding='utf-8')
print('Preserved 810 unchanged metal frames; black tail file prepared')
