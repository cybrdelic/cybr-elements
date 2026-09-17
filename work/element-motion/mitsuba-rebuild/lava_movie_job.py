"""A small resumable batch of CPU movie frames; never launches a GPU backend."""
import os,argparse,json,hashlib,shutil,gc
from pathlib import Path
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',LAVA_SOURCE_CAMERA='1',LAVA_LIGHT_GAIN='.14',LAVA_EXPOSURE='4.5',LAVA_NORMAL_SMOOTH='1',LAVA_VOLUME_PORE='1',LAVA_BUMP_SCALE='.0006',LAVA_RENDER_BATCH='4',LAVA_BASELINE_MATERIAL='1',LAVA_STAGE='lava')
from lava_lobes_render import main
R=Path(__file__).resolve().parent/'lava-focus';out=R/'stages/movie';out.mkdir(exist_ok=True)
p=argparse.ArgumentParser();p.add_argument('--start',type=int,required=True);p.add_argument('--end',type=int,required=True);args=p.parse_args();assert 0<=args.start<args.end<=32 and args.end-args.start<=6
for frame in range(args.start,args.end):
    source=R/f'stages/motion/mesh-{frame:03}.npz';source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
    os.environ.update(LAVA_SOURCE=f'stages/motion/mesh-{frame:03}.npz',LAVA_PLUME=str(R/f'stages/motion/plume-{frame:03}.npz'))
    stem=R/f'renders/stage-motion-hero-{frame:04}-480-4spp';receipt=stem.with_suffix('.json')
    reuse=False
    if receipt.exists() and stem.with_suffix('.png').exists():
        record=json.loads(receipt.read_text());reuse=record.get('meshSha256')==source_sha and isinstance(record.get('volumeRender'),dict) and record['volumeRender'].get('densityScale')==.20
    if not reuse:main(frame,4,480,'hero','stage-motion')
    shutil.copy2(stem.with_suffix('.png'),out/f'{frame:03}.png');shutil.copy2(receipt,out/f'{frame:03}.json')
    print(json.dumps({'frame':frame,'file':str(out/f'{frame:03}.png'),'reusedValidatedSource':reuse}),flush=True);gc.collect()
