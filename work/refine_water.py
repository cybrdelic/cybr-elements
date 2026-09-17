from pathlib import Path
p=Path('work/render_water_sans.py').read_text()
p=p.replace("s.cycles.device='GPU'", "s.render.engine='BLENDER_EEVEE_NEXT';s.eevee.taa_render_samples=48;s.eevee.use_raytracing=True\ns.cycles.device='GPU'")
p=p.replace("hold=1 if t<11 else 0", "hold=(t < 11+.18*np.sin(g['phase'][:n]*.6))[:,None].astype(float)")
p=p.replace("force[:,2]-=9.81*(1-hold)","force[:,2]-=9.81*(1-hold[:,0])")
p=p.replace("force[:,1]+=.48*np.sin(g['phase'][:n]-t*8)*hold", "force[:,1]+=.8*np.sin(g['phase'][:n]-t*8)*hold[:,0]")
p=p.replace("radius=.075/", "radius=.085/")
p=p.replace("radius*=1+.10", "radius*=1+.16")
p=p.replace("radius[:2]*=[.30,.85]", "radius*=1+.5*np.exp(-np.maximum(0,t-g['born'][:n])/.16)\n        radius[:2]*=[.30,.85]")
# Ballistic spray accompanies the moving nozzle, then hits the receiving floor.
p=p.replace("old=obj.data;new=", '''for j in range(86):
        born=.15+j*.079;age=t-born
        if age<0:continue
        center,direction,on,speed=font.pose(born*1.875)
        if on<.5:continue
        initial=np.array([center[0],0.,center[1]])
        velocity=np.array([-direction[0]*.75+.30*math.sin(j*7),.45*math.sin(j*4),-direction[1]*.75+.6])
        center=initial+velocity*age+np.array([0,0,-1.8])*age*age
        radius=.022+.009*(.5+.5*math.sin(j*13))
        squash=1.
        if center[2]<-.36: center[2]=-.365;squash=.18;radius*=2.0
        base=len(verts)
        for lat in range(9):
            phi=math.pi*(lat+.001)/8.002
            for k in range(12):
                theta=k*math.tau/12
                verts.append((center+radius*np.array([math.sin(phi)*math.cos(theta),math.sin(phi)*math.sin(theta),math.cos(phi)*squash])).tolist())
        for lat in range(8):
            for k in range(12):faces.append((base+lat*12+k,base+lat*12+(k+1)%12,base+(lat+1)*12+(k+1)%12,base+(lat+1)*12+k))
    old=obj.data;new=''')
Path('work/render_water_sans.py').write_text(p)
