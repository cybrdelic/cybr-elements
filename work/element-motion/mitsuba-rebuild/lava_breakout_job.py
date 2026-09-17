"""Bounded CPU renderer settings for the rupture material study."""
import os,argparse
for key in ['LAVA_MATTE','LAVA_RAKING_LIGHT']:os.environ.pop(key,None)
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',LAVA_EXPOSURE='24.0',LAVA_LIGHT_GAIN='0.006',LAVA_NORMAL_SMOOTH='2',LAVA_SURFACE_MIX='1',LAVA_BUMP_SCALE='0.0007',LAVA_BUMP_TEXTURE='basalt-vesicles.png',LAVA_BACK_LIGHT='1',LAVA_SOURCE_CAMERA='1',LAVA_RENDER_BATCH='4')
from lava_lobes_render import main
os.environ['LAVA_RUPTURE_MATERIAL']='1'
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',default='rupture-02');p.add_argument('--view',choices=['hero','detail'],default='hero');p.add_argument('--width',type=int,default=640);p.add_argument('--spp',type=int,default=8);p.add_argument('--revision',default='lava-rupture');a=p.parse_args();assert a.width<=1600 and a.spp<=128
    os.environ['LAVA_SOURCE']='breakout/'+a.source+'.npz';main(59,a.spp,a.width,a.view,a.revision)
