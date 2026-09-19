"""Bake the shallow-channel lava formation directly into renderable mesh frames."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from elements_core.lava_formation import PourFormationConfig, build_mold_mesh
from elements_core.lava_mpm import LavaConfig
from elements_core.lava_shallow import (
    ShallowLavaConfig, initialize, advance_state, build_surface_mesh, metrics,
)
from elements_core.runtime import RunIdentity, atomic_json, atomic_npz

R=Path(__file__).resolve().parent
DEFAULT_SOURCE=R/'sigil-02-v2/source.npz'


def ensure_source(path:Path)->Path:
    path=Path(path).resolve()
    if path.is_file():
        return path
    if path!=DEFAULT_SOURCE.resolve():
        raise FileNotFoundError(path)
    subprocess.run([sys.executable,str(R/'sigil_02_source.py'),'sigil-02-v2'],cwd=R,check=True)
    if not path.is_file():
        raise RuntimeError(f'failed to build {path}')
    return path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seconds',type=float,default=7.5)
    p.add_argument('--fps',type=int,default=12)
    p.add_argument('--nx',type=int,default=256)
    p.add_argument('--ny',type=int,default=128)
    p.add_argument('--pour-duration',type=float,default=4.15)
    p.add_argument('--target-depth',type=float,default=.041)
    a=p.parse_args()
    a.source=ensure_source(a.source)
    frames=round(a.seconds*a.fps)
    if frames<2 or abs(frames-a.seconds*a.fps)>1e-7:
        raise ValueError('seconds*fps must be an integer >=2')

    formation=PourFormationConfig(
        main_nozzles=7,
        nozzle_bottom=.105,
        inlet_speed=.34,
        inlet_stagger_scale=.55,
        tangent_speed=.055,
        initial_down_speed=.38,
        skin_temperature=1450.,
        core_temperature=1580.,
    )
    cfg=ShallowLavaConfig(nx=a.nx,ny=a.ny,pour_duration=a.pour_duration,target_depth=a.target_depth)
    state=initialize(a.source,formation,cfg)

    settings={
        'solver':'CPU conservative thermal shallow lava with yield + basal-slip closure',
        'config':cfg.manifest(),
        'fps':a.fps,'frames':frames,
        'floor':cfg.floor,
        'formationMode':'pour',
        'formation':formation.manifest(),
        'model':'capacity-balanced localized inlets + conservative pressure-driven channel flow + hot-bulk/cooling-skin rheology + wall-biased quench',
        'noTargetPositionForces':True,
        'noImageGeneration':True,
        'noFrameInterpolation':True,
    }
    inputs={
        'source':a.source,
        'entry':Path(__file__),
        'solver':R/'elements_core/lava_shallow.py',
        'formation':R/'elements_core/lava_formation.py',
    }
    run=RunIdentity(a.out,settings,inputs)
    (a.out/'meshes').mkdir(exist_ok=True)

    dummy=LavaConfig(floor=cfg.floor)
    mold_mesh,mold_report=build_mold_mesh(a.source,dummy,formation)
    with np.load(a.source,allow_pickle=False) as src:
        sdf=np.asarray(src['sdf'],np.float64)
        lo=np.asarray(src['lo'],np.float64)
        extent=np.asarray(src['extent'],np.float64)
    cell_x=extent[0]/(sdf.shape[1]-1)
    cell_y=extent[2]/(sdf.shape[0]-1)
    gy,gx=np.gradient(sdf,cell_y,cell_x)
    norm=np.maximum(np.hypot(gx,gy),1e-12)
    gx/=norm;gy/=norm
    atomic_npz(
        a.out/'mold.npz',
        **mold_mesh,
        sdf=sdf,gx=gx,gz=gy,lo=lo,extent=extent,
        stageScale=np.float64(formation.stage_scale),
        sourceCenterZ=np.float64(formation.source_center_z),
        wallTop=np.float64(cfg.floor+cfg.wall_height),
        margin=np.float64(min(cfg.dx,cfg.dy)*.22),
        friction=np.float64(.46),
    )
    run.receipt('mold',[a.out/'mold.npz'],kind='rigid glyph cavity')

    source_report=[]
    for src in state['sources']:
        source_report.append({k:v for k,v in src.items() if k!='shape'})
    atomic_json(a.out/'formation.json',{
        'mode':'depth-averaged pressure-driven cavity fill',
        'cavityAreaM2':state['cavityAreaM2'],
        'targetFillVolumeM3':state['targetVolumeM3'],
        'components':[{'label':int(k),'cells':int(v)} for k,v in state['components']],
        'inlets':source_report,
        'moldMesh':mold_report,
        'noTargetPositionForces':True,
        'noDistributedTargetSource':True,
        'boundaryModel':'signed-distance no-flux walls',
    })

    rows=[];wall=time.perf_counter();t=0.
    for f in range(frames):
        target=f/a.fps
        active=advance_state(state,t,target,cfg) if target>t else [
            i for i,s in enumerate(state['sources']) if s['start']<=target<s['end']
        ]
        t=target
        mesh=build_surface_mesh(
            state['h'],state['skin'],state['damage'],state['mask'],
            state['xs'],state['ys'],active,state['sources'],t,cfg,formation,
        )
        file=a.out/'meshes'/f'{f:04d}.npz'
        atomic_npz(file,**mesh,time=np.float64(t))
        row=metrics(state,t,cfg)
        row.update(frame=f,vertices=len(mesh['vertices']),triangles=len(mesh['faces']),
                   activeJets=len(active),wallSeconds=time.perf_counter()-wall)
        rows.append(row)
        atomic_json(a.out/'meshes'/f'{f:04d}.json',row)
        atomic_json(a.out/'metrics.json',rows)
        run.receipt(f'mesh-{f:04d}',[file],frame=f,time=t)
        print('SHALLOW_LAVA_FRAME',json.dumps(row),flush=True)

    atomic_json(a.out/'manifest.json',{
        'complete':True,'frames':frames,'fps':a.fps,
        'solver':settings['solver'],'settings':settings,
        'targetFillVolumeM3':state['targetVolumeM3'],
        'finalMetrics':rows[-1],
        'elapsedSeconds':time.perf_counter()-wall,
        'noImageGeneration':True,'noFrameInterpolation':True,
        'limits':[
            'depth-averaged non-Newtonian shallow-flow approximation',
            'surface-skin thermal model rather than resolved 3D crust thickness',
            'rigid mold; no two-way thermoelastic mold deformation',
        ],
    })


if __name__=='__main__':
    main()
