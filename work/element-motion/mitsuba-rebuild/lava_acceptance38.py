"""Evidence gate for lava publication. Numerical success is not visual success."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np


def hot_origin(folder):
    """Verify the initial cache and every continuation link, not just flags."""
    seen=set()
    for _ in range(32):
        folder=Path(folder).resolve()
        if folder in seen:return False
        seen.add(folder)
        proof_path=folder/'proof.json'
        if not proof_path.exists() and folder.name.startswith('frame-'):
            folder=folder.parent;proof_path=folder/'proof.json'
        if not proof_path.exists():return False
        proof=json.loads(proof_path.read_text())
        if any(proof.get(k) is not False for k in ('preparedSkin','authoredFragments','seededDamage')):return False
        parent=proof.get('source')
        if not parent:
            initial=folder/'frame-00000/state.npz'
            if not initial.exists():return False
            with np.load(initial) as s:
                return bool(float(s['time'])==0 and np.all(s['damage']==0)
                            and not s['bond_broken'].any() and not s['bond_frozen'].any()
                            and np.max(abs(s['temperature']-proof['initialTemperatureK']))<1e-7)
        path=Path(parent['path']);path=path if path.is_file() else path/'state.npz'
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=parent['sha256']:return False
        folder=path.parent
    return False


def audit(folder):
    folder=Path(folder);p=folder/'state.npz';s=dict(np.load(p));meta=json.loads((folder/'state.json').read_text())
    proof=json.loads((folder/'proof.json').read_text()) if (folder/'proof.json').exists() else {}
    finite=all(np.isfinite(s[k]).all() for k in ['x','v','temperature','damage','volume'])
    complete=proof.get('status')=='complete'
    same_time=abs(float(s['time'])-meta['time'])<1e-10
    mass_error=abs(float(s['mass'].sum())-meta['initial_mass']-meta['ledger'].get('source_mass',0.)+meta['ledger'].get('dust_mass_out',0.))
    rows=meta['rows'];thermal=max((r.get('thermalBalanceRelative',float('inf')) for r in rows),default=float('inf'))
    mechanical=max((r.get('mechanicalResidual',float('inf')) for r in rows),default=float('inf'))
    bed=meta.get('driver_state',{}).get('bed')
    bed_ok=bed is None or abs(bed['time']-meta['time'])<1e-9
    if bed is not None:
        stored=float(np.sum((np.asarray(bed['temperature'])-293.15)*(2800*850*bed['dx']**3)))
        bed_ok=bed_ok and abs(stored+bed['bottom_loss']-bed['received'])<1e-6*max(abs(bed['received']),1)
    numerics=finite and same_time and bed_ok and thermal<1e-6 and mechanical<1e-5 and mass_error<1e-9*max(meta['initial_mass'],1e-9)
    physical=complete and numerics
    driver=meta.get('driver_state',{});records=driver.get('temporalRecords',[])
    temporal=driver.get('adaptiveFromTime')==0 and bool(records)
    covered=0.
    for record in records:
        temporal=temporal and abs(record['time']-covered-record['dt'])<1e-8 and max(record['errors'].values())<=1
        covered=record['time']
    temporal=temporal and abs(covered-meta['time'])<1e-8
    born=hot_origin(folder)
    fracture=False;opening=0.
    if np.any(s['bond_broken'] & s['bond_frozen'][s['bond_edges']].all(1)):
        from lava_mpm_material_surface import reconstruct
        _,measured=reconstruct(s,np.asarray(meta['sample_size']),measure_cracks_only=True)
        opening=measured['maximumOpeningM'];fracture=measured['openFacePairs']>0 and opening>1e-8
    sha=hashlib.sha256(p.read_bytes()).hexdigest()
    review_path=folder/'visual-review.json';review=json.loads(review_path.read_text()) if review_path.exists() else {}
    visual=review.get('stateSha256')==sha and review.get('accepted') is True and bool(review.get('evidenceImages'))
    visual=visual and all(review.get(k) is True for k in ('geometryAccepted','motionAccepted','resolutionChecked'))
    report=dict(stateSha256=sha,time=meta['time'],physicalChecks=physical,acceptedStateNumerics=numerics,requestedIntervalComplete=complete,substrateChecks=bed_ok,temporalChecks=temporal,formedFromHotMaterial=born,openFracture=fracture,maximumOpeningM=opening,visualReview=visual,
        publishable=physical and born and temporal and fracture and visual,
        thermalResidual=thermal,mechanicalResidual=mechanical,massErrorKg=mass_error,
        nextGate='Fix physical failure' if not numerics else 'Complete declared simulation interval' if not complete else 'Verify hot-state ancestry' if not born else 'Complete temporal error checks' if not temporal else 'Demonstrate actual open fracture' if not fracture else 'Review fixed-view geometry and motion',
        rule='A new cache invalidates the prior visual review. Passing numerical checks never authorizes publication by itself.')
    (folder/'acceptance.json').write_text(json.dumps(report,indent=2));return report


def require_publishable(folder):
    report=audit(folder)
    if not report['publishable']:raise RuntimeError('Lava publication blocked: '+report['nextGate'])
    return report


def publish(folder,image,destination):
    # The workflow copies no final media until the exact cached state passes
    # physical, geometric and visual checks. No force/skip option exists.
    require_publishable(folder)
    folder=Path(folder);image=Path(image);review=json.loads((folder/'visual-review.json').read_text())
    digest=hashlib.sha256(image.read_bytes()).hexdigest()
    if not any(item.get('sha256')==digest for item in review['evidenceImages']):
        raise ValueError('Publication image was not included in the visual review')
    import shutil
    shutil.copyfile(image,Path(destination))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--require',action='store_true');a=p.parse_args()
    print(json.dumps(require_publishable(a.folder) if a.require else audit(a.folder)))
