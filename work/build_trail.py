from pathlib import Path
root=Path(__file__).resolve().parent
source=Path(r'C:\Users\alexf\Documents\Codex\2026-09-04\re\work\cybrdelic.github.io\tools\bake-reactive-fire.py')
code=source.read_text().split('total=round((a.warmup+a.seconds)*a.fps)')[0]
code=code.replace('ROOT = Path(__file__).resolve().parents[1]','ROOT = Path(__file__).resolve().parent')
code=code.replace("out = ROOT/'output'/a.name","out = ROOT/'trail-frames'")
code=code.replace("12*1024**3", "1024**3").replace('12 GiB free-space reserve required','1 GiB streaming render reserve required')
code=code.replace("else:\n    from bending_fire_moves import pose as gesture_pose", "else:\n    gesture_pose=None\nfrom trail_motion import pose as nozzle_pose, turn_rate as nozzle_turn, WRITE, START, MODE")
code=code.replace('lo=np.array([-1.2,-1.24,.15],np.float32)',"lo=np.array([-5.25,-3. if MODE=='word' else -.6,0],np.float32)")
code=code.replace('extent=np.array([183,103,223],np.float32)*(5.5/224)',"extent=np.array([10.5,6. if MODE=='word' else 1.2,4.2],np.float32)")
start=code.index('    inlet=1. if not a.pulse')
end=code.index('    activation=((temp-.15)',start)
code=code[:start]+'''    # Only a spherical moving nozzle adds fuel; its reacting wake is free.
    center,direction,on,speed=nozzle_pose(t)
    cx,cz=center;dx,dz=direction
    px=x-float(cx);pz=z-float(cz)
    across=-px*float(dz)+pz*float(dx);along=px*float(dx)+pz*float(dz)
    nozzle=torch.exp(-((across/.115)**2+(y/.100)**2+(along/.065)**2)*1.5)
    if MODE=='word':nozzle=torch.exp(-((px/.080)**2+((y+2.)/.100)**2+(pz/.080)**2)*1.5)
    inject=(nozzle*on*dt*(35+speed*10)).clamp(0,1)
    fuel.lerp_(torch.ones_like(fuel)*.95,inject)
    oxygen.mul_(1-inject)
    temp.lerp_(torch.ones_like(temp)*1.25,inject)
    v=state[0,:3]
    shear=1.2*torch.sin(y*43+t*19)*torch.cos((px+pz)*29-t*17)
    if MODE=='arc':
        v[0].lerp_(-float(dx)*3.5+shear*float(-dz),inject)
        v[1].lerp_(torch.sin(px*38+pz*27+t*23)*.8,inject)
        v[2].lerp_(-float(dz)*3.5+shear*float(dx),inject)
    else:
        v[0].lerp_(shear*.35,inject)
        v[1].lerp_(torch.ones_like(y)*3.5+shear*.3,inject)
        v[2].lerp_(shear*.3,inject)
''' +code[end:]
start=code.index('    # Resolved vorticity confinement')
code=code[:start]+'''    # Turn the hot gas momentum, preserving speed before pressure projection.
    # Native buoyancy, scalar transport and combustion remain active.
    angle=(temp*.8+soot*4).clamp(0,1)*(float(nozzle_turn(t))*dt if MODE=='arc' else 0.)
    c=angle.cos();s=angle.sin();old_x=v[0].clone()
    v[0].mul_(c).sub_(v[2]*s);v[2].mul_(c).add_(old_x*s)
    del angle,c,s,old_x
    if MODE=='word':
        lift=max(0.,min(1.,(START+WRITE+.35-t)/.20))*.65
        v[2].sub_((temp*3.4-soot*.32)*(lift*dt))
''' +code[start:]
tail=(root/'build_intro.py').read_text().split("code += '''",1)[1].rsplit("'''",1)[0]
tail=tail.replace('FPS=30','FPS=30\nSIM_FPS=a.fps')
tail=tail.replace("'7.5'","'6.0'").replace("'cybrdelic-fire-intro.mp4'","('fire-trail-study.mp4' if MODE=='arc' else 'cybrdelic-fire-trail.mp4')")
tail=tail.replace('step((frame+sub/a.substeps)/FPS)','step((frame+sub/a.substeps)/SIM_FPS)')
tail=tail.replace('size=(720,1920)','size=(768,1920)').replace('(0,0,155,205)','(0,0,120,192)')
tail=tail.replace('*.34','*.72')
tail=tail.replace('F.avg_pool2d(F.avg_pool2d(linear,21,stride=1,padding=10),21,stride=1,padding=10)','F.avg_pool2d(F.avg_pool2d(linear,(1,21),stride=1,padding=(0,10)),(21,1),stride=1,padding=(10,0))')
tail=tail.replace("'render-report.json'","'trail-report.json'").replace('Letter-shaped fuel inlet with left-to-right ignition; original transport, combustion, vorticity, pressure and radiance; linear-light bloom.','Single moving fuel nozzle with backward jet momentum; speed-preserving hot-gas turning; native buoyancy, reaction, pressure and radiance; no trail fitting, morph or cached particles.')
code+=tail
(root/'render_trail.py').write_text(code)
print(root/'render_trail.py')
