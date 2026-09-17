from pathlib import Path
p=Path('work/render_gas.py');s=p.read_text().replace("ROOT/'gas-preview-frames'","ROOT/'gas-final-frames'").replace('fuel.lerp_(torch.ones_like(fuel)*.30,gas_inject)','fuel.lerp_(torch.ones_like(fuel)*.22,gas_inject)')
s=s.replace('Single moving fuel nozzle with backward jet momentum; speed-preserving hot-gas turning; native buoyancy, reaction, pressure and radiance; no trail fitting, morph or cached particles.','One moving nozzle deposits a persistent gas supply along its continuous path. Supply releases fuel until physical t=15.0, then stops by 15.7. Camera pulls back at screen t=5.55-7.45. Native combustion, pressure and transport remain active. No text overlay.')
p.write_text(s)
