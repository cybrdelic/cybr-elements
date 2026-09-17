from pathlib import Path
p=Path('work/render_gas.py');s=p.read_text()
s=s.replace("ROOT/'gas-final-frames'","ROOT/'gas-hold-frames'").replace("'cybrdelic-gas-trail.mp4'","'cybrdelic-gas-hold.mp4'").replace("'gas-report.json'","'gas-hold-report.json'").replace("'10.0'","'15.0'")
s=s.replace('    supply=max(0.,min(1.,(15.7-t)/.7))\n    gas_inject=(reservoir*(1.8*dt*supply)).clamp(0,1)', '''    # The line stays supplied through the full-view hold. Closing the valve
    # leaves a finite gas inventory which drains into the reacting fluid.
    gas_inject=(reservoir*(1.8*dt)).clamp(0,1)
    if t>=20.625:  # Screen time 11.0s at this simulation/playback ratio.
        reservoir.sub_(gas_inject).clamp_min_(0)''')
s=s.replace('    closing=min(1,max(0,(TOTAL-1-frame)/(FPS*.6)))\n    pixels=(im[0].permute(1,2,0)*edges[:,:,None]*closing*255).byte().cpu().numpy()', '''    # Fixed spatial camera-edge treatment only. No time-dependent image fade.
    top=torch.linspace(0,H-1,H,device=device).div(85).clamp(0,1)
    top=top*top*(3-2*top)
    edge_right=((4.82-vx)/.95).clamp(0,1)
    edge_right=edge_right*edge_right*(3-2*edge_right)
    departure=np.clip((frame/FPS-6.5)/.35,0,1)
    edges=edges*top[:,None]*(1-departure*(1-edge_right))
    pixels=(im[0].permute(1,2,0)*edges[:,:,None]*255).byte().cpu().numpy()''')
s=s.replace('    render(frame)\nencoder.stdin.close()', '''    render(frame)
    if frame in [239,329,TOTAL-1]:
        torch.save({'state':state,'reservoir':reservoir,'next_frame':frame+1,'size':a.size,'sim_fps':SIM_FPS,'substeps':a.substeps},ROOT/f'gas-hold-checkpoint-{frame+1}.pt')
    if frame%15==0 and frame>=300:
        print(json.dumps({'frame':frame,'time':frame/FPS,'gasInventory':float(reservoir.sum()),'fuelInFluid':float(state[0,3].sum()),'reaction':float(state[0,7].sum()),'maxTemperature':float(state[0,5].max())}),flush=True)
encoder.stdin.close()''')
s=s.replace('One moving nozzle deposits a persistent gas supply along its continuous path. Supply releases fuel until physical t=15.0, then stops by 15.7. Camera pulls back at screen t=5.55-7.45. Native combustion, pressure and transport remain active. No text overlay.','Gas supply stays open through screen t=11.0, giving 3.55 seconds in the fully zoomed-out view. After valve closure, finite gas inventory drains at the existing 1.8 per-second release rate; native fuel reaction, cooling and soot decay extinguish the fire. Constant exposure and opacity; no closing fade. Simulation checkpoints saved for future timing edits.')
Path('work/render_gas_hold.py').write_text(s)
print('3.55s full-view hold; finite gas depletion at 11s; native combustion/cooling only; 15s export.')
