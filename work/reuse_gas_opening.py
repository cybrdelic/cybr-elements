from pathlib import Path
p=Path('work/render_gas_hold.py');s=p.read_text()
s=s.replace('for frame in range(TOTAL):', '''# Preserve the already approved opening pixels while rebuilding its fluid state.
opening=subprocess.Popen(['ffmpeg','-v','error','-i',str(ROOT.parent/'outputs'/'cybrdelic-gas-trail.mp4'),'-frames:v','240','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
for frame in range(TOTAL):''')
s=s.replace('    render(frame)\n    if frame in', '''    if frame<240:
        pixels=opening.stdout.read(W*H*3)
        if len(pixels)!=W*H*3:raise RuntimeError('Opening decode incomplete')
        encoder.stdin.write(pixels)
        if frame%15==0:
            Image.fromarray(np.frombuffer(pixels,np.uint8).reshape(H,W,3)).resize((1280,720),Image.Resampling.LANCZOS).save(out/f'{frame:04}.jpg',quality=91)
        if frame==239 and opening.wait()!=0:raise RuntimeError('Opening decode failed')
    else:
        render(frame)
    if frame in''')
p.write_text(s)
print('Approved first 8 seconds reused exactly; simulation rebuilt for the extended live hold and physical burnout.')
