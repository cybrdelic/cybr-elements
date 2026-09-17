from pathlib import Path
p=Path('work/render_cybrdelic.py')
s=p.read_text()
a=s.index('from intro_motion import p as letter_points');b=s.index('def render(frame):',a)
s=s[:a]+s[b:]
s=s.replace("'cybrdelic-firebending-intro.mp4'","'cybrdelic-fire-only.mp4'").replace("ROOT/'intro-frames'","ROOT/'fire-only-frames'")
s=s.replace('    plate=name_plate(frame/FPS)\n    pixels=(np.clip(1-(1-rgb)*(1-plate),0,1)*255).astype(np.uint8)', '''    screen_z=4.2-(np.arange(H)-120)/768*4.2
    falloff=np.clip((3.8-screen_z)/.7,0,1)
    falloff=falloff*falloff*(3-2*falloff)
    pixels=(np.clip(rgb*falloff[:,None,None],0,1)*255).astype(np.uint8)''')
s=s.replace("'cybrdelic-report.json'","'fire-only-report.json'")
p.write_text(s)
q=Path('work/review_cybrdelic.py').read_text().replace('cybrdelic-firebending-intro.mp4','cybrdelic-fire-only.mp4').replace('cybrdelic-review.jpg','fire-only-review.jpg').replace('cybrdelic-verification.json','fire-only-verification.json')
Path('work/review_fire_only.py').write_text(q)
print('Removed wordmark compositing; preserved fire choreography and optical finish.')
