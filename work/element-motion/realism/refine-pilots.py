from pathlib import Path
R=Path(__file__).resolve().parent
def edit(name,changes):
 p=R/name;s=p.read_text(encoding='utf-8')
 for a,b in changes:
  assert a in s,(name,a[:60]);s=s.replace(a,b)
 p.write_text(s,encoding='utf-8')
edit('grains.py', [('rock_material(gain=.10)','rock_material(gain=.008)'),("# Six dendritic arms, secondary forks and a porous core in every aggregate.","# Fine dendrites form irregular porous aggregates.\n radii*=.6"),('base=np.array(vv);faces=', '''base0=np.array(vv);f0=list(ff);vv=[];ff=[]
 for cluster in range(3):
  rot0=np.linalg.qr(rng.normal(size=(3,3)))[0];offset=len(vv);vv.extend(base0@rot0*.7+rng.normal(0,.20,3));ff.extend([tuple(np.array(face)+offset) for face in f0])
 base=np.array(vv);faces=''')])
edit('waves.py', [("(.18,.12,.046),.31,metal=.8","(.028,.033,.038),.24,metal=.95"),('gain=.18 if K==\'seismic\' else .22','gain=.008 if K==\'seismic\' else .025'),('4 if K==\'seismic\' else 2','2 if K==\'seismic\' else .7')])
edit('entities.py',[("l.new(scale.outputs['Distance'],bu.inputs[0])","l.new(scale.outputs['Distance'],bu.inputs['Height'])"),("for ob,rest in parts:\n    ob.hide_render=ft<.08", "for child in root.children:child.hide_render=ft<.08\n   for ob,rest in parts:\n    ob.hide_render=ft<.08")])
print('Refined lighting, aggregate scale and entity geometry')
