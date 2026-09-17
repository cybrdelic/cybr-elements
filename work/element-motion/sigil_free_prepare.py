"""Material-first sigil test: original nozzle, free wake, subdued gas persistence."""
from pathlib import Path
import ast, hashlib, json
R=Path(__file__).resolve().parent;B=R/'sigil-native'
motion=(R/'sigil_word_motion.py').read_text(encoding='utf-8').replace('*5.05','*4.2').replace('WRITE=5.05','WRITE=4.2')
(R/'sigil_free_motion.py').write_text(motion,encoding='utf-8')
s=(R/'sigil_native_word_fire_full.py').read_text(encoding='utf-8')
s=s.replace('from sigil_word_motion import','from sigil_free_motion import')
s=s.replace('sigil-native/fire-{VARIANT}-full','sigil-native/fire-{VARIANT}-free')
s=s.replace('DURATION=4.0','DURATION=8.5').replace('TOTAL=330','TOTAL=255')
s=s.replace('reservoir_dir=torch.zeros((2,*shape),device=device)\n','')
s=s.replace('    newly=line>reservoir\n    reservoir_dir[0]=torch.where(newly,float(dx),reservoir_dir[0]);reservoir_dir[1]=torch.where(newly,float(dz),reservoir_dir[1])\n','')
s=s.replace('(reservoir*(6.0*dt))','(reservoir*(2.0*dt))').replace('if t>=8.2:reservoir','if t>=6.3:reservoir')
s=s.replace('    v[0].lerp_(reservoir_dir[0]*2.8,(gas_inject*2).clamp(0,1));v[2].lerp_(reservoir_dir[1]*2.8,(gas_inject*2).clamp(0,1))\n','')
s=s.replace("angle=(temp*.8+soot*4).clamp(0,1)*(float(nozzle_turn(t))*dt*.35 if MODE=='arc' else 0.)", "angle=(temp*.8+soot*4).clamp(0,1)*wake*(float(nozzle_turn(t))*dt*.35 if MODE=='arc' else 0.)")
s=s.replace("    if frame==180:\n        print('REVIEW GATE native fire '+VARIANT,flush=True)\n        while not (ROOT/f'sigil-native/continue-fire-{VARIANT}').exists():time.sleep(.5)\n",'')
s=s.replace('A moving nozzle deposits a narrow gas source and tangential source momentum, supplied until 8.2s then drained.', 'Original moving nozzle deposits a subdued gas supply until 6.3s, then drains. No persistent tangent-velocity target. Only the local active jet receives authored turning.')
original=(R/'bending-fire.py').read_text(encoding='utf-8')
def function(source,name):
 n=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name)
 return ast.get_source_segment(source,n)
assert function(s,'radiance')==function(original,'radiance')
assert '(across/.23)**2' in s and '(along/.12)**2' in s
assert 'reservoir_dir' not in s
compile(s,'sigil_free_fire.py','exec');compile(motion,'sigil_free_motion.py','exec')
(R/'sigil_free_fire.py').write_text(s,encoding='utf-8')
(B/'material-first-contract.json').write_text(json.dumps({
 'priority':['Material quality and convincing free motion','Original sigil gesture and brand character','Momentary recognition'],
 'legibility':'Secondary. Closed counters, broken strokes and temporary obscuration alone are not rejection reasons.',
 'blackBackdrop':True,'variants':['01','02'],'elements':['earth','fire','water','air','lightning'],
 'fireTrial':{'duration':8.5,'writeEnd':4.35,'gasSupplyEnd':6.3,'sourceWidth':'Original .23 across / .12 along','persistenceRate':2.0,'radianceSha256':hashlib.sha256(function(s,'radiance').encode()).hexdigest()},
 'prohibited':['Glyph clipping','Invisible letter-shaped water walls','Carved flat stone letters','Filled lightning font','Readability-driven velocity pinning','Image fades'],
 'review':['Original material detail survives at the delivered scale','Motion remains volumetric and unconstrained away from the active source','No boundary crops or detached graphic overlays','Release uses the material model'],
 'trialBudget':1,
 'status':'Fire test only; other element videos remain unfinished'
},indent=2),encoding='utf-8')
print('Prepared material-first fire trial; original radiance and full nozzle scale verified. 255 frames.')
