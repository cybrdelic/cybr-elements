"""Isolated 02 adaptations. Originals and approved fire remain immutable."""
from pathlib import Path
import ast,json
R=Path(__file__).resolve().parent
O=R/'sigil-02-elements';O.mkdir(exist_ok=True)
def function(s,name):
 n=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name==name)
 return ast.get_source_segment(s,n)
s=(R/'sigil_02_fire_v2.py').read_text()
s=s.replace("out = ROOT/'sigil-02-v2/fire-frames'","out = ROOT/'sigil-02-elements/air-frames'")
s=s.replace("video=ROOT/'sigil-02-v2/fire-02.mp4'","video=ROOT/'sigil-02-elements/air-02.mp4'")
s=s.replace("ROOT/'sigil-02-v2/continue'","ROOT/'sigil-02-elements/continue-air'")
s=s.replace("ROOT/'sigil-02-v2/fire-report.json'","ROOT/'sigil-02-elements/air-report.json'")
s=s.replace('sheet_depth=.028+.026','sheet_depth=.050+.040')
s=s.replace('sustained=(current*dt*2.5)','sustained=(current*dt*4.0)')
a=s.index('    fuel.lerp_(torch.ones_like(fuel)*.55,sustained)');b=s.index('    v=state[0,:3]',a)
s=s[:a]+'''    # Passive tracer injected in thin striated layers; velocity/pressure are
    # still solved volumetrically. The mark is only the source support.
    filament=.25+.75*(.5+.5*torch.sin(x*45+z*33+y*29-t*5)).pow(3)
    soot.lerp_(torch.ones_like(soot)*.85,inject*filament)
    fuel.zero_();temp.zero_()
''' + s[b:]
s=s.replace('speed=.25+7.75*leading','speed=.16+5.1*leading')
a=s.index('    activation=((temp-.15)/.22).clamp(0,1)');b=s.index('    v[0].add_',a)
s=s[:a]+'''    state[0,7].zero_()
    soot.mul_(math.exp(-.65*dt))
    temp.zero_()
''' + s[b:]
# No buoyancy from combustion: retain a small uniform draught.
s=s.replace('v[0].add_(.25*dt)','v[0].add_(.035*dt)')
s=s.replace('v[2].add_((temp*3.4-soot*.32)*dt)','v[2].add_(.035*dt)')
air=(R/'bending-air-v5.py').read_text()
render=function(air,'render').replace('size=(768,1920)','size=(1080,1920)').replace('linear=F.pad(linear,(0,0,120,192))','linear=linear')
s=s.replace(function(s,'render'),render)
s=s.replace("'source':'bending-fire.py with full approved 02 source geometry'","'source':'bending-air-v5 optics and projected passive tracer flow, full approved 02 source geometry'")
s=s.replace("'changes':'Original reactive-flow solver/radiance, sourced from the complete approved style-02 artwork. Full approved 02 tapered geometry supplies a corrugated fuel sheet. A travelling ignition front and source momentum feed free reactive flow; fuel supply closes at 6.8s and drains. No render mask, oxygen boundary or glyph-shaped confinement. No silhouette clipping or filled glyph volume. Art-directed source, free reacting wake.'","'changes':'Full 02 source cross-section with thin passive tracer filaments; free pressure-projected transport and native directional volume optics. Source drains after 6.8 seconds.'")
compile(s,'sigil_02_air.py','exec');(R/'sigil_02_air.py').write_text(s)
(O/'contract.json').write_text(json.dumps({'variant':'02','approvedFire':'../sigil-02-v2/fire-02.mp4','elements':['water','earth','air','lightning'],'duration':9.8,'fps':30,'blackBackground':True,'geometry':'Full approved tapered source, no output-image mask','reviewFrames':[60,135,180,240,293],'iterationsPerElement':3,'gpuJobsAtOnce':1},indent=2))
print('Prepared air source adaptation and four-element review contract.')
