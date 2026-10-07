"""Trim captured live sessions, verify files and build a downloadable gallery."""
import argparse, hashlib, html, json, pathlib, subprocess, zipfile

parser = argparse.ArgumentParser()
parser.add_argument('capture_dir', type=pathlib.Path)
parser.add_argument('--previous', type=pathlib.Path, action='append')
parser.add_argument('--all-solvers', action='store_true')
args = parser.parse_args()
review_file = args.capture_dir / 'visual-review.json'
reviews = json.loads(review_file.read_text(encoding='utf-8')) if review_file.exists() else {}
out = args.capture_dir / 'downloads'
out.mkdir(exist_ok=True)
entries = []
for source in (args.previous or []) + [args.capture_dir]:
    for report_file in sorted(source.glob('*-*.json' if args.all_solvers else 'original-*.json')):
        report = json.loads(report_file.read_text(encoding='utf-8'))
        if report.get('status') != 'completed' or not report.get('video'):
            continue
        preset = report['preset']
        clip_id = report['simulation']+'-'+preset if args.all_solvers else preset
        target = out / (clip_id + '.mp4')
        capture = report['recording']
        raw_duration = float(subprocess.check_output(['ffprobe','-v','error',
            '-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',report['video']],text=True).strip())
        # Chromium's video clock can lose startup time during GPU stalls.
        # Never seek beyond the actual file: retain the final live segment.
        trim_start = min(capture['startSeconds'],max(0,raw_duration-capture['durationSeconds']-.4))
        subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error',
            '-ss',str(trim_start),'-i',report['video'],
            '-t',str(capture['durationSeconds']),'-c:v','libx264','-preset','fast',
            '-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(target)], check=True)
        metadata = json.loads(subprocess.check_output(['ffprobe','-v','error',
            '-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,nb_frames:format=duration',
            '-of','json',str(target)], text=True))
        duration = float(metadata['format']['duration'])
        if duration < capture['durationSeconds'] - 1:
            raise RuntimeError(f'{preset}: incomplete clip ({duration} seconds)')
        if not metadata['streams'] or int(metadata['streams'][0].get('nb_frames',0)) < 20:
            raise RuntimeError(f'{preset}: missing video frames')
        subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error',
            '-ss',str(min(5,duration/2)),'-i',str(target),'-frames:v','1',
            '-vf','scale=640:-1',str(out/(clip_id+'.jpg'))], check=True)
        entries.append(dict(preset=preset,simulation=report['simulation'],file=target.name,
            trim_start_seconds=trim_start,raw_duration_seconds=raw_duration,
            duration=duration,metadata=metadata,bytes=target.stat().st_size,
            sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            clip_id=clip_id,renderer=report['performance']['renderer'],adapter=report['performance'].get('adapter'),
            source_report=str(report_file),visual_review=reviews.get(preset,'Not automatically graded')))

# A newer capture replaces the same solver/preset from the previous folder.
entries=list({e['clip_id']:e for e in entries}.values())

(out/'manifest.json').write_text(json.dumps(entries,indent=2),encoding='utf-8')
(out/'README.txt').write_text('Fire Studio live preset captures\n\n'
    'These MP4s were recorded from the evolving GPU solvers in headed Chrome.\n'
    'Startup was trimmed. No prerecorded source animation was substituted.\n'
    'Capture encoding is 25 fps; that is not a claim about solver performance.\n'
    'Renderer details, checksums and video metadata are in manifest.json.\n'
    'Visual quality is not automatically certified.\n',encoding='utf-8')
if args.all_solvers:
    for mode in sorted({e['simulation'] for e in entries}):
        clips = sorted([e for e in entries if e['simulation']==mode],key=lambda e:(e['preset']!='torch',e['preset']))
        listing=out/(mode+'-clips.txt')
        listing.write_text(''.join("file '"+e['file']+"'\n" for e in clips),encoding='utf-8')
        subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-f','concat','-safe','0',
            '-i',str(listing),'-c','copy','-movflags','+faststart',str(out/(mode+'-comparison.mp4'))],check=True)
cards = ''.join(f'<article><h2>{html.escape((e["simulation"]+" · "+e["preset"]).replace("-"," ").title())}</h2>'
    f'<video controls playsinline preload="metadata" poster="{e["clip_id"]}.jpg" src="{e["file"]}"></video>'
    f'<p><a download href="{e["file"]}">Download MP4</a> · {e["duration"]:.1f}s · {e["bytes"]/1e6:.1f} MB</p>'
    f'<p>{html.escape(e["visual_review"])}</p></article>' for e in entries)
gallery = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fire Studio · Recorded presets</title><style>
body{margin:0;background:#111;color:#ddd;font:16px system-ui;padding:32px;max-width:1440px;margin:auto}
h1{font-size:32px}h2{font-size:18px}a{color:#eeb570}p{line-height:1.6}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:24px}
article{background:#1b1b1b;padding:16px;border-radius:8px}video{width:100%;display:block}
</style><h1>Fire Studio · Recorded presets</h1>
<p>Live captures from the selected GPU engines in Chrome. <a download href="../fire-presets.zip">Download all clips</a></p>
<p>Reference examples: <a href="https://jangafx.com/software/embergen/download/free-vdb-animations">EmberGen fire plume, campfire and smoke assets</a> ·
<a href="https://www.youtube.com/watch?v=ZKflCgRQd8g">JangaFX fire and smoke training</a> ·
<a href="https://player.vimeo.com/video/739683075">SideFX fire shading presentation</a></p><main>'''+cards+'</main></html>'
(out/'index.html').write_text(gallery,encoding='utf-8')
archive=args.capture_dir/'fire-presets.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
    for item in out.iterdir():
        bundle.write(item,arcname='fire-presets/'+item.name)
print(json.dumps({'clips':len(entries),'archive':str(archive),'gallery':str(out/'index.html'),
    'totalBytes':sum(e['bytes'] for e in entries),'presets':[e['preset'] for e in entries]}))
