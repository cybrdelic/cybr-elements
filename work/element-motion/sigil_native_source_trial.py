"""Build an isolated source-scale trial without changing the accepted renderer."""
from pathlib import Path
import hashlib, json

R=Path(__file__).resolve().parent
s=(R/'sigil_native_word_fire_full.py').read_text(encoding='utf-8')
s=s.replace("sigil-native/fire-{VARIANT}-full", "sigil-native/fire-{VARIANT}-source")
s=s.replace('TOTAL=330', 'TOTAL=181')
s=s.replace('(across/.23)**2', '(across/.105)**2')
s=s.replace('(along/.12)**2', '(along/.075)**2')
s=s.replace('(across/.32)**2+(y/.3)**2+(along/.55)**2', '(across/.145)**2+(y/.18)**2+(along/.25)**2')
s=s.replace('reservoir_dir[0]*2.8', 'reservoir_dir[0]*.15').replace('reservoir_dir[1]*2.8','reservoir_dir[1]*.15')
s=s.replace("angle=(temp*.8+soot*4).clamp(0,1)*(float(nozzle_turn(t))*dt*.35 if MODE=='arc' else 0.)", "angle=(temp*.8+soot*4).clamp(0,1)*wake*(float(nozzle_turn(t))*dt*.35 if MODE=='arc' else 0.)")
s=s.replace("    if frame==180:\n        print('REVIEW GATE native fire '+VARIANT,flush=True)\n        while not (ROOT/f'sigil-native/continue-fire-{VARIANT}').exists():time.sleep(.5)\n",'')
original=(R/'bending-fire.py').read_text(encoding='utf-8')
def fn(text,name,nextname): return text[text.index('def '+name+'('):text.index('def '+nextname+'(')]
assert fn(s,'radiance','capture')==fn(original,'radiance','capture')
(R/'sigil_native_word_fire_source.py').write_text(s,encoding='utf-8')
(R/'sigil-native/source-trial.json').write_text(json.dumps({
 'status':'unreviewed', 'frames':181,
 'changes':['Nozzle across radius .23 to .105, along .12 to .075',
 'Wake source footprint .32/.30/.55 to .145/.18/.25',
 'Deposited fuel line momentum 2.8 to .15 m/s',
 'Authored turning acts only near the current nozzle'],
 'preserved':['Combustion and cooling coefficients','Advection and pressure projection','Buoyancy and vorticity','Original radiance function','Exposure and optical glow'],
 'radianceSha256':hashlib.sha256(fn(s,'radiance','capture').encode()).hexdigest()
},indent=2))
print('Prepared 181-frame source-scale trial; original radiance verified unchanged.')
