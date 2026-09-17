"""Export delivered CFR3/CFR4 reconstructed meshes and raw primary caches without hidden decimation.

OBJ sequences preserve changing topology. Complete PLY primary exports require
raw .particles caches regenerated with simulate.mjs; downloaded mesh caches
contain only a diagnostic particle sample, which is never mislabeled complete.
"""
from __future__ import annotations
import argparse,gzip,json,struct
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]

def export_mesh(source:Path,destination:Path,extent:list[float])->dict:
 data=gzip.decompress(source.read_bytes())
 if len(data)<32:raise ValueError('Truncated CFR3 header')
 magic,nv,nf,nd,nw,np_,cw,ch=struct.unpack_from('<8I',data)
 if magic not in (0x43465233,0x43465234):raise ValueError('Expected a CFR3/CFR4 reconstructed mesh')
 expected=32+nv*13+nf*12+nd*(10 if magic==0x43465234 else 6)+nw*24+np_*6+cw*ch*2
 if len(data)!=expected:raise ValueError('CFR3 byte length does not match its header')
 pos=np.frombuffer(data,'<u2',nv*3,32).reshape(-1,3).astype(np.float64)/65535*np.array(extent)
 normal=np.frombuffer(data,'<i2',nv*3,32+nv*6).reshape(-1,3).astype(np.float64)/32767
 index=np.frombuffer(data,'<u4',nf*3,32+nv*13).reshape(-1,3)
 if nf and int(index.max())>=nv:raise ValueError('Out-of-range mesh index')
 destination.parent.mkdir(parents=True,exist_ok=True)
 with destination.open('w') as out:
  out.write('# CYBR FLIP III: decoded surface, metres, no export decimation\no liquid\n')
  np.savetxt(out,pos,fmt='v %.9g %.9g %.9g');np.savetxt(out,normal,fmt='vn %.9g %.9g %.9g')
  for a,b,c in index.astype(np.int64)+1:out.write(f'f {a}//{a} {b}//{b} {c}//{c}\n')
 return {'vertices':nv,'triangles':nf,'path':str(destination)}

def export_primary(source:Path,destination:Path,particles:int)->dict:
 data=np.fromfile(source,'<f4')
 if data.size!=particles*6 or not np.isfinite(data).all():raise ValueError('Invalid raw primary state')
 p=data[:particles*3].reshape(-1,3);v=data[particles*3:].reshape(-1,3)
 destination.parent.mkdir(parents=True,exist_ok=True)
 with destination.open('w') as out:
  out.write(f'ply\nformat ascii 1.0\ncomment Complete CPU primary state, metres and metres/second\nelement vertex {particles}\n')
  for prop in ['x','y','z','vx','vy','vz']:out.write('property float '+prop+'\n')
  out.write('end_header\n');np.savetxt(out,np.concatenate([p,v],axis=1),fmt='%.9g')
 return {'particles':particles,'completePrimaryState':True,'path':str(destination)}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('scene');ap.add_argument('destination',type=Path);ap.add_argument('--start',type=int,default=0);ap.add_argument('--end',type=int);ap.add_argument('--primary-ply',action='store_true');args=ap.parse_args()
 directory=ROOT/'cache'/args.scene;manifest=json.loads((directory/'manifest.json').read_text());end=len(manifest['frames']) if args.end is None else args.end
 if not 0<=args.start<end<=len(manifest['frames']):ap.error('Invalid half-open frame range')
 records=[]
 for f in range(args.start,end):
  stem=f'{f:04d}';record=export_mesh(directory/(stem+'.mesh.gz'),args.destination/(stem+'.obj'),manifest['config']['extent'])
  if args.primary_ply:
   source=directory/(stem+'.particles')
   if not source.is_file():raise FileNotFoundError('Regenerate complete primary .particles caches before using --primary-ply. Mesh-cache diagnostic samples are not a substitute.')
   record['primary']=export_primary(source,args.destination/(stem+'.ply'),manifest['frames'][f]['particles'])
  records.append({'frame':f,'time':manifest['frames'][f]['time'],**record});print('EXPORTED',args.scene,stem,flush=True)
 (args.destination/'export-manifest.json').write_text(json.dumps({'scene':args.scene,'units':'metres','frameDt':manifest['frameDt'],'exports':records},indent=2))
if __name__=='__main__':main()
