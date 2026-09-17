from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'sigil_02_repair_earth.py').read_text()
insert='''# CC0 photogrammetry from Poly Haven; preserve native UV material maps.
scanMeshes=[]
for asset in ['boulder_01','rock_07','rock_09']:
 before=set(bpy.data.objects)
 bpy.ops.import_scene.gltf(filepath=str(R/'sigil-02-repair/scans'/asset/f'{asset}_2k.gltf'))
 imported=[o for o in bpy.data.objects if o not in before]
 for item in imported:
  if item.type!='MESH':continue
  mesh=item.data.copy();mesh.transform(item.matrix_world)
  center=sum((v.co for v in mesh.vertices),Vector())/len(mesh.vertices)
  radius=max((v.co-center).length for v in mesh.vertices)
  for v in mesh.vertices:v.co=(v.co-center)/radius
  mesh.update();scanMeshes.append(mesh)
 for item in imported:bpy.data.objects.remove(item,do_unlink=True)
assert len(scanMeshes)>=3
'''
where='births=[];spawned=[]';assert where in s;s=s.replace(where,insert+'\n'+where)
s=s.replace("child=bpy.data.objects.new('Layered stone '+str(k),layerMeshes[family])","child=bpy.data.objects.new('Scanned stone '+str(k),scanMeshes[k%len(scanMeshes)] if r>.052 else layerMeshes[family])")
s=s.replace("'sigil-02-repair/earth-pilot'","'sigil-02-repair/earth-pilot-scanned'")
s=s.replace('f in [46,67,91,145]','f in [67]')
s=s.replace("'trail':'Full02 variable-width 3D source'","'trail':'Full02 variable-width 3D source','scanAssets':['boulder_01','rock_07','rock_09'],'scanLicense':'CC0 / Poly Haven'")
(R/'sigil_02_repair_earth_scanned.py').write_text(s)
print('Prepared scanned-rock CPU pilot.')
