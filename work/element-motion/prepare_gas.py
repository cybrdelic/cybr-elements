from pathlib import Path
R=Path(__file__).resolve().parent;source=(R.parent/'render_trail.py').read_text(encoding='utf-8')
for element in ['fire','air']:
 s=source.replace('from trail_motion import pose as nozzle_pose, turn_rate as nozzle_turn, WRITE, START, MODE','from motion import pose as nozzle_pose, turn_rate as nozzle_turn, WRITE, START, MODE')
 s=s.replace("out = ROOT/'trail-frames'",f"out = ROOT/'{element}-frames'")
 s=s.replace("DURATION=float(os.environ.get('INTRO_SECONDS','6.0'))","DURATION=4.0")
 s=s.replace("video=ROOT.parent/'outputs'/('fire-trail-study.mp4' if MODE=='arc' else 'cybrdelic-fire-trail.mp4')",f"video=ROOT.parent.parent/'outputs/cybrdelic-type/elements/motion/{element}-test.mp4'")
 s=s.replace("if frame%15==0 or frame==TOTAL-1:","if frame%5==0 or frame==TOTAL-1:")
 s=s.replace("(ROOT/'trail-report.json')",f"(ROOT/'{element}-report.json')")
 s=s.replace('blur*.22','blur*.06').replace('fade=max(0.,min(1.,(DURATION-frame/FPS)/.7)) if DURATION>6 else 1.','fade=1.')
 if element=='air':
  s=s.replace('burn=torch.minimum(fuel,oxygen*.7)*(1-math.exp(-8*dt))*activation','burn=torch.zeros_like(fuel)')
  s=s.replace('temp.lerp_(torch.ones_like(temp)*1.25,inject)','soot.lerp_(torch.ones_like(soot)*.6,inject);temp.zero_()')
  s=s.replace("soot.add_(burn*.8).mul_(math.exp(-1.15*dt))","soot.mul_(math.exp(-.35*dt))")
  start=s.index('    rgb,sigma=radiance()',s.index('def render(frame):'))
  end=start+len('    rgb,sigma=radiance()')
  s=s[:start]+"    sigma=state[0,6]*2.4\n    depthLight=torch.exp(-torch.cumsum(sigma,dim=0)*float(h[2])*.55)\n    rgb=sigma[...,None]*depthLight[...,None]*torch.tensor([.66,.75,.80],device=device)*1.8"+s[end:]
  s=s.replace('v[2].add_((temp*3.4-soot*.32)*dt)','v[0].add_(.25*dt)')
 (R/f'{element}.py').write_text(s,encoding='utf-8')
print('Prepared original 3D advection/pressure/combustion core for separate fire and tracer tests')
