import os,json
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1')
import mitsuba as mi
mi.set_variant('scalar_rgb')
from pathlib import Path
from lava_volume_texture import test
result=test();(Path(__file__).resolve().parent/'lava-focus/crust-volume/texture-qa.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
