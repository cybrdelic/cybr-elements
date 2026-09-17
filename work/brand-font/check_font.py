from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from fontTools.ttLib import TTFont
import json
r=Path('outputs/cybrdelic-type');f=r/'fonts/CybrdelicFlux-Display.ttf'
font=TTFont(f);cmap=font.getBestCmap();assert all(i in cmap for i in range(32,127))
assert 'GPOS' in font
for ch in range(33,127):
    g=font['glyf'][cmap[ch]];assert g.numberOfContours>0
web=TTFont(r/'fonts/CybrdelicFlux-Display.woff2');assert web.getBestCmap()==cmap
im=Image.new('RGB',(1500,1180),'#f4f2ed');d=ImageDraw.Draw(im)
ui=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',22)
def row(text,y,size):d.text((65,y),text,font=ImageFont.truetype(str(f),size),fill='#111111')
d.text((65,36),'CYBRDELIC FLUX / FONT SPECIMEN / 95 PRINTABLE CHARACTERS',font=ui,fill='#555555')
row('cybrdelic',110,270)
d.text((65,395),'LOWERCASE',font=ui,fill='#777777')
row('abcdefghijklm',435,130);row('nopqrstuvwxyz',575,130)
d.text((65,730),'CAPITALS / FIGURES',font=ui,fill='#777777')
row('ABCDEFGHIJKLM',780,110);row('NOPQRSTUVWXYZ',890,110)
row('0123456789  & @ ! ?',1010,105)
im.save(r/'previews/font-specimen.png')
report={'family':'Cybrdelic Flux','version':'0.1','printableAsciiCoverage':95,'glyphCount':len(font.getGlyphOrder()),'GPOS':True,'TTFParsed':True,'WOFF2RoundTrip':True,'thirdPartyOutlines':False,'fontSizes':{p.name:p.stat().st_size for p in (r/'fonts').iterdir()}}
(r/'source/validation.json').write_text(json.dumps(report,indent=2));print(report)
