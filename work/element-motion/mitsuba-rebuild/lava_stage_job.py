"""One bounded, reproducible CPU stage render."""
import os,argparse
from pathlib import Path
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',LAVA_SOURCE_CAMERA='1',LAVA_LIGHT_GAIN='.09',LAVA_EXPOSURE='8.5',LAVA_NORMAL_SMOOTH='2',LAVA_VOLUME_PORE='1',LAVA_BUMP_SCALE='.00085',LAVA_RENDER_BATCH='4',LAVA_BASELINE_MATERIAL='1')
from lava_lobes_render import main
R=Path(__file__).resolve().parent/'lava-focus'
p=argparse.ArgumentParser();p.add_argument('stage',choices=['magma','lava','cooling','basalt','obsidian']);p.add_argument('--width',type=int,default=640);p.add_argument('--spp',type=int,default=8);p.add_argument('--frame',type=int);a=p.parse_args()
assert a.width<=1600 and a.spp<=64
os.environ['LAVA_STAGE']=a.stage;os.environ['LAVA_SOURCE']='stages/'+a.stage+'.npz'
if a.stage in ['magma','lava']:os.environ.update(LAVA_EXPOSURE='4.5',LAVA_LIGHT_GAIN='.10')
if a.stage=='obsidian':os.environ.update(LAVA_EXPOSURE='8.5',LAVA_LIGHT_GAIN='.025')
if a.frame is not None:
 os.environ.update(LAVA_SOURCE=f'stages/motion/mesh-{a.frame:03}.npz',LAVA_PLUME=str(R/f'stages/motion/plume-{a.frame:03}.npz'),LAVA_EXPOSURE='4.5',LAVA_LIGHT_GAIN='.14',LAVA_NORMAL_SMOOTH='1',LAVA_BUMP_SCALE='.0006')
main(a.frame or 0,a.spp,a.width,'hero',('stage-'+a.stage) if a.frame is None else 'stage-motion')
