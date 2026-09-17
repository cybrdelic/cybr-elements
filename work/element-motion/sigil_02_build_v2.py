from pathlib import Path
import ast,json,hashlib
R=Path(__file__).resolve().parent;O=R/'sigil-02-v2'
s=(R/'sigil_02_fire.py').read_text(encoding='utf-8').replace('sigil-02/','sigil-02-v2/')
s=s.replace('lo=np.array([-5.25,-.6,-1.05],np.float32)','lo=np.array([-7.,-.6,-1.05],np.float32)')
s=s.replace('extent=np.array([10.5,1.2,5.90625],np.float32)','extent=np.array([14.,1.2,7.875],np.float32)')
s=s.replace('x=lo[0]+(xx+1)*float(extent[0])*.5','x=torch.linspace(float(lo[0]),float(lo[0]+extent[0]),X,device=device)[None,None,:]')
s=s.replace('y=lo[1]+(yy+1)*float(extent[1])*.5','y=torch.linspace(float(lo[1]),float(lo[1]+extent[1]),Y,device=device)[None,:,None]')
s=s.replace('z=lo[2]+(zz+1)*float(extent[2])*.5','z=torch.linspace(float(lo[2]),float(lo[2]+extent[2]),Z,device=device)[:,None,None]')
s=s.replace('source=torch.exp(-((x/.32)**4+(y/.245)**4+((z-.34)/.075)**4))\nsource=(source>.01)*source\n','')
s=s.replace('front=(sheet*leading*dt*34)','front=(sheet*leading*dt*20)')
s=s.replace('sustained=(current*dt*5.0)','sustained=(current*dt*2.5)')
s=s.replace('    fuel.lerp_(torch.ones_like(fuel)*.95,inject)','    fuel.lerp_(torch.ones_like(fuel)*.55,sustained)\n    fuel.lerp_(torch.ones_like(fuel)*.95,front)')
s=s.replace('speed=1.2+6.8*leading','speed=.25+7.75*leading')
s=s.replace('shear=4.8*torch.sin(y*19+t*13)*torch.cos((x+z)*12-t*11)','shear=4.8*torch.sin(y*19+t*13)*torch.cos((x+z)*12-t*11)*leading')
s=s.replace('v[1].lerp_(torch.sin(x*38+z*27+t*23)*.8,inject)','v[1].lerp_(.18+torch.sin(x*38+z*27+t*23)*(.12+.68*leading),inject)')
def function(text,name):
 node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name)
 return ast.get_source_segment(text,node)
assert function(s,'radiance')==function((R/'bending-fire.py').read_text(),'radiance')
compile(s,'sigil_02_fire_v2.py','exec');(R/'sigil_02_fire_v2.py').write_text(s,encoding='utf-8')
(O/'changes.json').write_text(json.dumps({'issue':'First full-geometry trial overfed the broad source and rising flames reached the domain top','changes':['Lower sustained fuel throughput, from 5*.95 to 2.5*.55','Keep strong shear and 8m/s source momentum at the travelling front only','Quiet gas supply after the front passes','Expand the full camera volume to 14 x 7.875 metres','896 x 56 x 504 grid, with broadcast coordinates to reduce GPU memory'],'preserved':['Approved 02 complete tapered source geometry','Reaction, cooling, buoyancy and vorticity','Original radiance and exposure'],'reviewGateFrame':135},indent=2))
print('Prepared lower-throughput 02 simulation with a larger physical domain. Original fire optics unchanged.')
