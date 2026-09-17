from pathlib import Path
ROOT=Path(__file__).resolve().parent
source=Path(r'C:\Users\alexf\Documents\Codex\2026-09-04\re\work\cybrdelic.github.io\tools\bake-reactive-fire.py')
code=source.read_text().split('total=round((a.warmup+a.seconds)*a.fps)')[0]
code=code.replace('ROOT = Path(__file__).resolve().parents[1]','ROOT = Path(__file__).resolve().parent')
code=code.replace("out = ROOT/'output'/a.name","out = ROOT/'flow-frames'")
code=code.replace("12*1024**3", "1024**3").replace('12 GiB free-space reserve required','1 GiB MP4 free-space reserve required')
code=code.replace("else:\n    from bending_fire_moves import pose as gesture_pose", "else:\n    gesture_pose=None")
code=code.replace('lo=np.array([-1.2,-1.24,.15],np.float32)','lo=np.array([-5.25,-.50,0],np.float32)')
code=code.replace('extent=np.array([183,103,223],np.float32)*(5.5/224)','extent=np.array([10.5,1.,4.2],np.float32)')
code=code.replace('source=(source>.01)*source', '''source=(source>.01)*source
from flow_paths import fields
curves,fg,nearest,tangents,distance,curve_ids=fields(x[0,0].cpu().numpy(),z[:,0,0].cpu().numpy())
def gpu(a):return torch.from_numpy(np.asarray(a,dtype=np.float32)).to(device)
near=gpu(nearest);target=gpu(tangents)
dist=gpu(distance)
support=torch.exp(-(dist[:,None,:]/.19)**4-(y/.24)**4)
offset_x=x-near[:,None,:,0];offset_z=z-near[:,None,:,1]
tx=target[:,None,:,0];tz=target[:,None,:,1]
nozzles=[]
for curve in curves:
    px,pz=curve['points'][0]
    nozzle=torch.exp(-(((x-px)/.070)**2+(y/.075)**2+((z-pz)/.070)**2)*2)
    nozzles.append((nozzle,curve))
# Streamfunction supplies a divergence-free jet with a surrounding return flow.
# Its curl carries momentum around a stroke; it does not alter scalar positions.
psi2=(-offset_x*tz+offset_z*tx)*torch.exp(-(dist[:,None,:]/.15)**4)
psi=psi2*torch.exp(-(y/.20)**4)
flow_guide=torch.stack([(torch.roll(psi,-1,0)-torch.roll(psi,1,0))/(2*h[2]),torch.zeros_like(x),-(torch.roll(psi,-1,2)-torch.roll(psi,1,2))/(2*h[0])])
state[0,:3]=flow_guide
del psi,psi2
''')
start=code.index('    inlet=1. if not a.pulse')
end=code.index('    activation=((temp-.15)',start)
code=code[:start]+'''    # Only point-like nozzles inject fuel, briefly. No glyph-shaped source.
    v=state[0,:3]
    for nozzle,curve in nozzles:
        age=t-curve['start']
        on=max(0.,min(1.,age/.10))*max(0.,min(1.,(2.05-age)/.18))
        on*=.82+.18*math.sin(t*34+curve['letter']*2.7)
        inject=(nozzle*on*dt*22).clamp(0,1)
        fuel.lerp_(torch.ones_like(fuel)*.95,inject)
        oxygen.mul_(1-inject)
        temp.lerp_(torch.ones_like(temp)*1.25,inject)
        dx,dz=curve['tangent'][0]*curve['speed']
        pulse=1+.20*math.sin(t*28+curve['letter']*1.9)
        dx*=pulse;dz*=pulse
        v[0].lerp_(torch.ones_like(x)*float(dx),inject)
        v[1].lerp_(torch.ones_like(y)*(.24*math.sin(t*23+curve['letter'])),inject)
        v[2].lerp_(torch.ones_like(z)*float(dz),inject)
''' + code[end:]
start=code.index('    # Resolved vorticity confinement')
code=code[:start]+'''    # Low-frequency momentum guidance; no scalar field is fitted or moved.
    hold=max(0.,min(1.,(3.2-t)/.65))
    v.lerp_(flow_guide,1-math.exp(-12*hold*dt))
    v[2].sub_((temp*3.4-soot*.32)*(hold*dt))
    # Release the same gas into a diagonal outgoing draft.
    release=max(0.,min(1.,(t-2.55)/.65))
    v[0].add_(release*1.8*dt);v[2].add_(release*.35*dt)
''' +code[start:]
base=(ROOT/'build_intro.py').read_text()
tail=base.split("code += '''",1)[1].rsplit("'''",1)[0]
tail=tail.replace("'7.5'","'6.5'").replace('cybrdelic-fire-intro.mp4','cybrdelic-flow-intro.mp4')
tail=tail.replace('size=(720,1920)','size=(768,1920)').replace('(0,0,155,205)','(0,0,120,192)')
tail=tail.replace('*.34','*1.15').replace("'render-report.json'","'flow-report.json'")
tail=tail.replace('Letter-shaped fuel inlet with left-to-right ignition; original transport, combustion, vorticity, pressure and radiance; linear-light bloom.','Short point nozzles; momentum guided stroke flow; native reactive advection and pressure; finite fuel pulses followed by release.')
code+=tail
(ROOT/'render_flow.py').write_text(code)
print(ROOT/'render_flow.py')
