"""Publish inspected basalt stills, preserving the earlier comparison assets."""
from pathlib import Path
import json,hashlib,shutil
import numpy as np
from PIL import Image

R=Path(__file__).resolve().parent;L=R/'lava-focus';O=L/'breakout'
P=R.parents[2]/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/lava'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(stem):
    path=L/'renders'/stem;receipt=json.loads(path.with_suffix('.json').read_text())
    im=np.asarray(Image.open(path.with_suffix('.png')));raw=np.load(str(path)+'-raw-aov.npz')['color']
    assert receipt['device']=='CPU' and receipt['variant']=='scalar_rgb' and receipt['threads']==2
    assert sha(path.with_suffix('.png'))==receipt['imageSha256']
    assert sha(Path(receipt['source']))==receipt['meshSha256']
    assert np.isfinite(raw).all() and raw.max()>0
    black=np.max(abs(raw),axis=-1)==0
    assert black.mean()>.10 and not im[black].any()
    if '-hero-' in stem:assert not im[:4].any() and not im[-4:].any()
    receipt['blackPixelFraction']=float(black.mean())
    return path,receipt

def main():
    hero,hr=verify('lava-basalt-final-hero-0059-1024-16spp')
    detail,dr=verify('lava-basalt-final-detail-0059-960-8spp')
    assert hr['meshSha256']==dr['meshSha256']
    qa=json.loads((O/'basalt-depth-01-qa.json').read_text())
    assert qa['openEdges']==0 and qa['nonManifoldEdges']==0 and qa['zeroAreaTriangles']==0 and qa['coreConnectedComponents']==1
    originals={'lava-folded.png':'8ddd925c1c2300c73017f4ea642a4db88d5417590aafb291d2d47402885923cf','lava-refined.png':'dab9d6c2f0ca2613b1643a176a2e20e4aa1500c0f87a002a5c7cfd2d0975e4be','lava-restored-first.png':'3e1eabbde8653b89b2cbae18b9f965da2b33a5c38e4e5a288aa59cf7ce26826f'}
    for name,digest in originals.items():assert sha(P/name)==digest
    if not (O/'folded-page.html').exists():shutil.copy2(P/'index.html',O/'folded-page.html')
    if not (O/'folded-review.json').exists():shutil.copy2(P/'review.json',O/'folded-review.json')
    shutil.copy2(hero.with_suffix('.png'),P/'lava-basalt-volume.png')
    shutil.copy2(detail.with_suffix('.png'),P/'lava-basalt-volume-detail.png')
    review={'status':'Reviewed material stills; not a completed fluid simulation or final quality acceptance','defaultView':'Basalt volume','image':'lava-basalt-volume.png','detail':'lava-basalt-volume-detail.png','render':hr,'detailRender':dr,'geometry':json.loads((O/'basalt-depth-01.json').read_text()),'meshQA':qa,'preservedImages':originals,'kept':['Original preferred rough-basalt cracks, pores and temperature field','Thicker coarse volume with a curved underside','Continuous interpolated thermal radiance','Soft side lighting that exposes the basalt relief'],'rejected':[{'image':'lava-rupture-01-hero-0059-640-8spp.png','reason':'Orange exposed surface reads as paint; uniformly pale rear cap'},{'image':'lava-rupture-02-hero-0059-640-8spp.png','reason':'Repeated ridges and thin tiled strips'},{'image':'lava-rupture-03-hero-0059-640-8spp.png','reason':'Smooth silhouette with painted-looking heat streaks'},{'image':'lava-clinker-01-hero-0059-640-8spp.png','reason':'Isolated stones are evenly scattered over exposed melt'},{'image':'lava-basalt-depth-hero-0059-640-8spp.png','reason':'Lighting hides too much crust'}],'remaining':['Some vertical creases retain the procedural character of the original mesh','Shape and temperature field are authored; no new coupled crust/melt dynamics have been validated','Still images do not establish temporal stability or moving sigil quality'],'sourceFiles':{name:sha(R/name) for name in ['lava_basalt_depth.py','lava_basalt_job.py','lava_lobes_render.py','lava_emission_io.py','lava_radiation.py']}}
    (P/'review.json').write_text(json.dumps(review,indent=2));(L/'active-candidate.json').write_text(json.dumps(review,indent=2));(O/'review.json').write_text(json.dumps(review,indent=2))
    html=(O/'folded-page.html').read_text(encoding='utf-8')
    views=[('Basalt volume','lava-basalt-volume.png','Basalt crust / incandescent fissures','Dark rough basalt with recessed incandescent fissures on pitch black',1024,576),('Close-up','lava-basalt-volume-detail.png','Close-up / crust depth and molten fissures','Close view of basalt relief and molten fissures on pitch black',960,672),('Folded pass','lava-folded.png','Previous folded pass','Earlier folded lava study',1280,720),('Rough baseline','lava-refined.png','Earlier rough-basalt baseline','Earlier rough basalt material study',896,672),('Original','lava-restored-first.png','Original saved rough pass','Original granular lava material study',640,480)]
    buttons='<nav aria-label="Lava version">'+''.join(f'<button type="button" aria-pressed="{str(i==0).lower()}" data-src="{src}" data-caption="{caption}" data-alt="{alt}" data-width="{w}" data-height="{h}">{label}</button>' for i,(label,src,caption,alt,w,h) in enumerate(views))+'</nav>'
    start=html.index('<nav aria-label="Lava version">');end=html.index('</nav>',start)+len('</nav>');html=html[:start]+buttons+html[end:]
    start=html.index('<figure>');end=html.index('</figure>',start)+len('</figure>')
    figure='<figure><img id="lava" src="lava-basalt-volume.png" alt="'+views[0][3]+'" width="1024" height="576"><figcaption><span id="caption" aria-live="polite">'+views[0][2]+'</span><a id="download" href="lava-basalt-volume.png" download>Download image</a></figcaption></figure>'
    html=html[:start]+figure+html[end:]
    html=html.replace('Folded basalt / molten breakouts','Basalt crust / molten fissures')
    start=html.index('<details>');end=html.index('</details>',start)+len('</details>')
    notes='<details><summary>Study notes</summary><p>This version returns to the earlier rough basalt, preserving its cracks and fine relief. The broad shape is thicker and the underside is curved; soft side lighting exposes the crust around the incandescent fissures.</p><p>Both images were rendered and denoised on the CPU with Mitsuba. These are authored material stills. Some creases remain procedural, and moving lava and sigil behavior have not been validated.</p><p><a href="review.json">Render and review record</a>. Previous images remain available above.</p></details>'
    html=html[:start]+notes+html[end:];(P/'index.html').write_text(html,encoding='utf-8')
    contract=json.loads((L/'breakout-contract.json').read_text());contract.update(status='Completed and rejected three rupture iterations; tested and rejected rubble, then retained the preserved rough-basalt surface with coarse depth and lighting changes',extension='Direct comparison showed the earlier rough-basalt surface was stronger. One rubble test and one preserved-baseline comparison were evaluated before the retained larger stills.',finalHero=str(hero.with_suffix('.png')),finalDetail=str(detail.with_suffix('.png')),remaining=review['remaining']);(L/'breakout-contract.json').write_text(json.dumps(contract,indent=2))
    print(json.dumps({'page':str(P/'index.html'),'hero':str(P/'lava-basalt-volume.png'),'detail':str(P/'lava-basalt-volume-detail.png'),'sizes':[hr['size'],dr['size']],'previousImagesUnchanged':True}))

if __name__=='__main__':main()
