from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'sigil_02_lightning_v2.py').read_text().replace('lightning-v2','lightning-v3').replace('lightning-02-v2','lightning-02-v3').replace('lightning-report-v2','lightning-report-v3')
s=s.replace("exec(aero,ns)\nif '--pilot'", "exec(aero,ns)\nrender=fn('render').replace('if aerosol:linear+=scatter[:,:,None]*np.array([.26,.31,.43],np.float32)','if aerosol:linear+=scatter[:,:,None]*np.array([.26,.31,.43],np.float32)*.12')\nexec(render,ns)\nif '--pilot'")
(R/'sigil_02_lightning_v3.py').write_text(s);compile(s,'lightning-v3','exec');print('Reduced aerosol scattering without changing conductor energy or branching.')
