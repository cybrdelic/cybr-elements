"""Reproducible CPU settings for the reviewed folded lava material."""
import os,argparse
for key in ['LAVA_MATTE','LAVA_RAKING_LIGHT']:os.environ.pop(key,None)
os.environ['LAVA_EXPOSURE']='8.0'
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',LAVA_SOURCE='lobes/lobes-05.npz',LAVA_LIGHT_GAIN='0.055',LAVA_NORMAL_SMOOTH='1',LAVA_SURFACE_MIX='1',LAVA_BUMP_SCALE='0.0028',LAVA_BUMP_TEXTURE='basalt-vesicles.png',LAVA_BACK_LIGHT='1')
from lava_lobes_render import main
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--view',choices=['hero','detail'],default='hero');p.add_argument('--width',type=int,default=1280);p.add_argument('--spp',type=int,default=8);p.add_argument('--revision',default='lava-continuous');a=p.parse_args()
    assert 64<=a.width<=1600 and 1<=a.spp<=128
    main(59,a.spp,a.width,a.view,a.revision)
