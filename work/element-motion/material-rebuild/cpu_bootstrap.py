"""Auditable Blender entry point. No device discovery or GPU kernels."""
import os,sys,runpy
from pathlib import Path
os.environ['CYBR_CPU_PROOF']='1'
assert os.environ.get('CUDA_VISIBLE_DEVICES')=='-1'
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R))
script=Path(sys.argv[sys.argv.index('--script')+1]).resolve();assert script.parent==R
import bpy
from cpu_stage import configure
configure(bpy.context.scene)
def require_cpu(scene,*args):
 assert scene.render.engine=='CYCLES' and scene.cycles.device=='CPU','GPU rendering is prohibited by the active CPU contract'
 if hasattr(scene.cycles,'denoising_use_gpu'):assert not scene.cycles.denoising_use_gpu
bpy.app.handlers.render_pre.append(require_cpu)
runpy.run_path(str(script),run_name='__main__')
