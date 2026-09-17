from pathlib import Path
p=Path('work/render_sans_fire.py').read_text().replace('from sans_motion import','from handprint_motion import').replace('sans-fire','handprint-fire')
Path('work/render_handprint_fire.py').write_text(p)
p=Path('work/render_water_sans.py').read_text().replace('import sans_motion as font','import handprint_motion as font').replace('water-sans','water-handprint').replace('water-pilot','water-handprint-pilot')
Path('work/render_water_handprint.py').write_text(p)
p=Path('work/review_sans_fire.py').read_text().replace('sans-fire','handprint-fire').replace('sans-burnout','handprint-burnout').replace('render_sans_fire','render_handprint_fire')
Path('work/review_handprint_fire.py').write_text(p)
p=Path('work/finish_water_video.py').read_text().replace('water-sans','water-handprint').replace('sans-water','handprint-water').replace('sans_motion','handprint_motion').replace('water-sequence-review','water-handprint-review').replace('water-release-review','water-handprint-release-review')
Path('work/finish_water_handprint.py').write_text(p)
