from pathlib import Path
r=Path(__file__).resolve().parent
s=(r/'sigil_02_water_hold_optics_render.py').read_text()
s=s.replace('optics-pilot','cool-pilot').replace('visible_transmission=False','visible_transmission=True')
s=s.replace('light.color=(.64,.83,1.0)','light.color=(.18,.52,1.0)')
s=s.replace('frames=[75,165]','frames=[165]')
(r/'sigil_02_water_hold_cool_render.py').write_text(s)
print('One-frame cool illumination comparison ready')
