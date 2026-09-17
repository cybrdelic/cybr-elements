from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'sigil_02_repair_water_render.py').read_text()
s=s.replace("cache=R/'sigil-02-repair/water-mesh'","cache=R/'sigil-02-water-hold/mesh'")
s=s.replace('sigil-02-repair/water-frames','sigil-02-water-hold/frames').replace('sigil-02-repair/water-pilot','sigil-02-water-hold/pilot')
s=s.replace('range(192)','range(300)').replace('[24,45,66,87]','[45,75,120,165]')
s=s.replace("s.cycles.samples=96 if '--full' in sys.argv else 24","s.cycles.samples=96 if '--full' in sys.argv else 24")
s=s.replace("for light in bpy.data.lights:light.energy*=.65","for light in bpy.data.lights:light.energy*=.44")
s=s.replace("bg.inputs['Strength'].default_value=.30","bg.inputs['Strength'].default_value=.24")
s=s[:s.index(' if f==135:')]+"print('COMPLETE',flush=True)\n"
# A preview render keeps four mesh caches. The full render consumes them after
# the chosen pilot passes, so no fluid resimulation is needed.
s=s.replace(' if True:\n  vectors.close()'," if '--full' in args:\n  vectors.close()")
(R/'sigil_02_water_hold_render.py').write_text(s)
print('CPU pilot and full renderer prepared.')
