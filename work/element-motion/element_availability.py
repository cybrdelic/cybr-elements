"""Recipe input/backend preflight, not a claim of completed or calibrated films."""
import hashlib,json
from pathlib import Path
import numpy as np
import torch
from element_scenes import SCENES,ROOT

MOTION_INPUTS={'motion':(), 'shared_motion':('shared-trail.json',),
               'sigil_native_motion':('sigil-native/c-stroke.npz',)}


def recipe_availability(name,gesture_version='19',control='none',root=ROOT):
    spec=SCENES[name];root=Path(root);required=[];errors=[];warnings=[]
    if spec.motion:
        required.append(spec.motion+'.py');required.extend(MOTION_INPUTS[spec.motion])
    if spec.source_asset:required.append(spec.source_asset)
    if gesture_version.startswith('21'):required.append('bending_fire_choreography_v'+gesture_version+'.py')
    if gesture_version=='22b':required.append('bending_fire_moves_v22b.py')
    if control=='orbit':warnings.append('Legacy orbit flag has no active orbit policy in these recipes')
    if control=='choreographed' and not gesture_version.startswith('21'):
        warnings.append('Choreographed steering is inactive unless gesture21/21b is selected')
    missing=[p for p in required if not (root/p).is_file()]
    # Check actual data contracts without allocating a simulation grid.
    try:
        if spec.motion=='shared_motion' and 'shared-trail.json' not in missing:
            data=json.loads((root/'shared-trail.json').read_text());frames=data['frames']
            if not frames or data['sampleRate']<=0:raise ValueError('Invalid shared trail sampling')
            for row in frames:
                values=[*row['p'],*row['d'],row['on'],row['speed'],row['turn']]
                if len(row['p'])!=2 or len(row['d'])!=2 or not np.isfinite(values).all():raise ValueError('Invalid shared trail sample')
        if spec.motion=='sigil_native_motion' and 'sigil-native/c-stroke.npz' not in missing:
            with np.load(root/'sigil-native/c-stroke.npz',allow_pickle=False) as data:
                p,t=data['points'],data['times']
                if p.ndim!=2 or p.shape[1]!=2 or t.shape!=(len(p),) or len(t)<3 or not np.isfinite(p).all() or not np.isfinite(t).all() or not (np.diff(t)>0).all():raise ValueError('Invalid original stroke points/times')
        if spec.source_asset and spec.source_asset not in missing:
            with np.load(root/spec.source_asset,allow_pickle=False) as data:
                for field in ('support','arrival','dirx','dirz','sdf'):
                    if data[field].shape!=(504,896) or data[field].dtype!=np.float32 or not np.isfinite(data[field]).all():raise ValueError('Original full-grid source contract mismatch: '+field)
    except (ValueError,KeyError,TypeError,OSError) as error:errors.append(str(error))
    ready=not missing and not errors;grid=[896,56,504] if spec.source_asset else [128,80,160]
    return dict(recipe=name,status='inputs_ready_execution_unqualified' if ready else 'missing_or_invalid_inputs',
        inputs_ready=ready,missing=missing,data_errors=errors,warnings=warnings,
        source_sha256={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in required if p not in missing},
        cpu_supported=True,cpu_resource_feasibility='Requires an actual run; input readiness is not full-grid memory qualification',
        cuda_available=torch.cuda.is_available(),cuda_parity_verified=False,
        native_grid=grid,state_tensor_bytes=int(np.prod(grid))*8*4,
        state_memory_note='State tensor only, not total solver/FFT/renderer memory',
        review_gate_frame=spec.review_gate,film_complete=False)


def all_recipes():
    return [recipe_availability(name) for name in SCENES]


if __name__=='__main__':print(json.dumps(all_recipes(),indent=2))
