from pathlib import Path
p=Path('work/brand-font/build_type.py').read_text()
extra='''# Complete printable Basic Latin coverage.
put('$',650,G['S'],S((313,786),(313,-53),w=58,flat=True))
put('%',750,translate(scale(oval(),xfact=.39,yfact=.52,origin=(0,0)),xoff=20,yoff=428),translate(scale(oval(),xfact=.39,yfact=.52,origin=(0,0)),xoff=432,yoff=20),S((111,50),(616,680),w=75,flat=True))
put('*',520,*[S((260,520),(260+190*math.sin(j*math.tau/5),520+190*math.cos(j*math.tau/5)),w=69,flat=True) for j in range(5)])
put('<',500,S((404,518),(82,280),(404,44),w=80,flat=True));put('>',500,scale(G['<'],xfact=-1,yfact=1,origin=(248,0)))
put('^',555,S((74,447),(277,694),(480,447),w=76,flat=True))
put('`',255,S((74,724),(172,600),w=76,flat=True))
put('|',245,S((120,780),(120,-130),w=76,flat=True))
put('~',625,S((75,299),(233,478,346,146,550,333),w=75,flat=True))
put('{',410,S((330,741),(203,741,180,706,180,559),(180,429,146,385,74,337),(145,293,180,250,180,121),(180,-42,203,-98,330,-98),w=79,flat=True));put('}',410,scale(G['{'],xfact=-1,yfact=1,origin=(202,0)))
'''
p=p.replace('# Layout and kerning shared',extra+'\n# Layout and kerning shared')
# Make the packaged generator resolve its output folder correctly too.
p=p.replace("ROOT=Path(__file__).resolve().parents[2]/'outputs'/'cybrdelic-type';ROOT.mkdir(exist_ok=True)","HERE=Path(__file__).resolve();ROOT=HERE.parent.parent if HERE.parent.name=='source' else HERE.parents[2]/'outputs'/'cybrdelic-type';ROOT.mkdir(exist_ok=True)")
p=p.replace("shutil.copy2(__file__,ROOT/'source'/'build_type.py')", "if Path(__file__).resolve()!=(ROOT/'source'/'build_type.py').resolve(): shutil.copy2(__file__,ROOT/'source'/'build_type.py')")
Path('work/brand-font/build_type.py').write_text(p)
