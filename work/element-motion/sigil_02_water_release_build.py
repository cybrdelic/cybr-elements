"""Use an unambiguous frame boundary and retain primary caches for validation."""
from pathlib import Path
import shutil
R=Path(__file__).resolve().parent;O=R/'sigil-02-repair'
(O/'water-release-frames').mkdir(exist_ok=True)
for f in range(136):shutil.copy2(O/f'water-frames/{f:04}.jpg',O/f'water-release-frames/{f:04}.jpg')
for suffix in ['.mjs','_mesh.py','_render.py']:
 src=R/f'sigil_02_water_outflow{suffix}';s=src.read_text()
 s=s.replace('water-outflow-','water-release-')
 if suffix=='.mjs':
  s=s.replace('this.time/timeScale>=136/30','this.time/timeScale>=137/30')
  s=s.replace("while(fs.readdirSync(out).filter(x=>x.endsWith('.gz')).length>=8)await new Promise(r=>setTimeout(r,300));",'// Primary caches are retained so any subsequent review can reuse them.')
 else:
  s=s.replace("(source/f'{f:04}.gz').unlink()",'pass # Retain primary cache for reproducible validation.')
 (R/f'sigil_02_water_release{suffix}').write_text(s)
s=(R/'sigil_02_water_outflow_run.py').read_text().replace('outflow','release')
(R/'sigil_02_water_release_run.py').write_text(s)
print('Release scripts prepared; exact formation state boundary and retained caches.')
