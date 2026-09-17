"""Attach the actual visual review and small artifact integrity measurements."""
import json,hashlib
import numpy as np
from PIL import Image,ImageDraw
from lava_mpm import ROOT

def main():
    folder=ROOT/'fractured-feed-18';image=folder/'optical-proof/state.png';pixels=np.asarray(Image.open(image).convert('RGB'))
    border=np.concatenate([pixels[0],pixels[-1],pixels[:,0],pixels[:,-1]])
    assert border.max()==0,'Backdrop boundary must be pitch black'
    receipt_path=folder/'optical-proof/state.json';receipt=json.loads(receipt_path.read_text());assert Image.open(image).size==(receipt['width'],receipt['height'])
    receipt['status']='visually inspected CPU study; not accepted as world-class or production-complete'
    review=dict(status=receipt['status'],inspectedImage=str(image),imageSha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                improved=['Actual thick, separate basalt surfaces instead of a smooth red lump','Rough relief and pores are visible in the CPU path-traced image','Fracture gaps open through solved clast motion; the larger piece moves about 8 mm','Object is framed fully against black'],
                remaining=['Exposed melt is too uniform in orange color and lacks resolved surface cooling detail','Several main fracture faces still look too clean and cut','Initial cracks and pores are authored initial volume, not simulated formation','The 0.658 s interval is a brief test; no full lava/gas/bed result','Affine surface fit has up to 0.863 mm residual and 3.26% per-clast volume mismatch'],
                blackBorderMaximum=int(border.max()),size=list(Image.open(image).size),device='CPU',
                initialBoundaryAudit=dict(path=str(folder/'initial-boundaries.npz'),sha256=hashlib.sha256((folder/'initial-boundaries.npz').read_bytes()).hexdigest(),note='Hash captured during review; the boundary was generated before simulation.'))
    receipt['visualReview']=review;receipt_path.write_text(json.dumps(receipt,indent=2));(folder/'visual-review.json').write_text(json.dumps(review,indent=2))
    sheet=Image.new('RGB',(1440,294));draw=ImageDraw.Draw(sheet)
    for j,(frame,timestamp) in enumerate([('000000','0.000 s'),('000322','0.322 s'),('000658','0.658 s')]):
        source=Image.open(folder/('frame-'+frame+'-surface-diagnostic.png'))
        crop=source.crop((0,480,720,870)).resize((480,260),Image.Resampling.LANCZOS)
        sheet.paste(crop,(480*j,26));draw.text((480*j+14,8),timestamp+' / fixed camera / CPU geometry',fill=(183,176,168))
    sheet.save(folder/'motion-comparison.png')
    print(json.dumps(dict(status=review['status'],image=str(image),size=review['size'],blackBorderMaximum=review['blackBorderMaximum'])))

if __name__=='__main__':main()
