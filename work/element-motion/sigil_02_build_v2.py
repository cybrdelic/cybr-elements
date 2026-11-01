"""Validate the historical v2 recipe; never overwrite maintained solver code."""
from pathlib import Path
import ast,json,hashlib,argparse
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
compile(s,'historical_sigil_02_fire_v2.py','exec')
expected='99b19f9725a755244f623433bdc8beb128bc1535d02f83d12b094dc204104005'
actual=hashlib.sha256(s.encode()).hexdigest()
if actual!=expected:raise RuntimeError('Historical twelve-replacement recipe changed; review its numerical provenance')
consumer=(R/'sigil_02_fire_v2.py').read_text(encoding='utf-8')
if "main('sigil_02_fire_v2')" not in consumer:raise RuntimeError('Style02 must use the maintained scene runtime')
owner=ast.parse((R/'element_choreography.py').read_text())
step=next(n for n in owner.body if isinstance(n,ast.FunctionDef) and n.name=='advance')
calls={n.func.attr for n in ast.walk(step) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Attribute) and n.func.value.attr=='flow'}
if not {'transport','project'}<=calls:raise RuntimeError('Fire must execute shared flow operators')
optics=ast.parse((R/'element_optics.py').read_text())
actual_optics=next(n for n in optics.body if isinstance(n,ast.FunctionDef) and n.name=='radiance_style02')
class Unbind(ast.NodeTransformer):
    def visit_Attribute(self,node):
        return ast.copy_location(ast.Name(node.attr,node.ctx),node) if isinstance(node.value,ast.Name) and node.value.id=='self' else self.generic_visit(node)
actual_optics=Unbind().visit(actual_optics);actual_optics.name='radiance';actual_optics.args.args=[]
expected_optics=ast.parse(function(s,'radiance')).body[0]
if ast.dump(actual_optics)!=ast.dump(expected_optics):raise RuntimeError('Fire optics changed; review separately')
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check',action='store_true',help='Validate provenance without writing recipe metadata')
args=parser.parse_args()
print(json.dumps({'historicalRecipeSha256':actual,'solverRewritten':False,'sharedFlowCalls':sorted(calls)}))
if args.check:raise SystemExit(0)
O.mkdir(parents=True,exist_ok=True)
(O/'changes.json').write_text(json.dumps({'issue':'First full-geometry trial overfed the broad source and rising flames reached the domain top','changes':['Lower sustained fuel throughput, from 5*.95 to 2.5*.55','Keep strong shear and 8m/s source momentum at the travelling front only','Quiet gas supply after the front passes','Expand the full camera volume to 14 x 7.875 metres','896 x 56 x 504 grid, with broadcast coordinates to reduce GPU memory'],'preserved':['Approved 02 complete tapered source geometry','Reaction, cooling, buoyancy and vorticity','Original radiance and exposure'],'reviewGateFrame':135},indent=2))
print('Validated historical v2 recipe and maintained shared-flow consumer; wrote recipe metadata only.')
