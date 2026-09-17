"""Continue an actual flow cache after its prescribed inlet pulse ends."""
import json,hashlib,shutil
from lava_mpm import MPM,ROOT
from lava_mpm_fed_run import save
from lava_mpm_continuous import main

name='continuous-21-cooling';folder=ROOT/name
if not (folder/'state.npz').exists():
    source=ROOT/'continuous-21';s=MPM.load(source);setup=json.loads((source/'inlet.json').read_text())
    setup['inletShutoffTime']=s.time;setup['config']['peak_speed']=0.;setup['nextEmission']=1.e12
    setup['parent']=dict(path=str(source/'state.npz'),sha256=hashlib.sha256((source/'state.npz').read_bytes()).hexdigest(),physicalTime=s.time)
    setup['description']='Continuous-21 molten inlet pulse ends at its cached physical time. The existing mass, heat, velocity and fracture state continue in the full MPM/thermal solve with zero inlet velocity. No artificial cooling, motion targets, pore cuts, or added cracks.'
    folder.mkdir(exist_ok=True);shutil.copy2(source/'source-history.json',folder/'source-history.json');save(s,folder,setup)
main(name,8,105,.12,.0005)
