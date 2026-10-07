"""Build a soft, glyph-bound density envelope for the psychic-medium study."""
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt

ROOT = Path(__file__).resolve().parent
data = np.load(ROOT / 'sigil-02-v2/source.npz')
mask = data['support'] > .5
lo, extent = data['lo'], data['extent']
height, width = mask.shape
x = np.linspace(lo[0], lo[0] + extent[0], width)[None, :]
z = np.linspace(lo[2], lo[2] + extent[2], height)[:, None]
outside = distance_transform_edt(
    ~mask, sampling=(extent[2] / (height - 1), extent[0] / (width - 1)))
near = np.exp(-(outside / .58) ** 2)
wide = np.exp(-(outside / 1.55) ** 2)
spatial = np.exp(-((x / 5.1) ** 4 + ((z - 2.7) / 2.55) ** 4))
envelope = np.where(~mask, (.82 * near + .18 * wide) * spatial, 0)
image = np.uint8(np.rint(np.clip(envelope, 0, 1) * 255))
dest = ROOT / 'sigil-02-coherent/telekinesis-psychic-envelope.png'
Image.fromarray(np.flipud(image)).save(dest)
print(f'{dest}: {width}x{height}, max={float(envelope.max()):.3f}')
