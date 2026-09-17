"""Refine existing glass bodies and scanned botanical geometry in place."""
from pathlib import Path
import sys
Q=Path(__file__).resolve().parent;D=Q.parent/'dynamics';sys.path.insert(0,str(Q))
K=sys.argv[sys.argv.index('--kind')+1]
source=D/('render_glass.py' if K=='glass' else 'render_botanical.py')
code=source.read_text()
code=code.replace('from scene import *','from scene import *\nfrom common import setup as quality_setup, finish as quality_finish\nsetup=lambda samples=192: quality_setup(secondary_environment=True)\nfinish=quality_finish')
if K=='glass':
 code=code.replace('quality_setup(secondary_environment=True)','quality_setup(secondary_environment=False)')
 code=code.replace("s=setup(112);", "s=setup(112);\nfrom optical_lighting import narrow_cards\nnarrow_cards()\n")
 code=code.replace("(.98,1,.985),.012,trans=1,ior=1.52","(.98,1,.985),.032,trans=1,ior=1.52")
 code=code.replace("ab.inputs['Density'].default_value=.5","ab.inputs['Density'].default_value=1.2")
 start=code.index('wn=s.world.node_tree.nodes');end=code.index('objects=[]',start)
 code=code[:start]+"for light in bpy.data.lights:light.energy*=.42\n"+code[end:]
 needle="ob.rigid_body.kinematic=True;"
 code=code.replace(needle,"bevel=ob.modifiers.new('Polished fracture-edge bevels','BEVEL');bevel.width=.0012;bevel.segments=3;bevel.limit_method='ANGLE';bevel.angle_limit=.25\n    "+needle)
 code=code.replace("(R/'glass-mechanism.json')","(Q/'glass-mechanism.json')")
else:
 code=code.replace("stem=material(","leaf_lag=np.load(Q/'cpu/identity/leaf-lag.npy')\nstem=material(")
 code=code.replace("s=setup(96)","s=setup(192)\nfor light in bpy.data.lights:light.energy*=.42")
 code=code.replace("radii=data['radii']","radii=data['radii']")
 code=code.replace("(.033,.055,.014),.7","(.018,.043,.008),.52")
 needle="v=center+side*(local[:,0]*scale*unfurl)[:,None]+depth*(local[:,1]*scale*unfurl)[:,None]"
 replacement="roll=i*2.399+u*.8;oldside=side.copy();side=oldside*np.cos(roll)[:,None]+depth*np.sin(roll)[:,None];depth=depth*np.cos(roll)[:,None]-oldside*np.sin(roll)[:,None]\n        v=center+side*(local[:,0]*scale*unfurl*1.42)[:,None]+depth*(local[:,1]*scale*unfurl*1.18)[:,None]\n        v+=depth*(.004*unfurl*u*np.sin(t*3.2+u*8+i))[:,None]"
 assert needle in code;code=code.replace(needle,replacement)
 code=code.replace("v+=depth*(.004*unfurl*u*np.sin(t*3.2+u*8+i))[:,None]", "v+=depth*(leaf_lag[f,i]*scale*u*u*unfurl)[:,None]")
 code=code.replace("(.025,.85,.16,1)","(.015,.35,.16,1)")
 code=code.replace("front=wound*np.exp(-((age-.63)/.30)**2)*4","front=wound*np.exp(-((age-.63)/.30)**2)*2.2")
 if K=='healing':
  code=code.replace("ob.data.attributes.new('repair_front','FLOAT','POINT')", """ob.data.attributes.new('repair_front','FLOAT','POINT')
        ob.data.attributes.new('repair_damage','FLOAT','POINT')
        mod=ob.modifiers.new('Locally closing wound','NODES');g=bpy.data.node_groups.new('Repair cut '+str(i),'GeometryNodeTree');mod.node_group=g
        g.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');g.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
        inp=g.nodes.new('NodeGroupInput');out=g.nodes.new('NodeGroupOutput');cut=g.nodes.new('GeometryNodeDeleteGeometry');cut.domain='FACE';at=g.nodes.new('GeometryNodeInputNamedAttribute');at.data_type='FLOAT';at.inputs['Name'].default_value='repair_damage';compare=g.nodes.new('ShaderNodeMath');compare.operation='GREATER_THAN';compare.inputs[1].default_value=.67
        g.links.new(inp.outputs['Geometry'],cut.inputs['Geometry']);g.links.new(at.outputs['Attribute'],compare.inputs[0]);g.links.new(compare.outputs[0],cut.inputs['Selection']);g.links.new(cut.outputs[0],out.inputs['Geometry'])""")
  code=code.replace("front=wound*np.exp(-((age-.63)/.30)**2)*2.2", "ob.data.attributes['repair_damage'].data.foreach_set('value',(wound*(1-repair)).astype('f4'))\n            front=wound*np.exp(-((age-.63)/.30)**2)*4.0")
  code=code.replace("if len(active)>1:paths.append(x[active]);rr.append(radii[active])", """if len(active)>1:
            repair=np.clip((t-birth[ch[0]]-.35)/.65,0,1);u0=np.arange(len(active))/max(1,len(ch)-1)
            if repair<.90:
                for half in [active[u0<.55],active[u0>.64]]:
                    if len(half)>1:paths.append(x[half]);rr.append(radii[half])
            else:paths.append(x[active]);rr.append(radii[active])""")
namespace={'__file__':str(source),'__name__':'__quality_constructed__','Q':Q}
exec(compile(code,str(source),'exec'),namespace)
