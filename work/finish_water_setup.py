from pathlib import Path
p=Path('work/render_water_sans.py').read_text()
p=p.replace("s.render.engine='BLENDER_EEVEE_NEXT';s.eevee.taa_render_samples=48;s.eevee.use_raytracing=True", "s.render.engine='CYCLES';s.cycles.use_adaptive_sampling=True;s.cycles.adaptive_threshold=.08;s.cycles.adaptive_min_samples=4;s.render.use_persistent_data=True")
p=p.replace("phase=np.linspace(0,length,count)*25", "broken=np.zeros(count-1,dtype=bool),phase=np.linspace(0,length,count)*25")
p=p.replace("tension=normal*((length-g['rest'])*150)[:,None]", "g['broken'][:n-1]|=(length>g['rest']*2.8)&(t>10.8)\n        tension=normal*((length-g['rest'])*150*(~g['broken'][:n-1]))[:,None]")
p=p.replace("for k in range(16):faces.append((base+j*16+k,base+j*16+(k+1)%16,base+(j+1)*16+(k+1)%16,base+(j+1)*16+k))", "if g['broken'][j]:\n                faces.append(tuple(base+j*16+k for k in range(16)))\n                faces.append(tuple(base+(j+1)*16+k for k in reversed(range(16))))\n            else:\n                for k in range(16):faces.append((base+j*16+k,base+j*16+(k+1)%16,base+(j+1)*16+(k+1)%16,base+(j+1)*16+k))")
Path('work/render_water_sans.py').write_text(p)
