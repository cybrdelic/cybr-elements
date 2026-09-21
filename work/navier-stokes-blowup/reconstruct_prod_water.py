#!/usr/bin/env python3
"""Production-detail reconstruction for the Navier-Stokes CYBR water scene.

This deliberately reuses the same detail-preserving reconstruction family as
the accepted CYBR bending-water pipeline: anisotropic PCA kernels, persistent
isolated-particle classification, volume-calibrated surface extraction,
mass-carrying detached droplets, and native surface motion vectors.

No image generation is involved.
"""
from __future__ import annotations
import argparse, json, sys, os, struct
from pathlib import Path
import numpy as np

for name in ["OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","NUMBA_NUM_THREADS"]:
    os.environ.setdefault(name,"2")

ROOT=Path(__file__).resolve().parents[2]
TOOLS=ROOT/"work/flip-lettering/vendor/tools"
sys.path.insert(0,str(TOOLS))
sys.path.insert(0,str(ROOT/"work/element-motion"))

from scipy.spatial import cKDTree
from bending_surface import DetailReconstruction
from bending_spray_v5 import Spray


def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    return p.parse_args()


def main():
    a=parse_args()
    src=a.input.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((src/"manifest.json").read_text())
    config=dict(manifest["config"])
    h=float(config["h"])
    extent=np.asarray(config["extent"],np.float32)

    # These are the accepted high-detail bending-water reconstruction controls.
    config["surfaceOptions"]={
        "spacingFactor":.43,
        "kernelRadiusFactor":1.48,
        "fieldSigma":.68,
        "meshSmoothingPasses":12,
        "temporalBlend":0,
        "shapeHistoryWeight":0,
        "geometricVolumeRecovery":False,
    }

    rec=DetailReconstruction(config)
    spray=Spray(h,capacity=config.get("maxParticles",520000))
    rows=[]

    for info in manifest["frames"]:
        f=int(info["frame"]);n=int(info["particles"])
        raw=np.fromfile(src/f"{f:04d}.particles",dtype="<f4")
        if raw.size!=n*6:
            raise ValueError(f"primary cache length mismatch frame {f}: {raw.size} vs {n*6}")
        p=raw[:n*3].reshape(-1,3)
        v=raw[n*3:].reshape(-1,3)
        shape=np.fromfile(src/f"{f:04d}.shape",dtype="<f4").reshape(n,6)

        field,vel,verts,normals,faces,drops,radii,dv,iso,measure=rec.reconstruct(
            p,v,shape,info.get("colliders",config.get("obstacles",[])),manifest["frameDt"]
        )

        # Match the accepted bending-water spray closure rather than drawing
        # generic spheres from every sparse marker.
        drops,radii,dv,spray_stats=spray.step(
            p,v,rec.isolated,manifest["frameDt"],rec.droplet_clusters
        )
        measure.update(spray_stats)

        # Native motion vectors are interpolated from the real primary FLIP
        # velocity field, exactly as in bending-water-v5.
        if len(verts):
            tree=cKDTree(p)
            dist,ids=tree.query(verts,k=min(6,n),workers=2)
            if dist.ndim==1:
                dist=dist[:,None];ids=ids[:,None]
            weight=1/np.maximum(dist,h*.07)**2
            weight/=np.maximum(weight.sum(1)[:,None],1e-20)
            surface_v=np.einsum("nk,nkj->nj",weight,v[ids]).astype(np.float32)
        else:
            surface_v=np.empty((0,3),np.float32)

        if len(drops):
            drop_v=np.asarray(dv,np.float32)
        else:
            drops=np.empty((0,3),np.float32)
            radii=np.empty(0,np.float32)
            drop_v=np.empty((0,3),np.float32)

        represented_error=float(measure.get("totalRepresentedVolumeError",0))
        if abs(represented_error)>.03:
            raise RuntimeError(f"surface volume validation failed frame {f}: {represented_error}")

        positions=np.asarray(verts,np.float32)
        faces_i=np.asarray(faces,np.uint32)
        drops_f=np.asarray(drops,np.float32)
        radii_f=np.asarray(radii,np.float32)
        drop_v_f=np.asarray(drop_v,np.float32)
        np.savez_compressed(
            out/f"{f:04d}.npz",
            positions=positions,
            normals=np.asarray(normals,np.float32),
            faces=faces_i.astype(np.int32),
            surface_velocity=surface_v,
            drops=drops_f,
            radii=radii_f,
            drop_velocity=drop_v_f,
        )
        # Blender's distro build on CI does not ship NumPy.  Write a tiny
        # little-endian binary handoff so the actual renderer needs only the
        # Python standard library and bpy.
        with (out/f"{f:04d}.cwb").open("wb") as stream:
            stream.write(struct.pack("<4I",0x43594257,len(positions),len(faces_i),len(drops_f)))
            stream.write(positions.astype("<f4",copy=False).tobytes())
            stream.write(surface_v.astype("<f4",copy=False).tobytes())
            stream.write(faces_i.astype("<u4",copy=False).tobytes())
            stream.write(drops_f.astype("<f4",copy=False).tobytes())
            stream.write(radii_f.astype("<f4",copy=False).tobytes())
            stream.write(drop_v_f.astype("<f4",copy=False).tobytes())

        row={
            "frame":f,
            "vertices":int(len(verts)),
            "triangles":int(len(faces)),
            "drops":int(len(drops)),
            "surfaceVolumeRelativeError":represented_error,
            "maximumAxisRatio":float(measure.get("maximumAxisRatio",1)),
            "sprayFragments":int(measure.get("sprayFragments",0)),
            "coherentDrops":int(measure.get("coherentDrops",0)),
            "maximumWeber":float(measure.get("maximumWeber",0)),
            "maxSpeed":float(info["maxSpeed"]),
            "kineticEnergy":float(info["kineticEnergy"]),
            "tau":float(info["tau"]),
        }
        rows.append(row)
        print(json.dumps(row),flush=True)

    output={
        "source":str(src),
        "config":config,
        "frameDt":manifest["frameDt"],
        "frames":rows,
        "reconstruction":"CYBR bending-water v5 DetailReconstruction + Spray",
        "noImageGeneration":True,
    }
    (out/"manifest.json").write_text(json.dumps(output,indent=2))


if __name__=="__main__":
    main()
