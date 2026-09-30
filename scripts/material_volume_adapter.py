"""Native float32 VDB density sampling for the retained material renderer.

All channel geometry, discharge pulses, material shading and continuous detail
noise remain in the original pipeline. The grid uses physical solver centers.
"""

VDB_SETUP = r'''
native_vdb=os.environ.get('CYBR_NATIVE_VDB')=='1' and '--physics-only' not in args
if native_vdb:
 original_cloud=cloud;original_mesh=cloud.data
 volumeData=bpy.data.volumes.new('Fresh full-precision gas field')
 cloud=bpy.data.objects.new('Native VDB advected atmosphere',volumeData)
 bpy.context.collection.objects.link(cloud);volumeData.materials.append(vm)
 bpy.data.objects.remove(original_cloud,do_unlink=True);bpy.data.meshes.remove(original_mesh)
 info=vn.new('ShaderNodeVolumeInfo')
 # The retained atlas stores clip(rho/1.2,0,1). Keep that transfer function
 # and the original animated detail noise, now using float32 solver density.
 normalizedDensity=op('MINIMUM',op('MAXIMUM',op('DIVIDE',info.outputs['Density'],1.2),0),1)
 nativeDensity=op('MULTIPLY',op('MULTIPLY',normalizedDensity,detail),{'lightning':5.5,'lava':1.4,'ice':.30}[kind])
 vl.new(nativeDensity,volume.inputs['Density'])
 print('Native float32 VDB density active; solver cell-centered world transform',flush=True)
'''

VDB_UPDATE = r'''
 if native_vdb:
  volumePath=O/'vdb'/f'{f:04}.vdb'
  while not volumePath.exists():time.sleep(.3)
  cloud.data.filepath=str(volumePath)
  cloud.data.update_tag()
'''
