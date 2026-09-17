from pathlib import Path
s=Path('work/render_gas.py').read_text().replace('FPS=30','FPS=15').replace('W,H=1920,1080','W,H=1280,720')
s=s.replace("ROOT/'gas-preview-frames'","ROOT/'gas-pilot-frames'").replace("ROOT.parent/'outputs'/'cybrdelic-gas-trail.mp4'","ROOT/'gas-pilot.mp4'")
Path('work/render_gas_pilot.py').write_text(s)
