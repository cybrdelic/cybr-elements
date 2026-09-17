"""Retain native reactive flow/optics; replace the source with full 02 geometry."""
from pathlib import Path
import ast,hashlib,json
R=Path(__file__).resolve().parent;O=R/'sigil-02'
s=(R/'sigil_free_fire.py').read_text(encoding='utf-8')
s=s.replace('from sigil_free_motion import pose as nozzle_pose, turn_rate as nozzle_turn, WRITE, START, MODE, VARIANT',"MODE='arc'; START=.30; WRITE=3.60; VARIANT='02'")
s=s.replace("out = ROOT/f'sigil-native/fire-{VARIANT}-free'","out = ROOT/'sigil-02/fire-frames'")
s=s.replace('reservoir=torch.zeros(shape,device=device)', '''source_fields=np.load(ROOT/'sigil-02/source.npz')
if source_fields['support'].shape!=(Z,X):raise RuntimeError('Source grid mismatch')
support=torch.from_numpy(source_fields['support']).to(device)[:,None,:]
arrival=torch.from_numpy(source_fields['arrival']).to(device)[:,None,:]
tangent_x=torch.from_numpy(source_fields['dirx']).to(device)[:,None,:]
tangent_z=torch.from_numpy(source_fields['dirz']).to(device)[:,None,:]
halfwidth=torch.from_numpy(source_fields['sdf']).to(device)[:,None,:].clamp_min(0)
sheet_depth=.028+.026*(halfwidth/.27).clamp(0,1).sqrt()
source_fields.close()''')
begin=s.index('    # Only a spherical moving nozzle adds fuel; its reacting wake is free.')
end=s.index('    activation=((temp-.15)/.22).clamp(0,1)',begin)
s=s[:begin]+'''    # The original broad, tapered artwork supplies NEW gas. Existing fluid
    # is never clipped, quenched or projected back into this cross-section.
    age=t-arrival
    opened=torch.sigmoid(age/.026)
    leading=torch.exp(-((age-.08)/.105)**2)
    valve=math.exp(-3.2*max(0.,t-6.8))
    corrugation=.045*torch.sin(x*7+z*5-t*3.4)+.025*torch.sin(x*17-z*11+t*5.7)
    sheet=torch.exp(-((y-corrugation)/sheet_depth)**2*1.5)*support
    current=sheet*opened*valve
    # Fuel-rich inflow burns at its mixing interfaces with ambient oxygen.
    # The narrower travelling ignition front carries stronger momentum.
    front=(sheet*leading*dt*34).clamp(0,1)
    sustained=(current*dt*5.0).clamp(0,1)
    inject=(front+sustained).clamp(0,1)
    fuel.lerp_(torch.ones_like(fuel)*.95,inject)
    oxygen.mul_(1-inject)
    temp.lerp_(torch.ones_like(temp)*.50,sustained)
    temp.lerp_(torch.ones_like(temp)*1.25,front)
    v=state[0,:3]
    speed=1.2+6.8*leading
    shear=4.8*torch.sin(y*19+t*13)*torch.cos((x+z)*12-t*11)
    v[0].lerp_(tangent_x*speed-tangent_z*shear,inject)
    v[1].lerp_(torch.sin(x*38+z*27+t*23)*.8,inject)
    v[2].lerp_(tangent_z*speed+tangent_x*shear,inject)
    wake=sheet*leading
    v[2].add_(wake*torch.sin(y*18+t*15)*20*dt)
    v[1].add_(wake*torch.cos(z*14-t*12)*16*dt)
    del age,opened,leading,corrugation,sheet,current,front,sustained,inject,speed,shear,wake
''' + s[end:]
begin=s.index('    # Turn the hot gas momentum, preserving speed before pressure projection.')
end=s.index('    # Resolved vorticity confinement retains rolled shear structures.',begin)
s=s[:begin]+s[end:]
s=s.replace('DURATION=8.5','DURATION=9.8').replace('TOTAL=255','TOTAL=294')
s=s.replace("video=ROOT/f'sigil-native/fire-{VARIANT}-free.mp4'","video=ROOT/'sigil-02/fire-02.mp4'")
s=s.replace("(ROOT/f'sigil-native/fire-{VARIANT}-free-report.json')","(ROOT/'sigil-02/fire-report.json')")
s=s.replace('Original moving nozzle deposits a subdued gas supply until 6.3s, then drains. No persistent tangent-velocity target. Only the local active jet receives authored turning.', 'Full approved 02 tapered geometry supplies a corrugated fuel sheet. A travelling ignition front and source momentum feed free reactive flow; fuel supply closes at 6.8s and drains. No render mask, oxygen boundary or glyph-shaped confinement.')
s=s.replace("'source':'bake-reactive-fire.py'","'source':'bending-fire.py with full approved 02 source geometry'")
s=s.replace('Accepted bending-fire solver/radiance with the approved sigil centerline as motion input. ', 'Original reactive-flow solver/radiance, sourced from the complete approved style-02 artwork. ')
s=s.replace('    render(frame)\nencoder.stdin.close()',"    render(frame)\n    if frame==135:\n        print('SOURCE 02 REVIEW GATE: frame 135',flush=True)\n        while not (ROOT/'sigil-02/continue').exists():time.sleep(.5)\nencoder.stdin.close()")
original=(R/'bending-fire.py').read_text(encoding='utf-8')
def function(text,name):
 node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name)
 return ast.get_source_segment(text,node)
assert function(s,'radiance')==function(original,'radiance')
assert 'nozzle_pose(' not in s and 'nozzle_turn(' not in s
compile(s,'sigil_02_fire.py','exec')
(R/'sigil_02_fire.py').write_text(s,encoding='utf-8')
(O/'build.json').write_text(json.dumps({'base':'bending-fire.py','radianceSha256':hashlib.sha256(function(s,'radiance').encode()).hexdigest(),'changed':'Source geometry, source scheduling and source momentum only; full-frustum simulation domain retained','preserved':['Advection and pressure solve','Reaction and cooling coefficients','Native buoyancy','Vorticity confinement','Original radiance and exposure'],'frames':294,'reviewGateFrame':135,'grid':[768,64,432]},indent=2))
print('Built full-geometry 02 fire; unchanged original radiance verified; 135-frame review gate.')
