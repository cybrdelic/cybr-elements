from pathlib import Path
import json
R=Path(__file__).resolve().parent
groups={
 'production-a':[('lava','lava.py'),('sand','grains.py'),('snow','grains.py')],
 'production-b':[('crystal','solids.py'),('metal','metal.py'),('glass','fracture.py')],
 'production-c':[('spirit','spirit.py'),('energy','entities.py'),('spirit-projection','entities.py'),('healing','healing.py'),('sound','black-fields.py'),('seismic','black-fields.py'),('heat','black-fields.py'),('pressure','grains.py'),('flight','grains.py'),('lightning','electric.py'),('lightning-redirection','electric.py')]
}
p=R/'solids.py';s=p.read_text(encoding='utf-8').replace('floor=bpy.context.object;','floor=bpy.context.object;floor.visible_camera=False;');p.write_text(s,encoding='utf-8')
for name,items in groups.items():
 jobs=[{'name':k+'-black-full','script':script,'args':['--kind',k,'--full']} for k,script in items]
 (R/(name+'.json')).write_text(json.dumps(jobs,indent=2),encoding='utf-8')
print('Production groups:',{k:len(v) for k,v in groups.items()})
