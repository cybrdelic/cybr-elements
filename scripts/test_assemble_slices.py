"""Disposable local integrity tests; synthetic clips are never delivery artifacts."""
from pathlib import Path
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image
import assemble_slices as assembly

SOURCE = Path(__file__).resolve().parent
sys.path.insert(0, str(SOURCE))
import rerender_slice as producer
import rerender_earth as earth_producer

COMMIT = 'a' * 40
SHA = 'b' * 64


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='cybr-disposable-assembly-test-')
        self.root = Path(self.temporary.name)
        self.contract = assembly.Contract(6, (64, 36))
        self.number = 0

    def tearDown(self):
        self.temporary.cleanup()

    def shard(self, start, end, *, kind='earth', contract=None, mutate=None):
        self.number += 1
        contract = contract or self.contract
        root = self.root / 'input' / f'shard-{self.number}'
        (root / 'frames').mkdir(parents=True)
        (root / 'reports' / kind).mkdir(parents=True)
        full_map = ([0, 1, 2, 2, 1, 0] if contract.frames == 6 else earth_producer.FRAME_MAP)
        summary = dict(version=1, kind=kind, start=start, end=end, frameIDs=list(range(start, end)),
                       sourceCommit=COMMIT, settings=producer.settings(kind, 4),
                       inputSha256={'work/original-input.npz': SHA},
                       sourceSha256={'scripts/rerender_slice.py': SHA},
                       cacheSha256={'fresh/full-solved-timeline': SHA},
                       physicsSha256={'fresh/full-solved-timeline': SHA},
                       frameSha256={}, reportSha256={}, frameMapping={},
                       freshPixels=True, oldFilmPixelsUsed=False, elapsedSeconds=1.5)
        summary['settings']['resolution'] = list(contract.resolution)
        if kind == 'earth':
            summary['frameMapping'] = {str(frame): full_map[frame] for frame in range(start, end)}
        for frame in range(start, end):
            path = root / 'frames' / f'{frame:04d}{".png" if kind == "earth" else ".jpg"}'
            image = Image.new('RGB', contract.resolution, ((frame * 37) % 255, (frame * 59) % 255, (frame * 83) % 255))
            image.save(path)
            summary['frameSha256'][path.relative_to(root).as_posix()] = assembly.sha256(path)
        report = root / 'reports' / kind / 'render-report.json'
        report.write_text(json.dumps({'complete': False, 'selectedOutputFrames': list(range(start, end)),
                                      'outputFrameMap': full_map} if kind == 'earth' else {'finite': True}))
        summary['reportSha256'][report.relative_to(root).as_posix()] = assembly.sha256(report)
        if mutate:
            mutate(summary, root)
        (root / 'slice-summary.json').write_text(json.dumps(summary))
        archive = self.root / f'shard-{self.number}.zip'
        with zipfile.ZipFile(archive, 'w') as bundle:
            for path in sorted(root.rglob('*')):
                if path.is_file():
                    bundle.write(path, path.relative_to(root).as_posix())
        return archive, root

    def assemble(self, archives, *, kind='earth', destination=None, digests=None):
        destination = destination or self.root / 'merged'
        digests = digests or {path.name: assembly.sha256(path) for path in archives}
        with contextlib.redirect_stdout(io.StringIO()):
            return assembly.assemble(archives, digests, kind, COMMIT, destination, threads=1, contract=self.contract)

    def test_zip_full_encode_decode_and_authored_earth_mapping_are_preserved(self):
        first, one = self.shard(0, 3)
        second, two = self.shard(3, 6)
        movie, summary = self.assemble([second, first])
        self.assertTrue(movie.is_file())
        self.assertTrue(summary['complete'])
        self.assertEqual(summary['frames'], 6)
        self.assertEqual(summary['encoding']['decodedFrames'], 6)
        self.assertTrue(summary['encoding']['faststartVerified'])
        self.assertEqual(summary['movieSha256'], assembly.sha256(movie))
        self.assertEqual(summary['frameMapping'], {'0': 0, '1': 1, '2': 2, '3': 2, '4': 1, '5': 0})
        self.assertTrue(summary['earthEditorialMappingPreserved'])
        for original in (one, two):
            for frame in (original / 'frames').iterdir():
                self.assertEqual(frame.read_bytes(), (movie.parent / 'frames' / frame.name).read_bytes())
        self.assertEqual(len(list((movie.parent / 'shards').rglob('slice-summary.json'))), 2)
        self.assertEqual(len(summary['reportSha256']), 2)
        self.assertTrue(first.is_file() and second.is_file())

    def test_extracted_directory_full_encode_decode_uses_actual_non_earth_schema(self):
        self.shard(0, 3, kind='water')
        self.shard(3, 6, kind='water')
        with contextlib.redirect_stdout(io.StringIO()):
            movie, summary = assembly.assemble([], {}, 'water', COMMIT, self.root / 'directory-merged',
                                               input_directory=self.root / 'input', threads=1, contract=self.contract)
        self.assertTrue(movie.is_file())
        self.assertEqual(summary['encoding']['decodedFrames'], 6)
        self.assertEqual(summary['nativeResolution'], [64, 36])
        self.assertNotIn('frameMapping', summary)
        self.assertTrue(all('artifactDirectory' in shard for shard in summary['shards']))

    def test_actual_producer_native_settings_are_accepted_for_all_five_elements(self):
        for kind in producer.KINDS:
            with self.subTest(kind=kind):
                contract = assembly.production_contract(kind)
                _, root = self.shard(0, 1, kind=kind, contract=contract)
                assembly.check_summary(root, kind, COMMIT, contract)

    def test_wrong_archive_digest_is_rejected_before_extraction(self):
        archive, _ = self.shard(0, 6)
        with self.assertRaisesRegex(ValueError, 'Archive digest mismatch'):
            self.assemble([archive], digests={archive.name: '0' * 64})
        self.assertFalse((self.root / 'merged').exists())

    def test_missing_frames_are_rejected_before_encoding(self):
        archive, _ = self.shard(0, 3)
        with patch.object(assembly, 'encode') as encode:
            with self.assertRaisesRegex(ValueError, 'full original frame sequence'):
                self.assemble([archive])
            encode.assert_not_called()

    def test_overlapping_delivered_frame_ids_are_rejected(self):
        first, _ = self.shard(0, 4)
        second, _ = self.shard(3, 6)
        with self.assertRaisesRegex(ValueError, 'overlap'):
            self.assemble([first, second])

    def test_all_source_input_cache_and_physics_identities_must_match(self):
        first, _ = self.shard(0, 3)
        for identity in assembly.IDENTITIES:
            with self.subTest(identity=identity):
                def change(summary, root):
                    summary[identity][next(iter(summary[identity]))] = 'c' * 64
                second, _ = self.shard(3, 6, mutate=change)
                with self.assertRaisesRegex(ValueError, 'Independent shards differ'):
                    self.assemble([first, second])

    def test_different_valid_thread_settings_are_rejected_across_shards(self):
        first, _ = self.shard(0, 3)
        second, _ = self.shard(3, 6, mutate=lambda s, r: s['settings'].update(threads=3))
        with self.assertRaisesRegex(ValueError, 'native settings'):
            self.assemble([first, second])

    def test_quality_reductions_and_wrong_material_storage_are_rejected(self):
        for kind, settings in [('earth', {'samples': 8}), ('ice', {'volumeFormat': 'native-vdb'}),
                               ('lava', {'volumeFormat': 'native-vdb'}), ('lightning', {'engine': 'CYCLES'})]:
            with self.subTest(kind=kind, settings=settings):
                archive, _ = self.shard(0, 6, kind=kind, mutate=lambda s, r: s['settings'].update(settings))
                with self.assertRaisesRegex(ValueError, 'production contract'):
                    self.assemble([archive], kind=kind)

    def test_per_frame_hash_mismatch_is_rejected(self):
        archive, _ = self.shard(0, 6, mutate=lambda s, r: s['frameSha256'].update({'frames/0000.png': '0' * 64}))
        with self.assertRaisesRegex(ValueError, 'Frame hash mismatch'):
            self.assemble([archive])

    def test_hashed_wrong_resolution_frame_is_rejected(self):
        def wrong_frame(summary, root):
            path = root / 'frames/0000.png'
            Image.new('RGB', (32, 18)).save(path)
            summary['frameSha256']['frames/0000.png'] = assembly.sha256(path)
        archive, _ = self.shard(0, 6, mutate=wrong_frame)
        with self.assertRaisesRegex(ValueError, 'native resolution'):
            self.assemble([archive])

    def test_preserved_report_hash_mismatch_is_rejected(self):
        def wrong_report(summary, root):
            (root / 'reports/earth/render-report.json').write_text('{}')
        archive, _ = self.shard(0, 6, mutate=wrong_report)
        with self.assertRaisesRegex(ValueError, 'Report hash mismatch'):
            self.assemble([archive])

    def test_extra_unreceipted_files_are_rejected(self):
        archive, _ = self.shard(0, 6, mutate=lambda s, r: (r / 'unknown.txt').write_text('unexpected'))
        with self.assertRaisesRegex(ValueError, 'unreceipted'):
            self.assemble([archive])

    def test_earth_mapping_must_match_preserved_original_full_map(self):
        archive, _ = self.shard(0, 6, mutate=lambda s, r: s['frameMapping'].update({'5': 3}))
        with self.assertRaisesRegex(ValueError, 'preserved full authored mapping'):
            self.assemble([archive])

    def test_different_source_commit_is_rejected(self):
        archive, _ = self.shard(0, 6, mutate=lambda s, r: s.update(sourceCommit='d' * 40))
        with self.assertRaisesRegex(ValueError, 'sourceCommit mismatch'):
            self.assemble([archive])

    def test_zip_traversal_is_rejected_without_writing_outside_staging(self):
        archive, _ = self.shard(0, 6)
        with zipfile.ZipFile(archive, 'a') as bundle:
            bundle.writestr('../outside.txt', 'bad')
        with self.assertRaisesRegex(ValueError, 'Unsafe archive'):
            self.assemble([archive])
        self.assertFalse((self.root / 'outside.txt').exists())

    def test_zip_symlinks_are_rejected(self):
        archive, _ = self.shard(0, 6)
        with zipfile.ZipFile(archive, 'a') as bundle:
            entry = zipfile.ZipInfo('link')
            entry.create_system = 3
            entry.external_attr = 0o120777 << 16
            bundle.writestr(entry, '/tmp/external')
        with self.assertRaisesRegex(ValueError, 'Nonregular'):
            self.assemble([archive])

    def test_duplicate_zip_members_are_rejected(self):
        archive, _ = self.shard(0, 6)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(archive, 'a') as bundle:
                bundle.writestr('slice-summary.json', '{}')
        with self.assertRaisesRegex(ValueError, 'Duplicate ZIP member'):
            self.assemble([archive])

    def test_extracted_artifact_symlink_is_rejected(self):
        _, root = self.shard(0, 6)
        (root / 'link').symlink_to(self.root / 'external')
        with self.assertRaisesRegex(ValueError, 'symbolic link'):
            assembly.assemble([], {}, 'earth', COMMIT, self.root / 'merged',
                              input_directory=self.root / 'input', contract=self.contract)

    def test_existing_deliveries_are_never_overwritten(self):
        archive, _ = self.shard(0, 6)
        destination = self.root / 'existing'
        destination.mkdir()
        film = destination / 'movie.mp4'
        film.write_bytes(b'existing real film')
        with self.assertRaisesRegex(ValueError, 'existing frames or films are preserved'):
            self.assemble([archive], destination=destination)
        self.assertEqual(film.read_bytes(), b'existing real film')

    def test_duplicate_and_nonfinite_json_are_rejected(self):
        path = self.root / 'bad.json'
        for contents in ['{"frames":1,"frames":2}', '{"elapsedSeconds":NaN}']:
            with self.subTest(contents=contents):
                path.write_text(contents)
                with self.assertRaises(ValueError):
                    assembly.read_json(path)


if __name__ == '__main__':
    unittest.main()
