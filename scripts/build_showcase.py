"""Build the README GIF from the seven delivered movies; no simulation runs."""
from pathlib import Path
import json
import subprocess
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FILMS = ROOT / 'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
OUT = ROOT / 'docs/media'
TMP = ROOT / 'work/publication'
MOVIES = [('Fire', 'fire-02.mp4'), ('Water', 'water-02-r8.mp4'),
          ('Earth', 'earth-02-r6.mp4'), ('Air', 'air-02.mp4'),
          ('Ice', 'ice-02.mp4'), ('Lava', 'lava-02.mp4'),
          ('Lightning', 'lightning-02-r5.mp4')]

def run(args):
    result = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                             *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:])

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    def font(size):
        for path in ['C:/Windows/Fonts/arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
            if Path(path).exists():
                return ImageFont.truetype(path, size)
        return ImageFont.load_default(size=size)
    labels = Image.new('RGBA', (1120, 1400), (0, 0, 0, 0))
    d = ImageDraw.Draw(labels)
    for i, (name, _) in enumerate(MOVIES):
        x, y = (i % 2) * 560, (i // 2) * 350
        d.text((x + 18, y + 9), f'{i+1:02} / {name.upper()}', font=font(14), fill='#c8c8c8')
        d.line((x + 16, y + 349, x + 543, y + 349), fill='#202020')
    d.rectangle((560, 1050, 1120, 1400), fill='#000000')
    mark = Image.open(FILMS / 'artwork-02.png').convert('RGB')
    mark.thumbnail((475, 205))
    labels.paste(mark, (602 + (475-mark.width)//2, 1080 + (205-mark.height)//2))
    d = ImageDraw.Draw(labels)
    d.text((596, 1320), 'CYBRDELIC / ELEMENTAL SIGILS', font=font(18), fill='#dddddd')
    d.text((596, 1350), 'SEVEN MATERIALS. ONE MARK.', font=font(12), fill='#777777')
    labels.save(TMP / 'labels.png')
    args = []
    for _, name in MOVIES:
        args += ['-i', str(FILMS / name)]
    args += ['-f', 'lavfi', '-i', 'color=c=black:s=560x350:r=12:d=11.2',
             '-loop', '1', '-i', str(TMP / 'labels.png')]
    graph = []
    for i in range(7):
        graph.append(f'[{i}:v]fps=12,scale=560:315:flags=lanczos,setsar=1,'
                     f'pad=560:350:0:30:black,tpad=stop_mode=clone:stop_duration=2,trim=duration=11.2[v{i}]')
    layout = '|'.join(f'{(i%2)*560}_{(i//2)*350}' for i in range(8))
    graph += [f'{"".join(f"[v{i}]" for i in range(7))}[7:v]xstack=inputs=8:layout={layout}:fill=black[grid]',
              '[grid][8:v]overlay=0:0:shortest=1,format=yuv420p[out]']
    preview = TMP / 'showcase.mp4'
    run([*args, '-filter_complex_threads', '2', '-filter_complex', ';'.join(graph),
         '-map', '[out]', '-t', '11.2', '-an', '-c:v', 'libx264', '-crf', '17',
         '-preset', 'fast', '-threads', '2', str(preview)])
    run(['-i', str(preview), '-vf', 'fps=10,scale=840:1050:flags=lanczos,palettegen=max_colors=160:stats_mode=diff',
         '-frames:v', '1', str(TMP / 'palette.png')])
    run(['-i', str(preview), '-i', str(TMP / 'palette.png'), '-filter_complex',
         '[0:v]fps=10,scale=840:1050:flags=lanczos[v];[v][1:v]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle',
         '-loop', '0', str(OUT / 'elements-02.gif')])
    run(['-ss', '4.6', '-i', str(preview), '-frames:v', '1', '-q:v', '3',
         str(OUT / 'elements-02.jpg')])
    gif = Image.open(OUT / 'elements-02.gif')
    report = {'source': 'Existing delivered MP4s; CPU FFmpeg montage, no new simulation',
              'movies': dict(MOVIES), 'size': list(gif.size), 'frames': gif.n_frames,
              'durationSeconds': sum(gif.seek(i) or gif.info.get('duration', 0)
                                     for i in range(gif.n_frames)) / 1000,
              'bytes': (OUT / 'elements-02.gif').stat().st_size}
    (OUT / 'showcase.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))

if __name__ == '__main__':
    main()
