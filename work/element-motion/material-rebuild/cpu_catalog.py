"""Material identities and bounded CPU proof recipes."""
from pathlib import Path
import json
R=Path(__file__).resolve().parent
ROWS=[
 ('lava','render_liquid_materials.py','thermal liquid','Viscous interior and connected cooling skin','Crust folds under compression and tears under tension','One-way thermal carrier; viscosity feedback still needs a new coupled solve'),
 ('ice','render_ice_body.py','phase change','Coherent clear ice with internal fracture surfaces','Solid regions retain shape before stress-driven breakup','Whole-body freeze transition is a rejected limitation pending progressive phase solve'),
 ('foam','render_liquid_materials.py','wet foam','Liquid-bearing connected cell structure','Surface attachment, cell packing, drainage and rupture','Carrier attachment exists; explicit shared films and drainage are incomplete'),
 ('metal','render_solids.py','plastic shell','Substantial brushed steel strip','Continuous thickness, localized folds and retained deformation','Cached deformation needs an independent yield and springback check'),
 ('glass','render_constructed.py','brittle dielectric','Thin clear glass with physical edges','Closed thickness, dark transparent faces, irregular fracture','Optical fill and prefracture appearance require visual review'),
 ('crystal','render_minerals.py','mineral clusters','Intergrown quartz-like clusters','Persistent growth structure and plausible optical depth','Growth geometry retained; no new crystal-growth solver'),
 ('sand','render_solids.py','frictional grains','Dense dry mineral sand','Packing, shear and nonelastic release','Render children inherit continuum deformation; no separate child-grain solve'),
 ('snow','render_solids.py','cohesive grains','Slightly cohesive powder snow','Compaction, irregular aggregates and fracture-born powder','Cached MPM response must be compared with material test'),
 ('mud','render_solids.py','yield fluid','Dense gritty wet mud','Slump under load, folds and restrained wet reflections','Existing viscous carrier lacks verified yield-stress response'),
 ('blood','render_solids.py','absorbing liquid','Dense red liquid with thin transmitting edges','Thickness-dependent absorption and coherent breakup','Existing carrier lacks independently calibrated rheology'),
 ('plants','render_constructed.py','branched rods','Connected living plant','Tapered stems, sound attachments, leaf lag and unfurling','Scanned leaves do not replace a botanical attachment audit'),
 ('healing','render_healing.py','fictional repair','A damaged original sigil restored by a traveling front','Actual gaps close behind a localized treatment','Designed fictional restoration, not a medical model'),
 ('lightning','lightning.py','discharge','Intermittent branched electrical discharge','Leader, bright stroke, selective restrikes and dark intervals','Authored slow-motion discharge; not calibrated electromagnetics'),
 ('lightning-redirection','lightning.py','discharge transfer','A continuous incoming-guided-outgoing event','Readable transfer through the source trajectory','Authored routing and temporal scale'),
 ('combustion','render_combustion.py','reactive gas','Concentrated jet and localized expanding burst','Distinct reaction, temperature, soot and pressure response','Current cache has a restrained burst; lighting alone cannot enlarge its physics'),
 ('spirit','render_channels.py','fictional conversion','Agitated structure becoming ordered behind a front','A readable local change in topology and motion','Art-directed fictional field'),
 ('energy','render_channels.py','fictional exchange','Two interacting directed energy flows','Intensity transfers locally rather than illuminating everything uniformly','Art-directed fictional field'),
 ('spirit-projection','render_projection.py','fictional separation','Original sigil retaining identity through separation','Coherent silhouette, depth and progressive detachment','Luminous membrane is a design interpretation'),
 ('sound','render_witness.py','air oscillation','Compression waves revealed by fine suspended matter','Traveling compressions and interference, no static diagram rings','Amplified slow-motion witness'),
 ('pressure','render_witness.py','air pressure','Moving inward pull and rebound','Cavity formation, inward acceleration and release','Reduced pressure-force witness'),
 ('heat','render_heat_witness.py','thermal optics','Cooling matter revealing transported heat','Radiation changes with temperature and gradients weaken','Visible witness, not self-luminous unlit air'),
 ('flight','render_channels.py','wake','Coherent air displacement and lift wake','Counter-rotating structure and velocity-dependent fine tracers','One-way integrated tracer wake'),
 ('seismic','render_minerals.py','elastic solid','Impulse traveling through a connected mineral structure','Source, propagation and boundary response remain readable','Reduced elastic-wave witness, not tomography')]
def catalog():
 return [{'id':k,'script':s,'family':f,'identity':i,'acceptance':a,'limitation':l,'engine':'numpy' if k=='combustion' else 'blender','frame':52 if k in ['combustion','healing'] else 65 if k=='ice' else 45} for k,s,f,i,a,l in ROWS]
if __name__=='__main__':
 out=R/'cpu';out.mkdir(exist_ok=True);(out/'catalog.json').write_text(json.dumps(catalog(),indent=2));print('CPU recipes',len(ROWS))
