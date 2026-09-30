"""Protect review deliveries against corrupt pixels, stale shards and bad timing."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from PIL import Image
from assemble_studio_reviews import ELEMENTS, collect, assemble, digest


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='cybr-export-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = self.root/'shards'; self.inputs.mkdir()
        for kind in ELEMENTS:
            self.shard(kind, kind, [0, 2, 4], hero=True)

    def shard(self, name, kind, frames, hero=False, source='same-renderer'):
        folder = self.inputs/name; folder.mkdir()
        hashes = {}
        for frame in frames:
            image = folder/f'{frame:04d}.png'
            Image.new('RGB', (16, 16), (frame*12, 20, 30)).save(image)
            hashes[str(frame)] = digest(image)
        report = {'kind': kind, 'frames': frames, 'resolution': [16, 16], 'native_fps': 30,
                  'fresh_rendered_pixels': True, 'old_film_pixels_used': False,
                  'complete_native_film': False, 'image_sha256': hashes,
                  'source_sha256': {f'scripts/{f}.py': source for f in
                                    ('studio_scene', 'render_studio', 'studio_lava')}, 'hero': None}
        if hero:
            Image.new('RGB', (16, 16), 'black').save(folder/'hero.png')
            report['hero'] = {'native_frame': 2, 'resolution': [16, 16],
                              'image_sha256': digest(folder/'hero.png')}
        path = folder/'review-report.json'
        path.write_text(json.dumps(report))
        return path

    def test_changed_rendered_pixels_are_rejected(self):
        Image.new('RGB', (16, 16), 'red').save(self.inputs/'water/0000.png')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            collect([self.inputs])

    def test_missing_native_time_is_rejected(self):
        path = self.inputs/'water/review-report.json'
        r = json.loads(path.read_text())
        (path.parent/'0004.png').rename(path.parent/'0006.png')
        r['frames'][-1] = 6; r['image_sha256']['6'] = r['image_sha256'].pop('4')
        path.write_text(json.dumps(r))
        with self.assertRaisesRegex(ValueError, 'timeline has a gap'):
            collect([self.inputs])

    def test_different_optical_revision_cannot_be_spliced_in(self):
        self.shard('water-later', 'water', [6, 8], source='stale-optics')
        with self.assertRaisesRegex(ValueError, 'Mixed renderer revisions'):
            collect([self.inputs])

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_real_encoder_retains_native_elapsed_time(self):
        out = self.root/'delivery'
        with contextlib.redirect_stdout(io.StringIO()):
            assemble(collect([self.inputs]), out)
        for video in out.glob('*.mp4'):
            result = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=nb_frames,avg_frame_rate:format=duration', '-of', 'json', str(video)], text=True))
            self.assertEqual(result['streams'][0]['nb_frames'], '3')
            self.assertEqual(result['streams'][0]['avg_frame_rate'], '15/1')
            self.assertAlmostEqual(float(result['format']['duration']), .2, places=5)


if __name__ == '__main__':
    unittest.main()
