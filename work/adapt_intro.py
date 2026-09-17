from pathlib import Path
p=Path('work/render_cybrdelic.py')
s=p.read_text().replace('from trail_motion import','from intro_motion import')
s=s.replace("out = ROOT/'trail-frames'","out = ROOT/'intro-frames'")
s=s.replace("-3. if MODE=='word' else -.6",'-.6').replace("6. if MODE=='word' else 1.2",'1.2')
s=s.replace("    if MODE=='word':nozzle=torch.exp(-((px/.080)**2+((y+2.)/.100)**2+(pz/.080)**2)*1.5)\n",'')
a=s.index("    if MODE=='arc':",s.index('def step('));b=s.index('    activation=',a)
s=s[:a]+'''    v[0].lerp_(-float(dx)*3.5+shear*float(-dz),inject)
    v[1].lerp_(torch.sin(px*38+pz*27+t*23)*.8,inject)
    v[2].lerp_(-float(dz)*3.5+shear*float(dx),inject)
'''+s[b:]
s=s.replace("(float(nozzle_turn(t))*dt if MODE=='arc' else 0.)",'(float(nozzle_turn(t))*dt)')
a=s.index("    if MODE=='word':",s.index('# Turn the hot gas'));b=s.index('    # Resolved vorticity confinement',a)
s=s[:a]+s[b:]
s=s.replace("('fire-trail-study.mp4' if MODE=='arc' else 'cybrdelic-fire-trail.mp4')","'cybrdelic-firebending-intro.mp4'")
s=s.replace("'trail-report.json'","'cybrdelic-report.json'")
s=s.replace("DURATION=float(os.environ.get('INTRO_SECONDS','6.0'))","DURATION=float(os.environ.get('INTRO_SECONDS','6.5'))")
s=s.replace('def render(frame):','''from intro_motion import p as letter_points, on as letter_on, distance as letter_distance, length as letter_length
from PIL import ImageFilter

def name_plate(t):
    # The moving nozzle writes a quiet, solid closing mark behind the transient flame.
    q=np.clip((t-START-.16)/WRITE,0,1)*letter_length
    pts=np.c_[(letter_points[:,0]+5.25)/10.5*1920,120+(4.2-letter_points[:,1])/4.2*768]
    mask=Image.new('L',(W,H));draw=ImageDraw.Draw(mask)
    active=(letter_distance<=q)&(letter_on>.5)
    indices=np.flatnonzero(np.diff(np.r_[False,active,False]))
    for a,b in indices.reshape(-1,2):
        if b-a>1:draw.line([tuple(v) for v in pts[a:b]],fill=255,width=6,joint='curve')
    ink=np.asarray(mask,dtype=np.float32)/255
    fade=min(1,max(0,(DURATION-t)/.5))
    return ink[:,:,None]*np.array([.76,.71,.65])*fade

def render(frame):''')
s=s.replace("    pixels=(im[0].permute(1,2,0)*255).byte().cpu().numpy()", "    rgb=im[0].permute(1,2,0).cpu().numpy()\n    plate=name_plate(frame/FPS)\n    pixels=(np.clip(1-(1-rgb)*(1-plate),0,1)*255).astype(np.uint8)")
s=s.replace("'no trail fitting, morph or cached particles.'","'no trail fitting, morph or cached particles; a separate non-burning closing mark is progressively revealed.'")
p.write_text(s)
print('Created faithful moving-nozzle word render with a persistent closing mark.')
