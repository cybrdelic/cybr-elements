"""Export the reviewed forest-surface tree, preserving every source triangle.

Blender is used as an asset reader only. No fire frames or GPU rendering.
"""
from pathlib import Path
import bpy,numpy as np,json,hashlib
ROOT=Path(__file__).resolve().parents[3]
WORLD=ROOT/'world'; SOURCE=WORLD/'output/forest-surface'
OUT=ROOT/'cybr-elements/outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/objects/forest-tree'
OUT.mkdir(parents=True,exist_ok=True)
state=np.load(WORLD/'output/forest-coupled/mature/stand-state.npz')
tree_id=json.loads((WORLD/'output/forest-refined/detail.json').read_text())['tree_index']
tree=state['trees'][tree_id];variant=int(tree[3])
with bpy.data.libraries.load(str(SOURCE/'forest.blend'),link=False) as (src,dst):
    dst.objects=[n for n in src.objects if n.startswith(f'Variant {variant} roots.')]+[next(n for n in src.objects if n.startswith(f'Variant {variant} wood.'))]
roots=min((o for o in dst.objects if 'roots' in o.name),key=lambda o:np.linalg.norm(np.array(o.location)[:2]-tree[:2]))
wood=next(o for o in dst.objects if 'wood' in o.name)
chunks=[];provenance=[]
def append_mesh(o,material):
    m=o.data;m.calc_loop_triangles();nv=len(m.vertices)
    v=np.empty(nv*3,np.float32);m.vertices.foreach_get('co',v);v=v.reshape(-1,3)
    n=np.empty(nv*3,np.float32);m.vertices.foreach_get('normal',n);n=n.reshape(-1,3)
    f=np.empty(len(m.loop_triangles)*3,np.int32);m.loop_triangles.foreach_get('vertices',f);f=f.reshape(-1,3)
    loops=np.empty(f.size,np.int32);m.loop_triangles.foreach_get('loops',loops)
    uv=np.empty(len(m.loops)*2,np.float32);m.uv_layers.active.data.foreach_get('uv',uv);uv=uv.reshape(-1,2)[loops]
    # Split UV seams, keeping normals from the actual displaced source mesh.
    verts=np.c_[v[f.ravel()],n[f.ravel()],uv,np.full(f.size,material)]
    verts,inv=np.unique(verts,axis=0,return_inverse=True)
    chunks.append((verts.astype('float32'),inv.astype('uint32').reshape(-1,3)))
    provenance.append({'object':o.name,'mesh':m.name,'sourceVertices':nv,'triangles':len(f)})
append_mesh(wood,1);append_mesh(roots,1)
parts=json.loads((WORLD/'output/forest-coupled/mature/parts/parts.json').read_text())['parts']
lookup={(p['cluster'],p['bucket']):p for p in parts}
rng=np.random.default_rng(9272026);foliage_count=0
for c,(owner,cluster) in enumerate(zip(state['owner'],state['cluster'])):
    shift=rng.random();order=rng.permutation(8)
    if owner!=tree_id:continue
    fraction=np.clip(state['area'][c]/max(state['capacity'][c],1e-20),0,1)
    buckets=[int(order[b]) for b in range(8) if (b+shift)/8<fraction]
    if buckets:buckets.append(8)
    for bucket in buckets:
        p=lookup.get((int(cluster),bucket))
        if p is None:continue
        d=np.load(WORLD/'output/forest-coupled/mature/parts'/p['file'])
        v=d['vertices'];f=d['faces'];n=np.zeros_like(v)
        fn=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
        for j in range(3):np.add.at(n,f[:,j],fn)
        n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12)
        chunks.append((np.c_[v,n,d['uv'],np.full(len(v),8 if bucket<8 else 1)].astype('float32'),f.astype('uint32')))
        foliage_count+=len(f)
vertices=[];faces=[];offset=0
for v,f in chunks:vertices.append(v);faces.append(f+offset);offset+=len(v)
v=np.concatenate(vertices);f=np.concatenate(faces)
# Display model scale is explicit: the fixed fluid chamber is six metres wide.
# The complete source topology and metre UVs are retained.
lo=v[:,:3].min(0);hi=v[:,:3].max(0);scale=2.7/max(hi-lo);center=(lo+hi)*.5
v[:,:3]=(v[:,:3]-center)*scale
v[:,:3]=v[:,[0,2,1]];v[:,3:6]=v[:,[3,5,4]]
f=f[:,[0,2,1]] # coordinate swap reverses winding
v.astype('<f4').tofile(OUT/'vertices.bin');f.astype('<u4').tofile(OUT/'indices.bin')
np.savez_compressed(OUT/'source-mesh.npz',vertices=v,faces=f)
(OUT/'source-space.js').write_text('export const SOURCE_SCALE='+str(float(scale))+';\nexport const SOURCE_CENTER='+json.dumps(center.tolist())+';\n')
for name in ['bark-color.png','bark-micro.png','bark-roughness.png']:
    (OUT/name).write_bytes((SOURCE/name).read_bytes())
manifest={'source':'world/output/forest-surface/forest.blend','treeIndex':int(tree_id),'variant':variant,
 'sourceTreeMetres':tree.tolist(),'normalization':{'scale':float(scale),'center':center.tolist(),'axis':'source XYZ to browser XZY'},
 'vertices':len(v),'triangles':len(f),'foliageTriangles':foliage_count,'vertexStride':36,'sourceMeshes':provenance,
 'geometrySimplified':False,'barkRelief':'Actual displaced wood and root vertices from forest-surface; residual microrelief retained',
 'files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in OUT.iterdir() if p.suffix in ['.bin','.png']}}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({k:manifest[k] for k in ['treeIndex','variant','vertices','triangles','foliageTriangles','sourceMeshes']}),flush=True)
