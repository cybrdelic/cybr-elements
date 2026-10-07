"""Export the approved 02 silhouette and counters as Blender-ready paths."""
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
source = np.load(ROOT / 'sigil-02-v2/source.npz')
mask = np.uint8(source['sdf'] > 0)
lo, extent = source['lo'], source['extent']
height, width = mask.shape
contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
paths = []
for contour, relation in zip(contours, hierarchy[0]):
    simplified = cv2.approxPolyDP(contour, 1.2, closed=True).reshape(-1, 2)
    if len(simplified) < 4 or cv2.contourArea(contour) < 5:
        continue
    points = [[round(float(lo[0] + x / (width - 1) * extent[0]), 5),
               round(float(lo[2] + y / (height - 1) * extent[2]), 5)]
              for x, y in simplified]
    paths.append({'hole': bool(relation[3] >= 0), 'points': points})
dest = ROOT / 'sigil-02-coherent/telekinesis-solid-paths.json'
dest.write_text(json.dumps({'source': 'sigil-02-v2/source.npz', 'paths': paths},
                           separators=(',', ':')))
print(f'{dest}: {len(paths)} paths, {sum(path["hole"] for path in paths)} holes')
