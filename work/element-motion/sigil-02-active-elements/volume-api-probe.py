import bpy,json
for kind in ['GeometryNodeVolumeCube','GeometryNodePointsToVolume','GeometryNodeSampleIndex','GeometryNodeSampleNearest']:
 g=bpy.data.node_groups.new('probe','GeometryNodeTree')
 try:
  n=g.nodes.new(kind);print('NODE',kind,[(s.name,s.bl_idname) for s in n.inputs],[(s.name,s.bl_idname) for s in n.outputs])
 except Exception as e: print('NODE ERROR',str(e))
