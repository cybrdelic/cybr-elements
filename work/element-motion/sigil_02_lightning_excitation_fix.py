from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'sigil_02_lightning_v3.py').read_text().replace('lightning-v3','lightning-v4').replace('lightning-02-v3','lightning-02-v4').replace('lightning-report-v3','lightning-report-v4')
patch='''aero=aero.replace("p=net['points'][net['trunk']];coords=", "p=net['points'][net['trunk'] & (net['arrival'] <= (f+1)/30)]\\n            if not len(p):continue\\n            coords=")
aero=aero.replace('densitylight=self.rho*(light+.005)','densitylight=self.rho*light')
exec(aero,ns)'''
s=s.replace('exec(aero,ns)',patch).replace('if f==160:','if f==75:')
(R/'sigil_02_lightning_v4.py').write_text(s);compile(s,'lightning-v4','exec');print('Aerosol lighting now follows only the excited channels; eliminated premature ghost of unlit strokes.')
