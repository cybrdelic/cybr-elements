"""Record the generated wood inventory/flux lineage in runtime manifests."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2]
LIVE=ROOT/'outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'
OBJECTS=LIVE/'pyro-gpu/objects'
def proof(path):
    data=path.read_bytes()
    if path.suffix=='.json':data=data.replace(b'\r\n',b'\n');path.write_bytes(data)
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
def main():
    for name,folder in [('cybr-tree','forest-tree'),('logs','logs'),('house','house'),('wood-sigil','wood-sigil')]:
        base=OBJECTS/folder;structure=base/'structure' if name=='cybr-tree' else base
        source=base/('wood-solid.rgba16.bin' if name=='cybr-tree' else 'solid.rgba16.bin')
        output=base/'flux-metadata.rgba32.bin';sidecar=output.with_suffix('.bin.json')
        stats=json.loads(sidecar.read_text());stats['sourceRuntimePath']=source.relative_to(LIVE).as_posix();stats['outputRuntimePath']=output.relative_to(LIVE).as_posix()
        if stats['sourceSha256']!=proof(source)['sha256'] or stats['sha256']!=proof(output)['sha256']:raise ValueError('Stale flux metadata '+name)
        sidecar.write_bytes((json.dumps(stats,indent=2)+'\n').encode())
        path=structure/'manifest.json';m=json.loads(path.read_text());m['fluxMetadata']=('../' if name=='cybr-tree' else '')+output.name
        m['fluxMetadataProof']=proof(output);m['fluxProvenance']={'sourceRuntimePath':stats['sourceRuntimePath'],'sourceSha256':stats['sourceSha256'],'dryMassModelKg':stats['dryMassModelKg'],'metadataSha256':stats['sha256']}
        if name=='cybr-tree':
            outer_path=base/'manifest.json';outer=json.loads(outer_path.read_text())
            for p in [source,output,sidecar]:outer['files'][p.name]=proof(p)
            outer['structureManifest']='structure/manifest.json';outer_path.write_bytes((json.dumps(outer,indent=2)+'\n').encode())
        else:
            for p in [source,output,sidecar]:m['files'][p.name]=proof(p)
        path.write_bytes((json.dumps(m,indent=2)+'\n').encode())
    print(json.dumps({'manifests':4,'fluxSourceHashesVerified':True,'jsonCanonicalLF':True}))
if __name__=='__main__':main()
