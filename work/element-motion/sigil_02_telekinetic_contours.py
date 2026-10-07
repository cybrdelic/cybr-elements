"""Extract near-silhouette pressure paths from the approved 02 source SDF."""
import json
from pathlib import Path

import cv2
import numpy as np
from skimage.measure import find_contours

ROOT = Path(__file__).resolve().parent
source = np.load(ROOT / 'sigil-02-v2/source.npz')
sdf = source['sdf']
lo, extent = source['lo'], source['extent']
height, width = sdf.shape
levels = (-.055, -.11, -.17)
result = {'source': 'sigil-02-v2/source.npz', 'levels': []}
for level in levels:
    paths = []
    for contour in find_contours(sdf, level):
        poly = np.asarray(contour[:, ::-1], dtype=np.float32).reshape(-1, 1, 2)
        simplified = cv2.approxPolyDP(poly, 1.7, closed=True).reshape(-1, 2)
        if len(simplified) < 6:
            continue
        world = [
            [round(float(lo[0] + x / (width - 1) * extent[0]), 4),
             round(float(lo[2] + y / (height - 1) * extent[2]), 4)]
            for x, y in simplified
        ]
        paths.append(world)
    result['levels'].append({'distance': level, 'paths': paths})
dest = ROOT / 'sigil-02-coherent/telekinesis-field-contours.json'
dest.write_text(json.dumps(result, separators=(',', ':')))
print(f'{dest}: {sum(len(level["paths"]) for level in result["levels"])} contours')
