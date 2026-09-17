from pathlib import Path
import json
import cv2
import numpy as np
from PIL import Image, ImageDraw

B = Path(__file__).resolve().parent
P = B.parents[2] / 'outputs/cybrdelic-type/elements/motion'
old = cv2.VideoCapture(str(B / 'baseline/media/earth.mp4'))
dust = cv2.VideoCapture(str(P / 'earth-dust.mp4'))
sheet = Image.new('RGB', (1440, 1215))
draw = ImageDraw.Draw(sheet)
for row, frame in enumerate([20, 50, 80]):
    old.set(cv2.CAP_PROP_POS_FRAMES, frame)
    ok, before = old.read()
    assert ok
    dust.set(cv2.CAP_PROP_POS_FRAMES, frame)
    ok, haze = dust.read()
    assert ok
    candidate = np.asarray(Image.open(B / f'earth-frames/{frame:04}.jpg'), dtype=np.float32) / 255
    haze = cv2.cvtColor(haze, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    candidate = 1 - (1 - candidate) * (1 - haze * .16)
    after = Image.fromarray(np.uint8(np.clip(candidate * 255, 0, 255)))
    sheet.paste(Image.fromarray(cv2.cvtColor(before, cv2.COLOR_BGR2RGB)).resize((720, 405)), (0, row * 405))
    sheet.paste(after.resize((720, 405)), (720, row * 405))
    draw.text((12, row * 405 + 12), f'Previous / {frame/30:.2f}s', fill='white')
    draw.text((732, row * 405 + 12), f'Trial / {frame/30:.2f}s', fill='white')
old.release()
dust.release()
sheet.save(B / 'earth-pilot-compare.jpg', quality=93)
original = json.loads(next((B / 'baseline').rglob('earth-report.json')).read_text())
trial = json.loads((B / 'earth-report.json').read_text())
assert original['births'] == trial['births']
assert original['camera'] == trial['camera']
print('Earth: 660 birth states and camera exactly match baseline; comparison saved.')
