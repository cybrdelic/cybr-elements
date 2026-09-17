from pathlib import Path
import math,json,string,shutil
import numpy as np
from shapely.geometry import LineString,Polygon,Point,MultiPolygon
from shapely.ops import unary_union
from shapely.affinity import scale,skew,translate
from shapely.geometry.polygon import orient
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve();ROOT=HERE.parent.parent if HERE.parent.name=='source' else HERE.parents[2]/'outputs'/'cybrdelic-type';ROOT.mkdir(exist_ok=True)
for folder in ['fonts','vector','previews','source']: (ROOT/folder).mkdir(exist_ok=True)

def path(start,*cmd):
    pts=[np.array(start,float)]
    for c in cmd:
        if len(c)==2: pts.extend(np.linspace(pts[-1],c,max(2,int(np.linalg.norm(np.array(c)-pts[-1])/5)))[1:])
        else:
            a,b,end=np.array(c).reshape(3,2);p=pts[-1];u=np.linspace(0,1,65)[1:,None]
            pts.extend((1-u)**3*p+3*(1-u)**2*u*a+3*(1-u)*u*u*b+u**3*end)
    return np.array(pts)
def stroke(p,w=102,flat=False):
    # Drawn centerlines are expanded into standalone closed outlines.
    return LineString(p).buffer(w/2,cap_style=2 if flat else 1,join_style=1,quad_segs=16)
def join(*parts):return unary_union(parts).buffer(0).simplify(.45,preserve_topology=True)
def S(start,*cmd,w=102,flat=False):return stroke(path(start,*cmd),w,flat)
def oval(x=0,y=0,w=102):
    return S((280+x,450+y),(440+x,450+y,495+x,410+y,495+x,250+y),(495+x,90+y,440+x,50+y,280+x,50+y),(120+x,50+y,65+x,95+y,65+x,250+y),(65+x,410+y,120+x,450+y,280+x,450+y),w=w)
def stem(x,top=450,bottom=50):return S((x,top),(x,bottom))
def dot(x,y,w=86):
    # A canted lozenge, repeated in punctuation and the i/j dots.
    return Polygon([(x-w*.5,y-w*.32),(x+w*.24,y-w*.47),(x+w*.5,y+w*.32),(x-w*.24,y+w*.47)]).buffer(9,join_style=1)
G={};A={}
def put(c,width,*p):G[c]=join(*p);A[c]=width
put('c',570,S((495,391),(430,465,350,450,280,450),(120,450,65,397,65,250),(65,92,120,50,280,50),(376,50,436,82,491,143),flat=True))
put('o',600,oval())
put('a',610,oval(),stem(495))
put('b',615,S((156,710),(100,710,80,676,80,622),(80,50)),S((80,324),(134,425,200,450,295,450),(440,450,505,394,505,250),(505,105,437,50,292,50),(199,50,129,77,80,117)))
put('d',615,oval(),S((495,50),(495,620),(495,675,516,710,566,710)))
put('e',590,S((75,261),(478,300),(479,407,426,450,281,450),(133,450,65,391,65,251),(65,107,128,50,280,50),(375,50,438,85,492,136),flat=True))
put('f',415,S((133,-105),(133,552),(133,674,206,726,362,689),flat=True),S((55,450),(336,450),w=88,flat=True))
put('g',615,oval(),S((495,446),(495,-4),(495,-119,421,-166,285,-166),(194,-166,122,-133,85,-91),flat=True))
put('h',615,stem(80,710),S((80,315),(153,426,215,450,309,450),(449,450,495,387,495,250),(495,50)))
put('i',245,stem(118),dot(118,630))
put('j',310,S((191,450),(191,-17),(191,-127,142,-166,28,-149),flat=True),dot(191,630))
put('k',570,stem(80,710),S((473,452),(86,204),flat=True),S((260,316),(495,50),flat=True))
put('l',330,S((112,711),(112,174),(112,74,161,48,274,62),flat=True))
put('m',850,stem(80),S((80,328),(143,425,197,450,258,450),(358,450,403,404,403,297),(403,50)),S((403,328),(463,427,519,450,581,450),(698,450,737,392,737,268),(737,50)))
put('n',615,stem(80),S((80,325),(151,427,217,450,309,450),(449,450,495,388,495,248),(495,50)))
put('p',615,stem(80,450,-180),S((80,324),(134,425,200,450,295,450),(440,450,505,394,505,250),(505,105,437,50,292,50),(199,50,129,77,80,117)))
put('q',615,oval(),stem(495,450,-180))
put('r',490,stem(80),S((80,319),(155,458,291,484,434,403),flat=True))
put('s',565,S((472,398),(399,468,177,484,95,396),(18,313,99,267,269,250),(449,233,537,177,464,104),(389,22,178,23,71,107),flat=True))
put('t',435,S((135,629),(135,180),(135,76,195,44,353,78),flat=True),S((49,451),(345,451),w=88,flat=True))
put('u',615,S((80,450),(80,247),(80,110,126,50,266,50),(358,50,424,77,495,182)),stem(495))
put('v',580,S((65,450),(267,50),(304,50),(512,450),flat=True))
put('w',850,S((65,450),(221,50),(261,50),(408,363),(555,50),(598,50),(772,450),flat=True))
put('x',575,S((71,450),(490,50),flat=True),S((490,450),(71,50),flat=True))
put('y',600,S((66,450),(66,251,105,180,265,180),(407,180,466,274,466,450)),S((466,450),(466,4),(466,-112,389,-165,251,-165),(170,-165,105,-129,60,-91),flat=True))
put('z',565,S((73,450),(483,450),(76,50),(492,50),flat=True))
# Capitals use the same large counters, squared shoulders and clipped terminals.
def capoval():return S((310,680),(496,680,550,606,550,355),(550,98,496,50,310,50),(119,50,65,103,65,355),(65,606,118,680,310,680))
put('A',670,S((61,50),(293,680),(330,680),(573,50),flat=True),S((143,256),(493,256),w=90,flat=True))
put('B',665,stem(80,680),S((80,680),(310,680),(525,680,555,547,476,452),(448,413,391,380,310,380),(80,380)),S((310,380),(561,380,596,186,493,100),(453,63,390,50,310,50),(80,50)))
put('C',660,S((551,582),(481,670,406,680,310,680),(118,680,65,605,65,355),(65,105,121,50,310,50),(415,50,497,86,558,168),flat=True))
put('D',685,stem(80,680),S((80,680),(281,680),(499,680,570,578,570,355),(570,132,499,50,281,50),(80,50)))
put('E',600,S((510,680),(80,680),(80,50),(521,50),flat=True),S((80,368),(449,390),w=90,flat=True))
put('F',585,S((80,50),(80,680),(520,680),flat=True),S((80,372),(444,394),w=90,flat=True))
put('G',685,S((551,582),(481,670,406,680,310,680),(118,680,65,605,65,355),(65,105,121,50,310,50),(442,50,557,107,557,246),(557,333),(360,333),flat=True))
put('H',690,stem(80,680),stem(570,680),S((80,368),(570,368),w=90))
put('I',315,S((90,680),(220,680),w=86,flat=True),stem(155,680),S((90,50),(220,50),w=86,flat=True))
put('J',560,S((445,680),(445,221),(445,104,400,50,260,50),(118,50,65,113,65,228),flat=True))
put('K',650,stem(80,680),S((552,680),(86,282),flat=True),S((285,450),(566,50),flat=True))
put('L',555,S((80,680),(80,173),(80,85,128,50,232,50),(485,50),flat=True))
put('M',830,S((80,50),(80,680),(133,680),(390,301),(651,680),(704,680),(704,50),flat=True))
put('N',705,S((80,50),(80,680),(125,680),(540,50),(579,50),(579,680),flat=True))
put('O',675,capoval())
put('P',635,stem(80,680),S((80,680),(285,680),(493,680,535,604,535,490),(535,376,478,315,285,315),(80,315)))
put('Q',710,capoval(),S((370,226),(604,-20),w=94,flat=True))
put('R',665,stem(80,680),S((80,680),(285,680),(493,680,535,604,535,490),(535,376,478,315,285,315),(80,315)),S((310,315),(565,50),flat=True))
put('S',650,scale(G['s'],xfact=1.12,yfact=1.575,origin=(0,50)))
put('T',635,S((52,680),(573,680),w=94,flat=True),stem(313,680))
put('U',680,S((80,680),(80,258),(80,106,140,50,320,50),(500,50,557,108,557,258),(557,680),flat=True))
put('V',655,S((61,680),(291,50),(329,50),(578,680),flat=True))
put('W',970,S((64,680),(265,50),(302,50),(460,494),(627,50),(665,50),(891,680),flat=True))
put('X',655,S((63,680),(568,50),flat=True),S((568,680),(63,50),flat=True))
put('Y',655,S((62,680),(309,361),(570,680),flat=True),stem(309,361))
put('Z',645,S((75,680),(564,680),(76,50),(568,50),flat=True))
# Numerals are independently drawn, with open counters and the same corner language.
put('0',675,capoval(),S((200,190),(423,550),w=46,flat=True))
put('1',440,S((72,560),(246,680),(246,50),flat=True),S((100,50),(371,50),w=88,flat=True))
put('2',645,S((74,573),(128,679,213,680,308,680),(475,680,555,617,545,481),(534,352,313,270,80,50),(553,50),flat=True))
put('3',630,S((77,610),(185,704,410,706,505,605),(596,507,500,389,339,367),(515,359,610,216,511,115),(415,14,179,28,72,121),flat=True))
put('4',650,S((433,50),(433,680),(392,680),(60,239),(555,239),flat=True))
put('5',630,S((528,680),(102,680),(88,388),(259,435,468,428,520,300),(577,164,465,50,301,50),(185,50,117,78,67,118),flat=True))
put('6',655,S((519,613),(423,696,232,717,132,580),(46,465,64,212,99,138),(141,36,366,19,481,97),(600,178,576,375,410,412),(284,443,146,397,88,296),flat=True))
put('7',615,S((66,680),(535,680),(243,50),flat=True))
put('8',655,scale(oval(),xfact=1.05,yfact=.73,origin=(0,50)),translate(scale(oval(),xfact=.90,yfact=.73,origin=(280,50)),xoff=10,yoff=310))
put('9',655,scale(G['6'],xfact=-1,yfact=-1,origin=(305,365)))
for c,y in [('.',65),(':',380)]:put(c,245,dot(118,y))
put(':',245,dot(118,400),dot(118,65));put(';',245,dot(118,400),S((142,82),(118,-34),(68,-72),w=78,flat=True))
put(',',245,S((142,82),(118,-34),(68,-72),w=78,flat=True))
put('-',440,S((68,258),(361,258),w=80,flat=True));put('_',600,S((55,-108),(534,-108),w=80,flat=True))
put('!',245,stem(118,680,246),dot(118,65))
put('?',590,S((72,579),(147,710,394,710,481,602),(571,483,431,396,306,327),(266,299,256,271,256,223),flat=True),dot(256,65))
put('/',455,S((56,-130),(380,742),w=80,flat=True));put('\\',455,S((56,742),(380,-130),w=80,flat=True))
put('+',565,S((75,285),(490,285),w=84,flat=True),S((282,492),(282,78),w=84,flat=True))
put('=',565,S((75,375),(490,375),w=76,flat=True),S((75,195),(490,195),w=76,flat=True))
put('(',330,S((257,740),(72,565,69,145,257,-107),w=82,flat=True));put(')',330,scale(G['('],xfact=-1,yfact=1,origin=(164,0)))
put('[',330,S((253,737),(97,737),(97,-106),(253,-106),w=82,flat=True));put(']',330,scale(G['['],xfact=-1,yfact=1,origin=(164,0)))
put("'",240,S((132,710),(105,542),w=76,flat=True));put('"',390,G["'"],translate(G["'"],xoff=155))
put('#',695,S((238,670),(143,50),w=76,flat=True),S((490,670),(395,50),w=76,flat=True),S((70,260),(581,260),w=76,flat=True),S((108,468),(619,468),w=76,flat=True))
put('&',735,S((609,54),(174,437),(77,524,134,675,273,680),(450,687,493,481,277,344),(107,237,52,166,126,87),(222,-2,422,49,548,234),(620,354),w=94,flat=True))
put('@',855,translate(scale(oval(),xfact=.6,yfact=.72,origin=(0,50)),xoff=183,yoff=99),S((507,416),(507,191),(612,102,740,163,739,385),(731,667,531,746,318,687),(27,607,26,204,176,78),(324,-43,598,-32,723,70),w=76,flat=True))
# Complete printable Basic Latin coverage.
put('$',650,G['S'],S((313,786),(313,-53),w=58,flat=True))
put('%',750,translate(scale(oval(),xfact=.39,yfact=.52,origin=(0,0)),xoff=20,yoff=428),translate(scale(oval(),xfact=.39,yfact=.52,origin=(0,0)),xoff=432,yoff=20),S((111,50),(616,680),w=75,flat=True))
put('*',520,*[S((260,520),(260+190*math.sin(j*math.tau/5),520+190*math.cos(j*math.tau/5)),w=69,flat=True) for j in range(5)])
put('<',500,S((404,518),(82,280),(404,44),w=80,flat=True));put('>',500,scale(G['<'],xfact=-1,yfact=1,origin=(248,0)))
put('^',555,S((74,447),(277,694),(480,447),w=76,flat=True))
put('`',255,S((74,724),(172,600),w=76,flat=True))
put('|',245,S((120,780),(120,-130),w=76,flat=True))
put('~',625,S((75,299),(233,478,346,146,550,333),w=75,flat=True))
put('{',410,S((330,741),(203,741,180,706,180,559),(180,429,146,385,74,337),(145,293,180,250,180,121),(180,-42,203,-98,330,-98),w=79,flat=True));put('}',410,scale(G['{'],xfact=-1,yfact=1,origin=(202,0)))

# Layout and kerning shared by the OpenType font and SVG master.
K={('c','y'):-18,('y','b'):-20,('b','r'):-8,('r','d'):-20,('d','e'):-10,('e','l'):-12,('l','i'):-25,('i','c'):-24,('T','o'):-48,('T','a'):-42,('A','V'):-38,('V','A'):-38,('W','a'):-30,('Y','o'):-44}
def polygons(g):return [g] if g.geom_type=='Polygon' else list(g.geoms)
def outline(g):
    out=[]
    for poly in polygons(g):
        poly=orient(poly,sign=-1)
        for ring in [poly.exterior,*poly.interiors]:out.append(list(ring.coords)[:-1])
    return out
def make_font():
    cmap={ord(c):('uni%04X'%ord(c)) for c in G};cmap[32]='space'
    order=['.notdef','space']+[cmap[ord(c)] for c in G]
    fb=FontBuilder(1000,isTTF=True);fb.setupGlyphOrder(order);fb.setupCharacterMap(cmap)
    glyphs={};metrics={}
    for c,g in G.items():
        pen=TTGlyphPen(None)
        for ring in outline(g):
            pen.moveTo(tuple(round(v) for v in ring[0]))
            for xy in ring[1:]:pen.lineTo(tuple(round(v) for v in xy))
            pen.closePath()
        name=cmap[ord(c)];glyphs[name]=pen.glyph();metrics[name]=(A[c],round(g.bounds[0]))
    for name in ['.notdef','space']:
        pen=TTGlyphPen(None)
        if name=='.notdef':
            pen.moveTo((80,0));pen.lineTo((80,650));pen.lineTo((450,650));pen.lineTo((450,0));pen.closePath()
        glyphs[name]=pen.glyph();metrics[name]=(320 if name=='space' else 530,0)
    fb.setupGlyf(glyphs);fb.setupHorizontalMetrics(metrics);fb.setupHorizontalHeader(ascent=820,descent=-240)
    fb.setupNameTable({'familyName':'Cybrdelic Flux','styleName':'Display','uniqueFontIdentifier':'CybrdelicFlux-Display-0.1','fullName':'Cybrdelic Flux Display','psName':'CybrdelicFlux-Display','version':'Version 0.100','copyright':'Custom Cybrdelic lettering, 2026. Original outlines.','description':'Original display prototype for Cybrdelic. Latin letters, figures and selected punctuation.','licenseDescription':'Created for the Cybrdelic brand; editable source included. No third-party font outlines used.'})
    fb.setupOS2(sTypoAscender=820,sTypoDescender=-240,sTypoLineGap=0,usWinAscent=850,usWinDescent=260,sxHeight=500,sCapHeight=730,usWeightClass=650)
    fb.setupPost();fb.setupMaxp()
    fea='languagesystem DFLT dflt; languagesystem latn dflt; feature kern {\n'+''.join(f'pos {cmap[ord(a)]} {cmap[ord(b)]} {v};\n' for (a,b),v in K.items())+'} kern;'
    addOpenTypeFeaturesFromString(fb.font,fea)
    dest=ROOT/'fonts'/'CybrdelicFlux-Display.ttf';fb.save(dest)
    f=TTFont(dest);f.flavor='woff2';f.save(ROOT/'fonts'/'CybrdelicFlux-Display.woff2')
    return dest
FONT=make_font()
def word(shapes=G,adv=A,spacing=K):
    parts=[];x=0;txt='cybrdelic'
    for i,c in enumerate(txt):
        parts.append((c,translate(shapes[c],xoff=x)))
        x+=adv[c]
        if i+1<len(txt):x+=spacing.get((c,txt[i+1]),0)
    return parts
# Concept B: low, broad, liquid forms with high stroke contrast.
U={};UA={}
for c in set('cybrdelic'):
    geo=G[c]
    # Broad horizontal bodies and compressed vertical proportions are deliberate.
    geo=scale(geo,xfact=1.20,yfact=.74,origin=(0,0))
    geo=skew(geo,xs=-10,origin=(0,0))
    U[c]=geo.buffer(14,join_style=1).simplify(.5);UA[c]=A[c]*1.20+10
# Bespoke wide orbit c and low sweeping y distinguish Undertow's silhouette.
U['c']=S((625,316),(519,422,75,401,67,220),(63,52,341,-4,608,114),w=144,flat=True);UA['c']=730
U['y']=join(S((80,341),(178,131,335,155,552,337),w=125,flat=True),S((552,337),(486,46,550,-140,144,-132),(65,-130,18,-105,-9,-74),w=96,flat=True));UA['y']=700
# Concept C: independently drawn, condensed cut-corner forms.
R={};RA={}
def rp(c,width,*pts):R[c]=S(pts[0],*pts[1:],w=112,flat=True);RA[c]=width
rp('c',455,(381,444),(296,490),(134,490),(63,405),(63,135),(141,50),(300,50),(387,123))
rp('y',455,(60,490),(60,248),(140,167),(338,167),(338,490),(338,-68),(254,-155),(73,-155))
rp('b',470,(66,720),(66,50),(286,50),(362,132),(362,406),(286,490),(143,490),(66,409))
rp('r',425,(66,50),(66,490),(66,355),(185,490),(318,490),(364,443))
rp('d',470,(361,720),(361,50),(140,50),(64,131),(64,406),(140,490),(286,490),(361,408))
rp('e',465,(64,258),(363,302),(363,407),(284,490),(144,490),(64,406),(64,131),(142,50),(302,50),(374,116))
rp('l',280,(67,720),(67,133),(145,50),(224,50))
R['i']=join(S((80,490),(80,50),w=112,flat=True),dot(80,655,92));RA['i']=205
rp('c',455,(381,444),(296,490),(134,490),(63,405),(63,135),(141,50),(300,50),(387,123))
CONCEPTS={'01-flux':word(),'02-undertow':word(U,UA,{}),'03-relay':word(R,RA,{})}
def svgpath(g):
    return ' '.join('M '+' '.join(f'{x:.2f},{-y:.2f}' for x,y in ring)+' Z' for ring in outline(g))
def svgmark(parts,name,color='#111111'):
    allg=unary_union([g for _,g in parts]);x0,y0,x1,y1=allg.bounds;pad=60
    body=''.join(f'<g id="glyph-{i+1}-{c}"><path d="{svgpath(g)}"/></g>' for i,(c,g) in enumerate(parts))
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0-pad:.2f} {-y1-pad:.2f} {x1-x0+pad*2:.2f} {y1-y0+pad*2:.2f}" role="img" aria-label="cybrdelic"><g id="wordmark" fill="{color}">{body}</g></svg>'
    (ROOT/'vector'/name).write_text(svg)
for key,parts in CONCEPTS.items():svgmark(parts,key+'.svg')
svgmark(CONCEPTS['01-flux'],'cybrdelic-flux-light.svg','#f4f2ed')
# PIL rasterizes the same original outlines for sheets and verified transparent exports.
def drawgeo(im,g,box,color):
    x0,y0,x1,y1=g.bounds;bx,by,bw,bh=box;sc=min(bw/(x1-x0),bh/(y1-y0));ox=bx+(bw-(x1-x0)*sc)/2;oy=by+(bh-(y1-y0)*sc)/2
    mask=Image.new('L',im.size,0);d=ImageDraw.Draw(mask)
    for poly in polygons(g):
        def pts(r):return [(ox+(x-x0)*sc,oy+(y1-y)*sc) for x,y in r.coords]
        d.polygon(pts(poly.exterior),fill=255)
        for r in poly.interiors:d.polygon(pts(r),fill=0)
    im.paste(color,(0,0,im.width,im.height),mask)
    return box
label=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',22)
small=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',17)
bold=ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf',28)
sheet=Image.new('RGB',(1500,1350),'#f4f2ed');d=ImageDraw.Draw(sheet)
d.text((60,38),'CYBRDELIC / CUSTOM LETTERING',font=bold,fill='#151515')
d.text((60,80),'Three structural directions. Original outlines. Black and white first.',font=small,fill='#666666')
for i,(key,parts) in enumerate(CONCEPTS.items()):
    y=150+i*390;d.line((60,y,1440,y),fill='#c8c6c1',width=1)
    names=['01  FLUX — recommended','02  UNDERTOW','03  RELAY']
    desc=['Broad counters. Clipped openings. A returning y tail.','Low, wide, and liquid. Strongest psychedelic direction.','Condensed, cut-corner strokes. Strongest machine direction.']
    d.text((60,y+20),names[i],font=label,fill='#151515')
    drawgeo(sheet,unary_union([g for _,g in parts]),(80,y+82,1340,210),'#101010')
    d.text((60,y+324),desc[i],font=small,fill='#666666')
sheet.save(ROOT/'previews'/'concepts.png')
hero=Image.new('RGB',(1500,900),'#121212');d=ImageDraw.Draw(hero)
d.text((64,48),'CYBRDELIC FLUX',font=label,fill='#f4f2ed');d.text((64,80),'Original display type / v0.1',font=small,fill='#9c9b97')
drawgeo(hero,unary_union([g for _,g in CONCEPTS['01-flux']]),(75,200,1350,340),'#f4f2ed')
d.line((64,661,1436,661),fill='#3e3e3e');d.text((64,698),'OPEN COUNTERS     /     SHARP RELEASES     /     SOFT RETURNS',font=small,fill='#bdbdb5')
d.text((64,742),'Drawn for motion. Recognizable before the effect.',font=label,fill='#f4f2ed')
hero.save(ROOT/'previews'/'flux-wordmark.png')
for color,name in [('#111111','cybrdelic-flux-dark.png'),('#f4f2ed','cybrdelic-flux-light.png')]:
    im=Image.new('RGBA',(2400,620),(0,0,0,0));drawgeo(im,unary_union([g for _,g in CONCEPTS['01-flux']]),(40,30,2320,560),color);im.save(ROOT/'previews'/name)
    assert im.getpixel((0,0))[3]==0
# Export complete construction data for edits and future source-following fluid motion.
(ROOT/'source'/'glyph-outlines.json').write_text(json.dumps({'unitsPerEm':1000,'family':'Cybrdelic Flux','version':'0.1','advances':A,'kerning':[[a,b,v] for (a,b),v in K.items()],'outlines':{c:outline(g) for c,g in G.items()}},separators=(',',':')))
if Path(__file__).resolve()!=(ROOT/'source'/'build_type.py').resolve(): shutil.copy2(__file__,ROOT/'source'/'build_type.py')
print(json.dumps({'folder':str(ROOT),'characters':len(G)+1,'fontBytes':FONT.stat().st_size,'concepts':list(CONCEPTS)}))
