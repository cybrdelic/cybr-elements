from pathlib import Path
import cv2, json
from PIL import Image, ImageDraw

B = Path(__file__).resolve().parent
report = json.loads((B / 'lightning-report.json').read_text())
assert report['frames'] == 120
assert all(n['finite'] and n['connected'] for n in report['networks'])
assert all(r['finite'] for r in report['aerosol'])
old = cv2.VideoCapture(str(B / 'baseline/media/lightning-v4.mp4'))
new = cv2.VideoCapture(str(B / 'lightning-v5.mp4'))
sheet = Image.new('RGB', (1440, 1215))
draw = ImageDraw.Draw(sheet)
for row, f in enumerate([22, 39, 50]):
    for col, (cap, label) in enumerate([(old, 'Previous'), (new, 'Trial')]):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, im = cap.read()
        assert ok
        sheet.paste(Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB)).resize((720, 405)), (col * 720, row * 405))
        draw.text((col * 720 + 12, row * 405 + 12), f'{label} / {f/30:.2f}s', fill='white')
old.release()
new.release()
sheet.save(B / 'lightning-full-compare.jpg', quality=93)
print('Ten connected finite networks; sampled aerosol states finite; comparison saved.')
