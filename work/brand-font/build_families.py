"""Cybrdelic display families: original outline construction + artwork ligature."""
from pathlib import Path
import json, math, string, shutil, unicodedata, zipfile
import numpy as np
import cv2
from PIL import Image,ImageDraw,ImageFont
from shapely.geometry import Polygon,LineString,Point,MultiPolygon
from shapely.ops import unary_union
from shapely.ops import transform
from shapely.affinity import translate,scale
from shapely.geometry.polygon import orient
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont

ROOT=Path(__file__).resolve().parents[2]
PACKAGED=Path(__file__).parent.name=='source'
OUT=Path(__file__).resolve().parents[1] if PACKAGED else ROOT/'outputs/cybrdelic-fonts';OUT.mkdir(exist_ok=True)
for p in ['fonts','specimens','source','vector']:(OUT/p).mkdir(exist_ok=True)
BASE=(OUT/'source/base-construction.py' if PACKAGED else ROOT/'work/brand-font/build_type.py').read_text()
ART=OUT/'source/approved-studies.png' if PACKAGED else ROOT/'outputs/cybrdelic-type/exploration-v6/cybrdelic-brandmark-refined.png'
START=BASE.index('def path(');END=BASE.index('# Layout and kerning shared')
CONSTRUCTION=BASE[START:END]
BRUSH='''def stroke(p,w=102,flat=False):
    p=np.asarray(p,float)
    # Two authored pens: a curved asymmetric ribbon and an angular broad nib.
    if STYLE==2:
        p=np.asarray(LineString(p).simplify(20,preserve_topology=False).coords)
        nib=np.array([[-80,-28],[-23,-65],[80,28],[23,65]])*(w/102)
        parts=[]
        for a,b in zip(p[:-1],p[1:]):
            parts.append(MultiPoint(np.vstack((nib+a,nib+b))).convex_hull)
        g=unary_union(parts)
        # Chisel terminals with fine projecting corners.
        for a,b in [(p[0],p[min(1,len(p)-1)]),(p[-1],p[max(0,len(p)-2)])]:
            v=a-b;v=v/max(np.linalg.norm(v),1e-6)
            n=np.array([-v[1],v[0]])
            g=g.union(Polygon([a+n*53,a+v*83+n*20,a-n*53]))
        return g.buffer(0)
    # Variable width, tilted elliptical nib. Taper ends into hooked points.
    step=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    if step[-1]<1:return Point(p[0]).buffer(w/2)
    q=np.linspace(0,step[-1],max(5,int(step[-1]/13)))
    p=np.array([np.interp(q,step,p[:,j]) for j in range(2)]).T
    theta=np.linspace(0,2*math.pi,12,endpoint=False)
    nib=np.stack([np.cos(theta)*91,np.sin(theta)*46],axis=1)@np.array([[.94,.342],[-.342,.94]])
    shapes=[]
    for j,a in enumerate(p):
        t=j/(len(p)-1);pressure=.60+.48*math.sin(math.pi*t)**.6
        shapes.append(Polygon(nib*(w/102)*pressure+a))
    g=unary_union([unary_union(shapes[j:j+2]).convex_hull for j in range(len(shapes)-1)])
    for a,b in [(p[0],p[1]),(p[-1],p[-2])]:
        v=a-b;v=v/max(np.linalg.norm(v),1e-6);n=np.array([-v[1],v[0]])
        g=g.union(Polygon([a+n*30,a+v*105+n*33,a-n*30]))
    return g.buffer(0)
'''
CONSTRUCTION=CONSTRUCTION[:CONSTRUCTION.index('def stroke(')]+BRUSH+CONSTRUCTION[CONSTRUCTION.index('def join('):]

def rings(g):
    for poly in ([g] if g.geom_type=='Polygon' else g.geoms):
        if poly.geom_type!='Polygon' or poly.area<2:continue
        poly=orient(poly,sign=-1)
        yield list(poly.exterior.coords)[:-1]
        for r in poly.interiors:yield list(r.coords)[:-1]

def trace_logo(which):
    art=np.array(Image.open(ART).convert('L'))
    top,bottom=[(95,535),(585,1005)][which-1]
    mask=(art[top:bottom,20:1005]<100).astype('uint8')
    n,labs,stats,centroids=cv2.connectedComponentsWithStats(mask)
    for i in range(1,n):
        if stats[i,4]<35 or (centroids[i,0]<85 and centroids[i,1]<130):mask[labs==i]=0
    ys,xs=np.where(mask);mask=mask[ys.min():ys.max()+1,xs.min():xs.max()+1]
    cs,h=cv2.findContours(mask,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
    def poly(c):
        p=cv2.approxPolyDP(c,.32,True)[:,0,:].astype(float);p[:,1]=mask.shape[0]-p[:,1]
        return p
    parts=[]
    for i,c in enumerate(cs):
        if h[0,i,3]>=0:continue
        holes=[poly(cs[j]) for j in range(len(cs)) if h[0,j,3]==i]
        parts.append(Polygon(poly(c),holes).buffer(0))
    g=unary_union(parts);g=scale(g,xfact=1000/mask.shape[0],yfact=1000/mask.shape[0],origin=(0,0))
    return translate(g,xoff=35,yoff=-220),mask

def native_letters(style):
    """Separate the original connected mark along its letter junctions."""
    art=np.array(Image.open(ART).convert('L'))
    regions1={
      'c':[(30,225),(165,225),(210,343),(170,413),(30,420)],
      'y':[(165,242),(303,242),(278,374),(326,520),(95,530),(95,404),(220,443),(252,423),(186,387),(205,343)],
      'b':[(291,108),(425,108),(440,330),(414,395),(399,452),(285,452),(305,382),(291,355)],
      'r':[(424,227),(566,227),(566,318),(500,348),(504,430),(405,430),(425,374)],
      'd':[(567,110),(684,110),(627,269),(628,351),(680,426),(500,440),(506,350),(560,320)],
      'e':[(632,255),(741,255),(747,448),(645,416),(631,365)],
      'l':[(731,106),(779,106),(779,390),(826,456),(734,452)],
      'i':[(784,181),(836,181),(843,430),(783,430)]}
    regions2={
      'c':[(38,679),(150,679),(188,751),(176,796),(139,856),(208,943),(38,943)],
      'y':[(150,680),(250,680),(280,781),(312,866),(256,1000),(128,1000),(144,864),(192,819),(193,732)],
      'b':[(292,588),(371,647),(361,698),(432,752),(390,817),(347,876),(301,927),(308,854),(237,790)],
      'r':[(398,672),(517,704),(581,797),(528,768),(509,861),(535,909),(420,904),(432,785)],
      'd':[(564,587),(644,587),(629,704),(627,817),(674,918),(597,951),(535,881),(490,828),(547,827),(570,779),(552,716)],
      'e':[(631,733),(723,690),(749,809),(730,904),(647,879),(631,840)],
      'l':[(728,589),(789,589),(784,854),(820,913),(726,905)],
      'i':[(789,640),(846,640),(848,900),(789,900)]}
    regions=regions1 if style==1 else regions2
    result={};baseline=428 if style==1 else 899
    for c,region in regions.items():
        m=(art<100).astype('uint8');clip=np.zeros_like(m);cv2.fillPoly(clip,[np.array(region,dtype='int32')],1);m*=clip
        cs,h=cv2.findContours(m,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE);parts=[]
        for j,contour in enumerate(cs):
            if h[0,j,3]>=0 or cv2.contourArea(contour)<30:continue
            shell=cv2.approxPolyDP(contour,.5,True)[:,0,:].astype(float)
            holes=[cv2.approxPolyDP(cs[k],.5,True)[:,0,:].astype(float) for k in range(len(cs)) if h[0,k,3]==j and cv2.contourArea(cs[k])>8]
            def flip(p):p=p.copy();p[:,1]=baseline-p[:,1];return p*2
            parts.append(Polygon(flip(shell),[flip(hh) for hh in holes]).buffer(0))
        g=unary_union(parts)
        if g.geom_type=='MultiPolygon' and c!='i':g=max(g.geoms,key=lambda p:p.area)
        result[c]=translate(g,xoff=-g.bounds[0])
    return result

def build(style,family):
    from shapely.geometry import MultiPoint
    ns=dict(STYLE=style,np=np,math=math,LineString=LineString,Polygon=Polygon,Point=Point,MultiPolygon=MultiPolygon,MultiPoint=MultiPoint,unary_union=unary_union,scale=scale,translate=translate)
    exec(CONSTRUCTION,ns)
    G=ns['G'];S=ns['S'];join=ns['join'];stem=ns['stem'];dot=ns['dot']
    # Signature hooks, swept y tail and clearly separated l/i skeletons.
    G['y']=join(S((65,465),(105,290,190,198,285,215),(397,240,448,354,474,465)),S((474,465),(464,150,382,-89,263,-207),(154,-314,32,-198,-74,-125)))
    G['l']=S((128,760),(85,661,100,435,104,201),(105,72,154,23,277,32))
    G['i']=join(S((116,449),(104,55)),dot(115,638,91))
    G['b']=join(S((126,764),(66,711,82,593,85,508),(85,45)),S((85,336),(212,498,455,512,494,295),(527,99,291,-31,93,108)))
    G['d']=join(ns['oval'](),S((489,50),(489,489),(472,610,508,708,570,767)))
    G['r']=join(S((84,460),(84,46)),S((89,332),(212,502,340,511,440,418)))
    # Preserve the source marks' actual bowl, spike and swash vocabulary.
    # New characters are extensions; the intact wordmark remains a separate ligature.
    def compact(x,y,z=None):
        xx=np.asarray(x)*.62;yy=np.asarray(y)
        yy=np.where(yy<=500,yy*.70,350+(yy-500)*1.45)
        return xx,yy
    G={c:transform(compact,g) for c,g in G.items()}
    native=native_letters(style)
    # Open the c aperture beyond the contextual logo's touching junction.
    cg=native['c'];x0,y0,x1,y1=cg.bounds;mid=(y0+y1)/2
    native['c']=cg.difference(Polygon([(x1*.59,mid),(x1+20,mid+31),(x1+20,mid-31)]))
    G.update(native)
    # The same c supplies the closed bowls throughout the alphabet.
    bowl=join(native['c'],translate(scale(native['c'],xfact=-1,yfact=1,origin=(0,0)),xoff=native['c'].bounds[2]))
    bw=bowl.bounds[2];top=bowl.bounds[3]
    def bar(x,bottom=0,high=top):
        if style==2:return Polygon([(x-43,bottom+30),(x-43,high-30),(x+34,high+27),(x+38,bottom+15),(x+67,bottom-19)])
        return join(S((x,high),(x-7,bottom+38),(x+24,bottom-3),w=75))
    G['o']=bowl;G['a']=join(bowl,bar(bw-25));G['q']=join(bowl,bar(bw-20,-196))
    G['d']=scale(native['b'],xfact=-1,yfact=1,origin=(native['b'].bounds[2]/2,0))
    G['p']=join(native['b'],bar(47,-206,390))
    # Standalone shoulders need their own join, not the logo's contextual overlap.
    nw=325
    G['r']=join(bar(47),S((47,238),(129,368,249,367,310,287),w=92))
    G['n']=join(bar(47),S((47,225),(120,372,282,388,288,213),(288,20),w=98))
    G['m']=join(G['n'],translate(G['n'],xoff=258))
    G['u']=scale(G['n'],xfact=-1,yfact=-1,origin=(nw/2,top/2))
    G['h']=join(G['n'],bar(44,0,620))
    G['g']=join(bowl,S((bw-28,top),(bw-22,24),(bw-12,-211,66,-254,-12,-137),w=86))
    G['j']=join(translate(native['i'],xoff=65),S((112,80),(109,-130,39,-212,-45,-168),w=74))
    # Capitals adopt the same source-derived rounded or cut bowls where possible.
    for cap,lower in [('C','c'),('O','o'),('S','s'),('U','u'),('V','v'),('W','w'),('X','x'),('Z','z')]:
        g=G[lower];G[cap]=scale(g,xfact=1.12,yfact=650/max(1,g.bounds[3]-g.bounds[1]),origin=(0,g.bounds[1]))
    ns['oval']=lambda: bowl
    # Latin-1 letters use native base glyphs and authored accents.
    G['Æ']=join(scale(G['A'],xfact=.78,yfact=1,origin=(0,0)),translate(G['E'],xoff=420))
    G['æ']=join(scale(G['a'],xfact=.85,yfact=1,origin=(0,0)),translate(G['e'],xoff=415))
    G['Ø']=join(G['O'],S((80,7),(539,726),w=55))
    G['ø']=join(G['o'],S((57,0),(525,521),w=50))
    G['Ð']=join(G['D'],S((12,360),(268,360),w=60));G['ð']=join(G['o'],S((426,430),(250,720)),S((238,582),(457,700),w=55))
    G['Þ']=join(stem(80,710),translate(G['p'],yoff=140));G['þ']=join(stem(80,710,-160),G['p'])
    G['ß']=join(stem(80,530),S((80,535),(77,775,425,741,419,552),(411,457,321,417,274,397),(591,323,527,44,235,52)))
    G['Œ']=join(G['O'],translate(G['E'],xoff=475));G['œ']=join(G['o'],translate(G['e'],xoff=430))
    for c in ''.join(chr(n) for n in range(192,256))+'ŠšŽžŸ':
        decomp=unicodedata.normalize('NFD',c)
        if c in G or len(decomp)!=2 or decomp[0] not in G:continue
        base,accent=decomp;g=G[base];cx=(g.bounds[0]+g.bounds[2])/2;yy=max(g.bounds[3]+110,650)
        if accent=='\u0301':ac=S((cx-58,yy),(cx+78,yy+117),w=53)
        elif accent=='\u0300':ac=S((cx-78,yy+117),(cx+58,yy),w=53)
        elif accent=='\u0302':ac=S((cx-122,yy),(cx,yy+101),(cx+122,yy),w=49)
        elif accent=='\u0308':ac=join(dot(cx-103,yy+36,64),dot(cx+103,yy+36,64))
        elif accent=='\u0303':ac=S((cx-140,yy),(cx-43,yy+119,cx+40,yy-66,cx+143,yy+54),w=46)
        elif accent=='\u030a':ac=Point(cx,yy+49).buffer(79).difference(Point(cx,yy+49).buffer(33))
        elif accent=='\u0327':ac=S((cx,0),(cx-35,-90),(cx+64,-157,cx+74,-210,cx-54,-228),w=49)
        elif accent=='\u030c':ac=S((cx-122,yy+95),(cx,yy),(cx+122,yy+95),w=49)
        else:continue
        if base=='i':g=S((116,449),(104,55))
        G[c]=join(g,ac)
    for c,original in {'‘':"'",'’':"'",'‚':',','“':'"','”':'"','„':'"','–':'-','—':'-','−':'-','¡':'!','¿':'?'}.items():
        g=G[original]
        if c in '—–':g=scale(g,xfact=2 if c=='—' else 1.5,yfact=1,origin=(0,0))
        if c in '¡¿':g=scale(g,xfact=-1,yfact=-1,origin=(260,300))
        if c=='„':g=translate(g,yoff=-550)
        G[c]=g
    G['…']=join(G['.'],translate(G['.'],xoff=220),translate(G['.'],xoff=440))
    G['€']=join(G['C'],S((10,415),(398,415),w=53),S((10,275),(366,275),w=53))
    G['£']=join(S((125,65),(133,512),(117,760,446,741,497,620)),S((30,340),(338,340),w=59),S((40,50),(506,50),w=64))
    G['¥']=join(G['Y'],S((103,294),(515,294),w=55),S((103,163),(515,163),w=55))
    G['¢']=join(G['c'],S((290,624),(232,-120),w=50))
    G['©']=join(Point(340,355).buffer(343).difference(Point(340,355).buffer(299)),translate(scale(G['C'],xfact=.62,yfact=.62,origin=(0,0)),xoff=132,yoff=142))
    G['®']=join(Point(340,355).buffer(343).difference(Point(340,355).buffer(299)),translate(scale(G['R'],xfact=.62,yfact=.62,origin=(0,0)),xoff=132,yoff=142))
    G['™']=join(scale(G['T'],xfact=.53,yfact=.53,origin=(0,0)),translate(scale(G['M'],xfact=.53,yfact=.53,origin=(0,0)),xoff=320))
    G['°']=Point(125,580).buffer(118).difference(Point(125,580).buffer(61))
    G['·']=dot(115,275,75);G['×']=join(S((70,70),(470,470),w=63),S((70,470),(470,70),w=63));G['÷']=join(G['-'],dot(215,450,70),dot(215,58,70))
    G['•']=Point(135,280).buffer(85)
    G['±']=join(G['+'],translate(G['-'],yoff=-310));G['¬']=S((50,365),(470,365),(470,164),w=65)
    G['¦']=join(S((120,750),(120,380),w=66),S((120,210),(120,-130),w=66))
    G['¨']=join(dot(80,640,70),dot(270,640,70));G['¯']=S((50,660),(350,660),w=55)
    G['´']=S((100,590),(244,742),w=53);G['¸']=S((166,0),(128,-84),(238,-160,135,-244,76,-183),w=55)
    G['µ']=join(G['u'],bar(30,-170,300))
    G['§']=join(scale(G['S'],xfact=.8,yfact=.65,origin=(0,0)),translate(scale(G['S'],xfact=.8,yfact=.65,origin=(0,0)),yoff=260))
    G['¶']=join(Point(230,480).buffer(210).intersection(Polygon([(0,0),(230,0),(230,800),(0,800)])),bar(245,0,690),bar(420,0,690))
    G['«']=join(G['<'],translate(G['<'],xoff=270));G['»']=join(G['>'],translate(G['>'],xoff=270))
    G['¤']=join(Point(270,340).buffer(180).difference(Point(270,340).buffer(110)),S((65,135),(143,213),w=62),S((396,465),(474,543),w=62),S((65,543),(143,465),w=62),S((396,213),(474,135),w=62))
    for c,base in [('ª','a'),('º','o'),('¹','1'),('²','2'),('³','3')]:G[c]=translate(scale(G[base],xfact=.55,yfact=.55,origin=(0,0)),yoff=390)
    for c,num,den in [('¼','1','4'),('½','1','2'),('¾','3','4')]:G[c]=join(translate(scale(G[num],xfact=.5,yfact=.5,origin=(0,0)),yoff=390),S((110,0),(440,710),w=40),translate(scale(G[den],xfact=.5,yfact=.5,origin=(0,0)),xoff=350))
    G['\u00ad']=G['-']
    logo,mask=trace_logo(style)
    normalized={};advances={}
    for c,g in G.items():
        g=g.buffer(0).simplify(.7,preserve_topology=True)
        normalized[c]=translate(g,xoff=42-g.bounds[0]);advances[c]=round(g.bounds[2]-g.bounds[0]+84)
    G=normalized
    cmap={ord(c):f'uni{ord(c):04X}' for c in G};cmap.update({32:'space',160:'space',0xE000:'brandmark'})
    order=['.notdef','space']+[cmap[ord(c)] for c in G]+['brandmark']
    glyphs={};metrics={}
    geoms={cmap[ord(c)]:g for c,g in G.items()};geoms['brandmark']=logo
    geoms['.notdef']=Polygon([(45,0),(455,0),(455,700),(45,700)],holes=[[(105,60),(105,640),(395,640),(395,60)]])
    for name,g in geoms.items():
        pen=TTGlyphPen(None)
        for ring in rings(g):
            pen.moveTo(tuple(round(v) for v in ring[0]))
            for p in ring[1:]:pen.lineTo(tuple(round(v) for v in p))
            pen.closePath()
        glyphs[name]=pen.glyph();metrics[name]=(round(g.bounds[2]+42),round(g.bounds[0]))
    glyphs['space']=TTGlyphPen(None).glyph();metrics['space']=(300,0)
    fb=FontBuilder(1000,isTTF=True);fb.setupGlyphOrder(order);fb.setupCharacterMap(cmap);fb.setupGlyf(glyphs);fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=1180,descent=-420,lineGap=0)
    psname=family.replace(' ','')+'-Regular'
    fb.setupNameTable({'familyName':family,'styleName':'Regular','uniqueFontIdentifier':psname+'-1.000','fullName':family+' Regular','psName':psname,'version':'Version 1.000','copyright':'Cybrdelic custom type, 2026.','description':'Custom display type. Discretionary cybrdelic wordmark ligature at U+E000.'})
    fb.setupOS2(sTypoAscender=1180,sTypoDescender=-420,sTypoLineGap=0,usWinAscent=1180,usWinDescent=420,sxHeight=500,sCapHeight=750,fsType=0,fsSelection=64)
    fb.setupPost();fb.setupMaxp()
    kern={('A','V'):-70,('V','A'):-70,('A','W'):-50,('W','A'):-50,('T','o'):-65,('T','a'):-55,('Y','o'):-60,('L','T'):-40,('F','a'):-35,('P','a'):-30,('r','a'):-20,('r','o'):-20,('l','i'):18,('i','c'):10}
    seq=' '.join(cmap[ord(c)] for c in 'cybrdelic')
    fea='languagesystem DFLT dflt; languagesystem latn dflt;\nfeature kern {\n'+''.join(f'pos {cmap[ord(a)]} {cmap[ord(b)]} {v};\n' for (a,b),v in kern.items())+'} kern;\nfeature dlig { sub '+seq+' by brandmark; } dlig;'
    addOpenTypeFeaturesFromString(fb.font,fea)
    ttf=OUT/'fonts'/f'{psname}.ttf';fb.save(ttf)
    web=TTFont(ttf);web.flavor='woff2';web.save(ttf.with_suffix('.woff2'))
    (OUT/'source'/f'{psname}.fea').write_text(fea)
    (OUT/'source'/f'{psname}-outlines.json').write_text(json.dumps({name:[r for r in rings(g)] for name,g in geoms.items()},separators=(',',':')))
    # A real vector outline of the approved wordmark, not an embedded bitmap.
    commands=[]
    for ring in rings(logo):commands.append('M'+' L'.join(f'{x:.2f},{-y:.2f}' for x,y in ring)+' Z')
    x0,y0,x1,y1=logo.bounds
    (OUT/'vector'/f'{psname}-wordmark.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0-20} {-y1-20} {x1-x0+40} {y1-y0+40}"><path d="'+ ' '.join(commands)+'"/></svg>')
    # Inspect actual font rasterization, including the optional OpenType wordmark.
    im=Image.new('RGB',(1500,1580),'#f6f4ef');d=ImageDraw.Draw(im)
    ui=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
    d.text((55,30),family.upper()+' / REGULAR',font=ui,fill='#333')
    y=95
    for text,size in [('cybrdelic',220),('ABCDEFGHIJKLMNOPQRSTUVWXYZ',90),('abcdefghijklmnopqrstuvwxyz',102),('0123456789  & @ # ! ?',104),('FLOW / FORM / FREQUENCY',95),('li il ill lily minimum',110),('ÀÁÂÃÄÅ Æ Ç ÈÉÊË Ð Ñ Ø Œ',84),('àáâãäå æ ç èéêë ð ñ ø œ',90),('Šš Žž ß € £ ¥ © ® ™',88)]:
        f=ImageFont.truetype(str(ttf),size)
        d.text((55,y),text,font=f,fill='#111',anchor='lt');y+=205 if text=='cybrdelic' else 106
    d.line((55,1160,1445,1160),fill='#bbb');d.text((55,1180),'OPTIONAL WORDMARK LIGATURE / dlig',font=ui,fill='#555')
    f=ImageFont.truetype(str(ttf),250);d.text((55,1250),'\uE000',font=f,fill='#111',anchor='lt')
    im.save(OUT/'specimens'/f'{psname}.png')
    # Font round-trip and outline coverage validation.
    font=TTFont(ttf);missing=[c for c in string.printable[:95] if ord(c) not in font.getBestCmap()]
    assert not missing,missing
    assert font['OS/2'].fsType==0
    for name in font.getGlyphOrder():
        gl=font['glyf'][name]
        if gl.numberOfContours:assert gl.yMax<=1180 and gl.yMin>=-420,(name,gl.yMin,gl.yMax)
    report={'family':family,'mappedCharacters':len(cmap),'glyphs':len(order),'kerningPairs':len(kern),'wordmark':'U+E000 or dlig on cybrdelic','ttfBytes':ttf.stat().st_size,'woff2Bytes':ttf.with_suffix('.woff2').stat().st_size}
    print(json.dumps(report),flush=True)
    return report

reports=[build(1,'Cybrdelic Sigil'),build(2,'Cybrdelic Cut')]
(OUT/'validation.json').write_text(json.dumps(reports,indent=2))
if not PACKAGED:
    shutil.copy2(__file__,OUT/'source/build_families.py')
    shutil.copy2(ROOT/'work/brand-font/build_type.py',OUT/'source/base-construction.py')
    shutil.copy2(ART,OUT/'source/approved-studies.png')
