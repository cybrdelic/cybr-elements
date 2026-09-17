from pathlib import Path
p=Path('work/render_gas_hold.py').read_text()
p=p.replace('from gesture_motion import','from font_motion import').replace('gas-hold','script-fire')
a=p.index('# Preserve the already approved opening pixels')
b=p.index('for frame in range(TOTAL):',a)
p=p[:a]+p[b:]
a=p.index('    if frame<240:');b=p.index('    if frame in [239,329,TOTAL-1]:',a)
p=p[:a]+'    render(frame)\n'+p[b:]
Path('work/render_script_fire.py').write_text(p)
q=Path('work/review_gas_hold.py').read_text().replace('gas-hold','script-fire').replace('gas-burnout','script-burnout').replace('render_gas_hold','render_script_fire')
q=q.replace('contact([7.6,8.5,9.5,10.7,11.3,12.,13.,14.]', 'contact([1.5,3.,4.5,6.,8.,10.7,11.7,13.]')
Path('work/review_script_fire.py').write_text(q)
