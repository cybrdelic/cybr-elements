"""Bake thermal lava either as a formed diagnostic or a gravity-fed glyph pour."""
from __future__ import annotations
import argparse,json,time,subprocess,sys
from pathlib import Path
from dataclasses import asdict
import numpy as np
from numba import set_num_threads
from elements_core.lava_mpm import LavaConfig,LavaMPM,sample_glyph
from elements_core.lava_formation import (PourFormationConfig,build_pour_initial_state,
                                          build_mold_mesh,advance_with_mold)
from elements_core.runtime import RunIdentity,atomic_json,atomic_npz,stage_status

R=Path(__file__).resolve().parent
DEFAULT_SOURCE=R/'sigil-02-v2/source.npz'

def ensure_source(path: Path) -> Path:
 path=Path(path).resolve()
 if path.is_file():return path
 if path != DEFAULT_SOURCE.resolve():raise FileNotFoundError(f'Missing lava source: {path}')
 builder=R/'sigil_02_source.py';artwork=R.parents[1]/'outputs/cybrdelic-type/exploration-v6/cybrdelic-brandmark-refined.png'
 if not builder.is_file() or not artwork.is_file():raise FileNotFoundError('Cannot rebuild default lava source')
 subprocess.run([sys.executable,str(builder),'sigil-02-v2'],cwd=R,check=True)
 if not path.is_file():raise RuntimeError(f'Source builder completed without {path}')
 return path

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--source',type=Path,default=DEFAULT_SOURCE);p.add_argument('--out',type=Path,required=True)
 p.add_argument('--formation',choices=['pour','formed'],default='pour')
 p.add_argument('--seconds',type=float,default=2.5);p.add_argument('--fps',type=int,default=24)
 p.add_argument('--samples-per-axis',type=int,default=2);p.add_argument('--threads',type=int,default=2)
 p.add_argument('--viscosity',type=float,default=92.);p.add_argument('--support-end',type=float,default=.62)
 a=p.parse_args();set_num_threads(a.threads);a.source=ensure_source(a.source)
 if a.formation=='pour':
  c=LavaConfig(spacing=.018,shape=(96,68,58),origin=(-.864,-.612,0.),melt_viscosity=a.viscosity,
               max_dt=.0007,support_start=-1.,support_end=-.5)
  formation=PourFormationConfig()
 else:
  c=LavaConfig(melt_viscosity=a.viscosity,support_end=a.support_end);formation=None
 n=round(a.seconds*a.fps)
 if n<2:raise ValueError('Need at least two physical frames')
 settings={'solver':'CPU quadratic APIC thermal Maxwell/J2 MPM','config':asdict(c),
           'fps':a.fps,'frames':n,'samplesPerAxis':a.samples_per_axis,'formationMode':a.formation,
           'formation':formation.manifest() if formation else None}
 inputs={'source':a.source,'entry':Path(__file__),'solver':R/'elements_core/lava_mpm.py'}
 if formation:inputs['formation']=R/'elements_core/lava_formation.py'
 run=RunIdentity(a.out,settings,inputs);(a.out/'particles').mkdir(exist_ok=True)
 if formation:
  pos,H,V,velocity,mold,formation_report=build_pour_initial_state(a.source,c,samples_per_axis=a.samples_per_axis,formation=formation)
  sim=LavaMPM(c,pos,H,V);sim.v[:]=velocity
  mold_mesh,mold_report=build_mold_mesh(a.source,c,formation)
  atomic_npz(a.out/'mold.npz',**mold_mesh)
  formation_report['moldMesh']=mold_report
  atomic_json(a.out/'formation.json',formation_report)
  run.receipt('mold',[a.out/'mold.npz'],kind='rigid basalt cavity')
 else:
  pos,H,V=sample_glyph(a.source,c,samples_per_axis=a.samples_per_axis);sim=LavaMPM(c,pos,H,V);mold=None;formation_report=None
 rows=[];start=time.perf_counter();stage_status(a.out,'simulation','running')
 print('PARTICLES',len(pos),'mass',sim.mass.sum(),'formation',a.formation,flush=True)
 try:
  for f in range(n):
   if f:
    row=advance_with_mold(sim,1/a.fps,mold) if mold is not None else sim.advance(1/a.fps)
   else:
    row=sim.metrics();row.update(moldContactCorrections=0,maxMoldCorrectionMeters=0.)
   row.update(frame=f,wallSeconds=time.perf_counter()-start)
   file=a.out/'particles'/f'{f:04d}.npz';atomic_npz(file,**sim.snapshot())
   run.receipt(f'particles-{f:04d}',[file],frame=f,time=sim.time)
   rows.append(row);atomic_json(a.out/'metrics.json',rows);print(json.dumps(row),flush=True)
  atomic_json(a.out/'manifest.json',{'complete':True,'config':asdict(c),'frames':n,'fps':a.fps,
    'identity':run.identity,'elapsedSeconds':time.perf_counter()-start,'solver':'thermal viscoelastic MPM',
    'formationMode':a.formation,'formation':formation_report,
    'modelLimits':['weakly compressible','uncalibrated material constants','J2 damage, not resolved fracture',
      'subgrid convection/radiation','rigid one-way signed-distance mold contact','no two-way surrounding gas']})
  stage_status(a.out,'simulation','complete')
 except BaseException as e:stage_status(a.out,'simulation','failed',error=str(e));raise
if __name__=='__main__':main()
