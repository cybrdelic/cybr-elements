from pathlib import Path
s=Path('work/render_gesture.py').read_text()
s=s.replace("ROOT/'gesture-final-frames'","ROOT/'gas-preview-frames'").replace("'cybrdelic-fire-gesture.mp4'","'cybrdelic-gas-trail.mp4'").replace("'gesture-report.json'","'gas-report.json'").replace("'14.43'","'10.0'")
s=s.replace('state[:,4]=1','state[:,4]=1\nreservoir=torch.zeros(shape,device=device)')
s=s.replace('    inject=(nozzle*on*dt*(35+speed*10)).clamp(0,1)', '''    inject=(nozzle*on*dt*(35+speed*10)).clamp(0,1)
    # The moving tip lays down a thin local gas supply, never a prefilled word mask.
    line=torch.exp(-((across/.044)**2+(y/.05)**2+(along/.085)**2)*1.5)*on
    torch.maximum(reservoir,line,out=reservoir)
    supply=max(0.,min(1.,(15.7-t)/.7))
    gas_inject=(reservoir*(1.8*dt*supply)).clamp(0,1)
    fuel.lerp_(torch.ones_like(fuel)*.30,gas_inject)
    oxygen.lerp_(torch.ones_like(oxygen)*.80,gas_inject)
    temp.lerp_(torch.ones_like(temp)*.80,gas_inject)''')
s=s.replace("    camera_x=float(np.mean([nozzle_pose(physical+lag)[0][0] for lag in np.linspace(-1.2,.35,18)]))\n    view_x=torch.linspace(camera_x-3.2,camera_x+3.2,W,device=device)\n    view_z=torch.linspace(3.6,0,H,device=device)",'''    following=float(np.mean([nozzle_pose(physical+lag)[0][0] for lag in np.linspace(-1.2,.35,18)]))
    zoom=np.clip((frame/FPS-5.55)/1.9,0,1)
    zoom=zoom*zoom*(3-2*zoom)
    camera_x=following*(1-zoom)
    view_width=6.4+(11.4-6.4)*zoom
    view_height=view_width*9/16
    view_x=torch.linspace(camera_x-view_width/2,camera_x+view_width/2,W,device=device)
    view_z=torch.linspace(1.8+view_height/2,1.8-view_height/2,H,device=device)''')
s=s.replace('    edge_x=((5.25-vx.abs())/.45).clamp(0,1)','    edge_x=((4.9-vx.abs())/.55).clamp(0,1)')
s=s.replace('    edge_z=torch.minimum((3.6-vz)/.45,vz/.12).clamp(0,1)','    edge_z=torch.minimum((3.75-vz)/.60,vz/.12).clamp(0,1)')
Path('work/render_gas.py').write_text(s)
print('Persistent deposited gas supply; pull back 5.55-7.45s; shut supply off 8.0-8.37s; 10s total.')
