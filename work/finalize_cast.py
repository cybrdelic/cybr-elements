from pathlib import Path
p=Path('work/render_cast.py');s=p.read_text()
s=s.replace("ROOT/'cast-frames'","ROOT/'cast-final-frames'")
s=s.replace("    pixels=(np.clip(rgb*falloff[:,None,None],0,1)*255).astype(np.uint8)","""    horizontal=np.minimum(np.arange(W),W-1-np.arange(W))/65
    horizontal=np.clip(horizontal,0,1);horizontal=horizontal*horizontal*(3-2*horizontal)
    closing=min(1,max(0,(TOTAL-1-frame)/(FPS*.55)))
    pixels=(np.clip(rgb*falloff[:,None,None]*horizontal[None,:,None]*closing,0,1)*255).astype(np.uint8)""")
p.write_text(s)
