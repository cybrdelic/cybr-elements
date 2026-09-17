"""Bounded CPU material proof of separated crust and molten volume."""
import os,argparse
for key in ['LAVA_MATTE','LAVA_RAKING_LIGHT','LAVA_BACK_LIGHT','LAVA_RUPTURE_MATERIAL']:os.environ.pop(key,None)
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',LAVA_SOURCE_CAMERA='1',LAVA_EXPOSURE='8.5',LAVA_LIGHT_GAIN='0.09',LAVA_NORMAL_SMOOTH='2',LAVA_SURFACE_MIX='1',LAVA_BUMP_SCALE='0.0018',LAVA_BUMP_TEXTURE='basalt-vesicles.png',LAVA_RENDER_BATCH='4',LAVA_BASELINE_MATERIAL='1',LAVA_CRUST_VOLUME='1')
from lava_lobes_render import main
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',default='crust-01');p.add_argument('--spp',type=int,default=8);p.add_argument('--width',type=int,default=640);p.add_argument('--view',choices=['hero','detail'],default='hero');p.add_argument('--revision',default='lava-crust-01');p.add_argument('--volume-pores',action='store_true');args=p.parse_args();assert args.width<=1600 and args.spp<=128
    if args.volume_pores:os.environ.update(LAVA_VOLUME_PORE='1',LAVA_BUMP_SCALE='0.00085')
    os.environ['LAVA_SOURCE']='crust-volume/'+args.source+'.npz';main(59,args.spp,args.width,args.view,args.revision)
