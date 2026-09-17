"""Reuse the actual shader setup from the reviewed material studies."""
from pathlib import Path
import sys
R=Path(__file__).resolve().parent;D=R.parent/'dynamics';sys.path.insert(0,str(D))
import scene
import bpy
def build(kind):
    script={'metal':'render_mpm.py','sand':'render_mpm.py','snow':'render_mpm.py','ice':'render_phase.py','lava':'render_phase.py','glass':'render_glass.py','mud':'render_liquid.py','blood':'render_liquid.py','foam':'render_foam.py'}.get(kind)
    if script:
        code=(D/script).read_text(encoding='utf-8').split('objects=[]')[0]
        ns={'__file__':str(D/script),'__name__':'sigil_material_setup'}
        exec(compile(code,str(D/script),'exec'),ns)
        return ns
    s=scene.setup(96)
    if kind in ['energy','spirit','lightning','lightning-redirection','spirit-projection']:
        from channels import build as channels
        scene.glare(s,1.7,-.9)
        return {'s':s,'mats':channels(kind)}
    if kind=='crystal':
        mat=scene.material('Amethyst',(.62,.30,.8),.045,trans=1,ior=1.544)
        n=mat.node_tree.nodes;l=mat.node_tree.links;a=n.new('ShaderNodeVolumeAbsorption');a.inputs['Color'].default_value=(.38,.045,.62,1);a.inputs['Density'].default_value=5;l.new(a.outputs[0],n.get('Material Output').inputs['Volume'])
    elif kind in ['plants','healing']:mat=scene.material('Fibrous living stem',(.033,.055,.014),.7)
    elif kind=='flight':mat=scene.material('Fine wake tracers',(.38,.47,.51),.26)
    else:mat=scene.material('Granular seismic witness',(.20,.13,.065),.7)
    return {'s':s,'mat':mat}
