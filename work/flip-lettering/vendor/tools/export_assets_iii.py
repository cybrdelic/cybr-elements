"""Changing-topology USDA, complete primary PLY/OBJ, and stable-ID particle VAT.

USDA numeric payloads are independently checked by this tool. The report names
whether the optional official pxr reader is available; self-parsing is NOT an
external OpenUSD round trip. VAT uses lossless RGBA32F, not unstable mesh IDs.
"""
from __future__ import annotations
from pathlib import Path
import argparse,base64,gzip,hashlib,json,math,re,struct
import numpy as np
from export_sequence import export_mesh,export_primary
ROOT=Path(__file__).resolve().parents[1]

def mesh_data(path:Path,extent):
 b=gzip.decompress(path.read_bytes());magic,nv,nf,nd,nw,npp,cw,ch=struct.unpack_from('<8I',b)
 if magic!=0x43465234:raise ValueError('Expected CFR4')
 if len(b)!=32+nv*13+nf*12+nd*10+nw*24+npp*6+cw*ch*2:raise ValueError('Corrupt mesh length')
 p=np.frombuffer(b,'<u2',nv*3,32).reshape(-1,3).astype(np.float64)/65535*np.array(extent)
 n=np.frombuffer(b,'<i2',nv*3,32+nv*6).reshape(-1,3).astype(np.float64)/32767
 f=np.frombuffer(b,'<u4',nf*3,32+nv*13).reshape(-1,3);off=32+nv*13+nf*12
 d=np.frombuffer(b,'<u2',nd*3,off).reshape(-1,3).astype(np.float64)/65535*np.array(extent)
 radius=np.frombuffer(b,'<f4',nd,off+nd*6)
 if nf and int(f.max())>=nv:raise ValueError('Invalid triangle index')
 return p,n,f,d,radius

def vec_array(a):return '['+', '.join('('+', '.join(format(float(v),'.9g') for v in row)+')' for row in a)+']'
def scalar_array(a):return '['+', '.join(format(float(v),'.9g') for v in np.ravel(a))+']'
def int_array(a):return '['+', '.join(map(str,np.asarray(a).reshape(-1).tolist()))+']'

def export_usda(scene:str,frames:list[int],dest:Path):
 directory=ROOT/'cache'/scene;m=json.loads((directory/'manifest.json').read_text());samples=[]
 for i in frames:
  p,n,f,d,r=mesh_data(directory/f'{i:04d}.mesh.gz',m['config']['extent']);count=m['frames'][i]['particles']
  raw=np.fromfile(directory/f'{i:04d}.particles','<f4');assert len(raw)==count*6
  samples.append({'frame':i,'time':m['frames'][i]['time']/m['frameDt'],'p':p,'n':n,'f':f,'d':d,'r':r,'primary':raw[:count*3].reshape(-1,3),'velocity':raw[count*3:].reshape(-1,3)})
 dest.parent.mkdir(parents=True,exist_ok=True)
 with dest.open('w') as out:
  out.write('#usda 1.0\n(\n    defaultPrim = "Liquid"\n    metersPerUnit = 1\n    upAxis = "Y"\n    timeCodesPerSecond = %.12g\n    framesPerSecond = %.12g\n    startTimeCode = %.12g\n    endTimeCode = %.12g\n)\n\ndef Xform "Liquid" {\n' %(1/m['frameDt'],1/m['frameDt'],samples[0]['time'],samples[-1]['time']))
  def attribute(decl,key,formatter):
   out.write('        '+decl+'.timeSamples = {\n')
   for row in samples:out.write('            '+format(row['time'],'.12g')+': '+formatter(row[key])+',\n')
   out.write('        }\n')
  out.write('    def Mesh "Surface" {\n        uniform token subdivisionScheme = "none"\n        uniform token orientation = "rightHanded"\n        bool doubleSided = false\n')
  attribute('point3f[] points','p',vec_array);attribute('normal3f[] normals','n',vec_array)
  # Metadata is authored separately from the time sample map, as allowed by USDA.
  out.write('        normal3f[] normals ( interpolation = "vertex" )\n')
  attribute('int[] faceVertexCounts','f',lambda f:int_array(np.full(len(f),3)));attribute('int[] faceVertexIndices','f',int_array)
  out.write('    }\n    def Points "PrimaryParticles" {\n        uniform token purpose = "guide"\n')
  attribute('point3f[] points','primary',vec_array);attribute('vector3f[] velocities','velocity',vec_array)
  attribute('int64[] ids','primary',lambda p:int_array(np.arange(len(p),dtype=np.int64)))
  width=2*(3*(m['config']['h']*.5)**3/(4*np.pi))**(1/3)
  attribute('float[] widths','primary',lambda p:scalar_array(np.full(len(p),width)))
  out.write('    }\n    def Points "DetachedLiquid" {\n')
  attribute('point3f[] points','d',vec_array);attribute('float[] widths','r',lambda r:scalar_array(2*r))
  out.write('    }\n}\n')
 # Independent lexical payload check: never call this a pxr round trip.
 text=dest.read_text();blocks=re.findall(r'point3f\[\] points\.timeSamples = \{(.*?)\n        \}',text,re.S)
 error=0.
 for block,key in zip(blocks,['p','primary','d']):
  arrays=re.findall(r'[\d.eE+-]+:\s*\[(.*?)\],',block,re.S)
  assert len(arrays)==len(samples)
  for row,a in zip(samples,arrays):
   values=np.fromstring(re.sub(r'[(),]',' ',a),sep=' ').reshape(-1,3)
   assert values.shape==row[key].shape
   if values.size:error=max(error,float(np.max(np.abs(values-row[key]))))
 official={'available':False,'passed':None,'reason':'pxr is not installed; pip dependency retrieval failed due unavailable DNS in this execution environment.'}
 try:
  from pxr import Usd,UsdGeom
  stage=Usd.Stage.Open(str(dest));assert stage
  geom=UsdGeom.Mesh.Get(stage,'/Liquid/Surface')
  for row in samples:
   t=row['time'];assert len(geom.GetPointsAttr().Get(t))==len(row['p']);assert len(geom.GetFaceVertexIndicesAttr().Get(t))==row['f'].size
  official={'available':True,'passed':True}
 except ImportError:pass
 return {'path':str(dest.relative_to(ROOT)),'samples':len(samples),'changingTopology':True,'nativeTimeCodesPerSecond':1/m['frameDt'],'primaryVelocityUnits':'m/s','lexicalNumericCheck':True,'maximumPointSerializationError':error,'officialOpenUSDRoundTrip':official}

def export_vat(scene:str,dest:Path):
 directory=ROOT/'cache'/scene;m=json.loads((directory/'manifest.json').read_text());counts=[f['particles'] for f in m['frames']];n=max(counts);nf=len(counts)
 width=2**math.ceil(math.log2(math.sqrt(n)));rows=math.ceil(n/width);height=rows*nf
 positions=np.zeros((height,width,4),'<f4');velocities=np.zeros_like(positions)
 for frame,count in enumerate(counts):
  data=np.fromfile(directory/f'{frame:04d}.particles','<f4');assert data.size==count*6
  a=positions[frame*rows:(frame+1)*rows].reshape(-1,4);v=velocities[frame*rows:(frame+1)*rows].reshape(-1,4)
  a[:count,:3]=data[:count*3].reshape(-1,3);a[:count,3]=1;v[:count,:3]=data[count*3:].reshape(-1,3);v[:count,3]=1
 dest.mkdir(parents=True,exist_ok=True);pb=positions.tobytes();vb=velocities.tobytes()
 (dest/'positions.rgba32f').write_bytes(pb);(dest/'velocities.rgba32f').write_bytes(vb)
 metadata={'schema':'cybr-particle-vat/1','sourceScene':scene,'textureFormat':'RGBA32F','byteOrder':'little-endian','width':width,'height':height,'rowsPerFrame':rows,'frames':nf,'capacity':n,'counts':counts,'frameDt':m['frameDt'],'firstSimulationTime':m['frames'][0]['time'],'lengthUnit':'m','velocityUnit':'m/s','alpha':'1=live stable-ID primary marker, 0=unused; no mesh vertex correspondence is assumed','stableID':'primary array index; current solver appends emitters and has no particle deletion','positionSha256':hashlib.sha256(pb).hexdigest(),'velocitySha256':hashlib.sha256(vb).hexdigest()}
 (dest/'metadata.json').write_text(json.dumps(metadata,indent=2))
 # Decode from bytes and compare every original state (not merely first/last).
 a=np.fromfile(dest/'positions.rgba32f','<f4').reshape(height,width,4);v=np.fromfile(dest/'velocities.rgba32f','<f4').reshape(height,width,4)
 for f,count in enumerate(counts):
  raw=np.fromfile(directory/f'{f:04d}.particles','<f4');sl=a[f*rows:(f+1)*rows].reshape(-1,4);vl=v[f*rows:(f+1)*rows].reshape(-1,4)
  assert np.array_equal(sl[:count,:3].ravel(),raw[:count*3]);assert np.array_equal(vl[:count,:3].ravel(),raw[count*3:]);assert sl[:,3].sum()==count
 # Standalone browser exercise of the exported position texture. Camera scales to SI domain.
 three=(ROOT/'vendor/three.global.js')
 if not three.exists():three=next((ROOT/'vendor').glob('three*.js'))
 js=three.read_text().replace('</script','<\\/script')
 blob=base64.b64encode(gzip.compress(pb,compresslevel=6,mtime=0)).decode()
 html='''<!doctype html><meta charset="utf-8"><title>CYBR / Stable-ID particle VAT</title><style>body{margin:0;background:#0e1820;color:#def0f2;font:15px Arial}header{position:fixed;top:20px;left:25px}input{width:320px}</style><header><h2>CYBR / FLIP III · Particle VAT</h2><p>GPU playback of exported stable-ID particle positions; not live physics.</p><input id="frame" type="range" min="0" max="95" value="0"><span id="count"></span></header><script>'''+js+'''</script><script>
(async()=>{const meta=__VAT_METADATA_7815__,encoded="__VAT_PAYLOAD_7815__";const raw=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));const buffer=await new Response(new Blob([raw]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();const data=new Float32Array(buffer),texture=new THREE.DataTexture(data,meta.width,meta.height,THREE.RGBAFormat,THREE.FloatType);texture.minFilter=texture.magFilter=THREE.NearestFilter;texture.needsUpdate=true;
const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});renderer.setPixelRatio(1);renderer.setSize(innerWidth,innerHeight);document.body.append(renderer.domElement);const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(38,innerWidth/innerHeight,.0001,100);const extent=__VAT_EXTENT_7815__,s=Math.max(...extent);camera.position.set(extent[0]/2+s*.85,extent[1]/2+s*.45,extent[2]/2+s*1.1);camera.lookAt(...extent.map(x=>x/2));
const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(new Float32Array(meta.capacity*3),3));const uniforms={uTexture:{value:texture},uFrame:{value:0},uWidth:{value:meta.width},uRows:{value:meta.rowsPerFrame},uSize:{value:4.0}};
const material=new THREE.ShaderMaterial({glslVersion:THREE.GLSL3,uniforms,vertexShader:`uniform sampler2D uTexture;uniform int uFrame,uWidth,uRows;uniform float uSize;void main(){ivec2 uv=ivec2(gl_VertexID%uWidth,uFrame*uRows+gl_VertexID/uWidth);vec4 p=texelFetch(uTexture,uv,0);gl_Position=p.w>.5?projectionMatrix*modelViewMatrix*vec4(p.xyz,1.):vec4(2.,2.,2.,1.);gl_PointSize=uSize;}`,fragmentShader:`out vec4 result;void main(){vec2 q=gl_PointCoord*2.-1.;float d=dot(q,q);if(d>1.)discard;result=vec4(vec3(.2,.65,.85)*(1.-.45*d),1.);}`});const points=new THREE.Points(geometry,material);points.frustumCulled=false;scene.add(points);
function frame(i){i=Math.max(0,Math.min(meta.frames-1,i|0));uniforms.uFrame.value=i;renderer.render(scene,camera);document.getElementById('count').textContent=' Frame '+i+' / '+meta.counts[i]+' particles';return {frame:i,particles:meta.counts[i],glError:renderer.getContext().getError()};}document.getElementById('frame').max=meta.frames-1;document.getElementById('frame').oninput=e=>frame(+e.target.value);window.CYBR_VAT={metadata:meta,data,frame};frame(0);})().catch(e=>{window.CYBR_VAT_ERROR=e.stack;console.error(e);});</script>'''
 html=html.replace('__VAT_METADATA_7815__',json.dumps(metadata)).replace('__VAT_PAYLOAD_7815__',blob).replace('__VAT_EXTENT_7815__',json.dumps(m['config']['extent']))
 (dest/'viewer.html').write_text(html)
 return {'path':str(dest.relative_to(ROOT)),'passed':True,'type':'stable-ID primary particle VAT, not changing-topology mesh VAT','frames':nf,'capacity':n,'textureSize':[width,height],'allPositionsAndVelocitiesBitIdentical':True,'bytes':len(pb)+len(vb)}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--scene',default='capillary');ap.add_argument('--destination',type=Path,default=ROOT/'exports');args=ap.parse_args();out=args.destination;out.mkdir(parents=True,exist_ok=True)
 manifest=json.loads((ROOT/'cache'/args.scene/'manifest.json').read_text());frames=[0,36,72,95]
 report={'usda':export_usda(args.scene,frames,out/f'{args.scene}_changing_topology.usda'),'vat':export_vat(args.scene,out/f'{args.scene}_particle_vat'),'objPly':[]}
 import trimesh
 for frame in (0,72):
  mesh=out/f'{args.scene}_{frame:04d}.obj';ply=out/f'{args.scene}_{frame:04d}.ply';source=ROOT/'cache'/args.scene
  obj=export_mesh(source/f'{frame:04d}.mesh.gz',mesh,manifest['config']['extent']);primary=export_primary(source/f'{frame:04d}.particles',ply,manifest['frames'][frame]['particles'])
  loaded=trimesh.load(mesh,process=False);points=trimesh.load(ply,process=False);assert len(loaded.vertices)==obj['vertices'];assert len(loaded.faces)==obj['triangles'];assert len(points.vertices)==primary['particles']
  expected,*_=mesh_data(source/f'{frame:04d}.mesh.gz',manifest['config']['extent']);error=float(np.max(np.abs(loaded.vertices-expected)));assert error<1e-7
  raw=np.fromfile(source/f'{frame:04d}.particles','<f4');assert np.max(np.abs(points.vertices-raw[:len(points.vertices)*3].reshape(-1,3)))<1e-7
  report['objPly'].append({'frame':frame,'passed':True,'independentReader':'trimesh '+trimesh.__version__,'meshMaxCoordinateError':error,'mesh':obj,'primary':primary})
 (ROOT/'tests/exports-iii.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
