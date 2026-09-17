from pathlib import Path
s=Path('work/render_fire_hq.py').read_text()
s=s.replace('from intro_hq_motion import pose as nozzle_pose, turn_rate as nozzle_turn, WRITE, START, MODE','from cast_motion import emitters, turning, physical_time')
s=s.replace("ROOT/'fire-hq-frames'","ROOT/'cast-frames'").replace("'cybrdelic-fire-hq.mp4'","'cybrdelic-fire-cast.mp4'").replace("'fire-hq-report.json'","'cast-report.json'").replace("'9.5'","'7.0'")
a=s.index('    # Only a spherical moving nozzle');b=s.index('    activation=',a)
s=s[:a]+'''    # Compact moving fuel nozzles. No stationary text mask or target field.
    v=state[0,:3]
    for center,direction,on,speed,width,jet in emitters(t):
        cx,cz=center;dx,dz=direction
        center3=np.array([cx,0,cz]);radius=np.array([.38,.28,.38])
        low=np.maximum(0,np.floor((center3-radius-lo)/extent*(np.array(a.size)-1)).astype(int))
        high=np.minimum(np.array(a.size),np.ceil((center3+radius-lo)/extent*(np.array(a.size)-1)).astype(int)+1)
        if np.any(high<=low):continue
        sl=(slice(low[2],high[2]),slice(low[1],high[1]),slice(low[0],high[0]))
        px=x[sl]-float(cx);pz=z[sl]-float(cz);py=y[sl]
        across=-px*float(dz)+pz*float(dx);along=px*float(dx)+pz*float(dz)
        nozzle=torch.exp(-((across/width)**2+(py/.09)**2+(along/(width*.65))**2)*1.5)
        inject=(nozzle*on*dt*(35+speed*10)).clamp(0,1)
        fuel[sl].lerp_(torch.ones_like(inject)*.95,inject)
        oxygen[sl].mul_(1-inject)
        temp[sl].lerp_(torch.ones_like(inject)*1.15,inject)
        shear=(jet/3.5)*1.2*torch.sin(py*43+t*19)*torch.cos((px+pz)*29-t*17)
        v[0][sl].lerp_(-float(dx)*jet+shear*float(-dz),inject)
        v[1][sl].lerp_(torch.sin(px*38+pz*27+t*23)*(.8*jet/3.5),inject)
        v[2][sl].lerp_(-float(dz)*jet+shear*float(dx),inject)
''' +s[b:]
s=s.replace('float(nozzle_turn(t))','float(turning(t))')
s=s.replace('    v[2].add_((temp*3.4-soot*.32)*dt)', '''    # Smaller letter jets use proportionally lower lift during the brief cast.
    lift=.28 if 1.8<t<2.85 else 1.
    v[2].add_((temp*3.4-soot*.32)*(dt*lift))
    if t>2.85:
        release=min(1,(t-2.85)/.25)
        heat=(temp*.5+soot*3).clamp(0,1)
        v[0].add_(heat*(13*release*dt))
        v[2].add_(heat*(1.5*release*dt))''')
s=s.replace('*.72','*.48').replace('blur*.22','blur*.12')
s=s.replace('    for sub in range(a.substeps):div=step((frame+sub/a.substeps)/SIM_FPS)', '''    t0=float(physical_time(frame/FPS));t1=float(physical_time((frame+1)/FPS))
    dt=(t1-t0)/a.substeps
    for sub in range(a.substeps):div=step(t0+(sub+.5)*dt)''')
s=s.replace('Single moving fuel nozzle with backward jet momentum; speed-preserving hot-gas turning; native buoyancy, reaction, pressure and radiance; no trail fitting, morph or cached particles.','Overlapping moving fuel nozzles and broad entrance/exit gestures; native reactive fluid transport and pressure; scaled lift during small letter jets; slow-motion timing and hot-gas exit force. No text overlay or stationary letter fuel mask.')
Path('work/render_cast.py').write_text(s)
print('Cast renderer ready.')
