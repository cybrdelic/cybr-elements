"""Cheap CPU preflight before expensive lava optics. Tests are not final shots."""
import hashlib,json
from pathlib import Path
import numpy as np


def inspect_surface(path):
    path=Path(path);receipt=json.loads(path.with_suffix('.json').read_text());folder=path.parent
    state_path=Path(receipt['source']);meta=json.loads((folder/'state.json').read_text())
    s=np.load(state_path);top=s['rest'][:,2]>np.quantile(s['rest'][:,2],.75)
    damaged=s['damage']>.1
    top_damage=float((damaged&top).sum()/max(1,damaged.sum()))
    setup_path=folder/'setup.json';setup=json.loads(setup_path.read_text()) if setup_path.exists() else {}
    description=str(setup.get('load',setup.get('description',''))).lower()
    validation=bool(setup.get('prescribedCracks',False) or 'validation' in description or 'specimen' in description or 'test' in description)
    from lava_mpm import ROOT,SOURCE_HASHES
    temporal_path=ROOT/'validation/upper_crust_timestep.json'
    temporal=json.loads(temporal_path.read_text()) if temporal_path.exists() else {}
    revised=meta['material'].get('fracture_model')=='phase_field'
    production_path=ROOT/'rebuild-24/production-validation.json'
    production=json.loads(production_path.read_text()) if production_path.exists() else {}
    validation_current=production.get('sourceHashes')==SOURCE_HASHES
    solved_current=meta.get('sourceHashes')==SOURCE_HASHES
    configuration=dict(material=meta['material'],contact_solver=meta.get('contact_solver','dense'),transfer=meta.get('transfer','apic'),transfer_filter_seconds=meta.get('transfer_filter_seconds',.001))
    checks=dict(currentSource=hashlib.sha256(state_path.read_bytes()).hexdigest()==receipt['sourceSha256'],
        topology=receipt.get('fractureTopologyPreserved',False),
        openFractures=receipt.get('openFacePairs',0)>0 and receipt.get('crackWallTriangles',0)>0,
        volume=receipt.get('relativeVolumeDifference',1)<.02 and receipt.get('cellVolumeRelativeErrorP95',1)<.1,
        upperCrust=top_damage>.5,
        horizontalResolution=max(meta.get('cell_size',[meta['dx']]*3)[:2])<=.00101,
        noInversion=receipt.get('minimumCellVolumeM3',0)>0,
        resolvedDeformation=receipt.get('maximumDeformationCondition',float('inf'))<8,
        productionScene=setup.get('sceneKind')=='natural_lava_flow' and not validation,
        fractureTimestepConvergence=(production.get('fullFractureTemporal',{}).get('status')=='pass' and validation_current) if revised else temporal.get('status')=='pass',
        currentSolver=solved_current,
        validatedConfiguration=production.get('configuration')==configuration,
        materialCalibration=production.get('materialCalibration',{}).get('status')=='pass' and validation_current if revised else False,
        spatialFractureConvergence=production.get('fullFractureSpatial',{}).get('status')=='pass' and validation_current if revised else False,
        naturalFlowBreakup=production.get('naturalFlow',{}).get('status')=='pass' and validation_current if revised else False)
    report=dict(status='pass' if all(checks.values()) else 'blocked',checks=checks,
        upperShareOfDamagedParticles=top_damage,
        message='Geometric preflight only; passing still requires visual and motion review. Controlled fracture coupons are diagnostic-only.',
        source=str(path))
    path.with_name(path.stem+'-render-gate.json').write_text(json.dumps(report,indent=2))
    return report
