"""Bounded CPU regression tests; no real downloads or release writes occur."""
from pathlib import Path
import contextlib
import errno
import hashlib
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import fetch_assets as fetch
import prepare_publication as prepare
import publish_assets as publish


class AssetFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='cybr-asset-test-')
        self.root = Path(self.temporary.name)
        self.patches = [patch.object(module, 'ROOT', self.root) for module in (fetch, prepare, publish)]
        for item in self.patches:
            item.start()
        (self.root / 'docs').mkdir()
        self.payload = b'cybrdelic asset verification\n'
        self.manifest = {'version': 1, 'repository': 'cybrdelic/cybr-elements', 'tag': 'fixture',
            'assets': [{'path': 'outputs/example.bin', 'bytes': len(self.payload),
                        'sha256': hashlib.sha256(self.payload).hexdigest(),
                        'pack': 'example.zip', 'member': 'outputs/example.bin'}],
            'packs': [{'name': 'example.zip', 'uncompressedBytes': len(self.payload)}]}
        self.make_archive()
        self.save()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temporary.cleanup()

    def make_archive(self, entries=None):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as bundle:
            for name, payload in entries or [('outputs/example.bin', self.payload)]:
                bundle.writestr(name, payload)
        self.archive = data.getvalue()
        self.manifest['packs'][0].update(bytes=len(self.archive), sha256=hashlib.sha256(self.archive).hexdigest())

    def save(self):
        (self.root / 'docs/assets.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def restore(self, **options):
        with contextlib.redirect_stdout(io.StringIO()):
            return fetch.restore_assets(self.manifest, **options)

    def source(self):
        target = self.root / self.manifest['assets'][0]['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.payload)
        return target

    def stage(self):
        self.source()
        self.staged = json.loads(json.dumps(self.manifest))
        self.staged['tag'] = 'next-fixture'
        for pack in self.staged['packs']:
            pack.pop('bytes', None)
            pack.pop('sha256', None)
        self.plan = {'tracked': [], 'packs': [{'name': 'example.zip',
            'uncompressedBytes': len(self.payload), 'files': [{key: self.manifest['assets'][0][key]
                    for key in ('path', 'bytes', 'sha256')}]}]}
        directory = self.root / 'work/publication'
        directory.mkdir(parents=True)
        (directory / 'assets.json').write_text(json.dumps(self.staged), encoding='utf-8')
        (directory / 'plan.json').write_text(json.dumps(self.plan), encoding='utf-8')


class RestoreTests(AssetFixture):
    def test_restore_and_skip_verified_asset(self):
        with patch('urllib.request.urlopen', return_value=io.BytesIO(self.archive)) as request:
            self.assertEqual(self.restore(), 0)
            self.assertEqual((self.root / 'outputs/example.bin').read_bytes(), self.payload)
            self.assertEqual(self.restore(), 0)
            self.assertEqual(request.call_count, 1)
        self.assertEqual(list(self.root.glob('cybr-assets-*')), [])

    def test_verify_only_returns_missing_status_without_downloading(self):
        with patch('urllib.request.urlopen') as request:
            self.assertEqual(self.restore(verify_only=True), 1)
            self.source()
            self.assertEqual(self.restore(verify_only=True), 0)
            request.assert_not_called()
        self.assertEqual(list(self.root.glob('cybr-assets-*')), [])

    def test_existing_changed_file_is_preserved(self):
        target = self.source()
        target.write_bytes(b'local edit')
        with self.assertRaisesRegex(RuntimeError, 'Existing file differs'):
            self.restore()
        self.assertEqual(target.read_bytes(), b'local edit')

    def test_existing_directory_is_preserved(self):
        target = self.root / 'outputs/example.bin'
        target.mkdir(parents=True)
        with self.assertRaisesRegex(RuntimeError, 'Existing file differs'):
            self.restore()
        self.assertTrue(target.is_dir())

    def test_corrupt_pack_is_rejected_and_cleaned_up(self):
        with patch('urllib.request.urlopen', return_value=io.BytesIO(b'x' * len(self.archive))):
            with self.assertRaisesRegex(RuntimeError, 'Archive checksum mismatch'):
                self.restore()
        self.assertFalse((self.root / 'outputs/example.bin').exists())
        self.assertEqual(list(self.root.glob('cybr-assets-*')), [])

    def test_download_cannot_exceed_manifest_size(self):
        with patch('urllib.request.urlopen', return_value=io.BytesIO(self.archive + b'excess')):
            with self.assertRaisesRegex(RuntimeError, 'Byte count exceeds'):
                self.restore()
        self.assertEqual(list(self.root.glob('cybr-assets-*')), [])

    def test_truncated_download_is_rejected(self):
        with patch('urllib.request.urlopen', return_value=io.BytesIO(self.archive[:-1])):
            with self.assertRaisesRegex(RuntimeError, 'Byte count mismatch'):
                self.restore()

    def test_asset_checksum_is_verified_even_when_archive_is_valid(self):
        self.manifest['assets'][0]['sha256'] = '0' * 64
        with patch('urllib.request.urlopen', return_value=io.BytesIO(self.archive)):
            with self.assertRaisesRegex(RuntimeError, 'Asset checksum mismatch'):
                self.restore()
        self.assertFalse((self.root / 'outputs/example.bin').exists())
        self.assertEqual(list((self.root / 'outputs').glob('*.partial')), [])

    def test_zip_expansion_size_is_checked_before_copying(self):
        self.make_archive([('outputs/example.bin', self.payload * 100)])
        with patch('urllib.request.urlopen', return_value=io.BytesIO(self.archive)):
            with self.assertRaisesRegex(RuntimeError, 'Invalid archive member'):
                self.restore()
        self.assertFalse((self.root / 'outputs/example.bin').exists())

    def test_duplicate_zip_members_are_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                self.make_archive([('outputs/example.bin', self.payload)] * 2)
        with patch('urllib.request.urlopen', return_value=io.BytesIO(self.archive)):
            with self.assertRaisesRegex(RuntimeError, 'Duplicate archive member'):
                self.restore()

    def test_symbolic_link_zip_entry_is_rejected(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as bundle:
            entry = zipfile.ZipInfo('outputs/example.bin')
            entry.create_system = 3
            entry.external_attr = 0o120777 << 16
            bundle.writestr(entry, self.payload)
        self.archive = data.getvalue()
        self.manifest['packs'][0].update(bytes=len(self.archive), sha256=hashlib.sha256(self.archive).hexdigest())
        with patch('urllib.request.urlopen', return_value=io.BytesIO(self.archive)):
            with self.assertRaisesRegex(RuntimeError, 'Invalid archive member'):
                self.restore()

    def test_unsafe_paths_are_rejected(self):
        for value in ['../escape', '/absolute', 'C:/absolute', 'outputs/../../escape',
                      'outputs\\escape', '', '.', './outputs/a', 'outputs//a', 'outputs/a/', 'a\x00b',
                      'outputs/NUL.bin', 'outputs/COM1.mp4', 'outputs/name.', 'outputs/invalid?.bin']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                fetch.safe_target(value)

    def test_unsafe_pack_names_are_rejected_before_network_access(self):
        for value in ['../escape.zip', '/escape.zip', 'nested/escape.zip', 'escape\\pack.zip']:
            with self.subTest(value=value), patch('urllib.request.urlopen') as request:
                self.manifest['packs'][0]['name'] = value
                self.manifest['assets'][0]['pack'] = value
                with self.assertRaises(ValueError):
                    self.restore()
                request.assert_not_called()

    def test_duplicate_asset_paths_and_unknown_packs_are_rejected(self):
        self.manifest['assets'].append(dict(self.manifest['assets'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate asset path'):
            self.restore()
        self.manifest['assets'].pop()
        self.manifest['assets'][0]['pack'] = 'missing.zip'
        with self.assertRaisesRegex(ValueError, 'Unknown pack'):
            self.restore()

    def test_invalid_metadata_is_rejected(self):
        for key, value in [('bytes', -1), ('bytes', True), ('sha256', 'incorrect')]:
            original = self.manifest['assets'][0][key]
            self.manifest['assets'][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.restore()
            self.manifest['assets'][0][key] = original
        self.manifest['packs'][0].pop('sha256')
        with self.assertRaisesRegex(ValueError, 'integrity metadata'):
            self.restore()

    def test_malformed_pack_reference_is_rejected_without_a_type_error(self):
        self.manifest['assets'][0]['pack'] = []
        with self.assertRaisesRegex(ValueError, 'Unknown pack'):
            self.restore()

    def test_restore_supports_filesystems_without_hardlinks(self):
        with patch('urllib.request.urlopen', return_value=io.BytesIO(self.archive)), patch('fetch_assets.os.link', side_effect=OSError(errno.EOPNOTSUPP, 'unsupported')):
            self.restore()
        self.assertEqual((self.root / 'outputs/example.bin').read_bytes(), self.payload)

    def test_fallback_install_still_preserves_concurrent_local_files(self):
        target = self.source()
        target.write_bytes(b'preserve me')
        verified = self.root / 'verified.partial'
        verified.write_bytes(self.payload)
        with patch('fetch_assets.os.link', side_effect=OSError(errno.EOPNOTSUPP, 'unsupported')):
            with self.assertRaises(FileExistsError):
                fetch.install_verified(verified, target, len(self.payload))
        self.assertEqual(target.read_bytes(), b'preserve me')

    def test_fallback_install_removes_only_its_own_failed_copy(self):
        target = self.root / 'outputs/example.bin'
        target.parent.mkdir()
        verified = self.root / 'verified.partial'
        verified.write_bytes(self.payload)
        with patch('fetch_assets.os.link', side_effect=OSError(errno.EOPNOTSUPP, 'unsupported')):
            with self.assertRaisesRegex(RuntimeError, 'Byte count exceeds'):
                fetch.install_verified(verified, target, len(self.payload) - 1)
        self.assertFalse(target.exists())

    def test_destination_symlink_is_rejected(self):
        unrelated = self.root / 'local-file'
        unrelated.write_bytes(self.payload)
        (self.root / 'outputs').mkdir()
        (self.root / 'outputs/example.bin').symlink_to(unrelated)
        with self.assertRaisesRegex(ValueError, 'symbolic link'):
            self.restore()
        self.assertEqual(unrelated.read_bytes(), self.payload)

    def test_broken_destination_symlink_is_rejected(self):
        (self.root / 'outputs').mkdir()
        (self.root / 'outputs/example.bin').symlink_to(self.root / 'nonexistent')
        with self.assertRaisesRegex(ValueError, 'symbolic link'):
            self.restore()

    def test_shared_download_directory_is_never_followed(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root / '.asset-downloads').symlink_to(outside, target_is_directory=True)
            marker = Path(outside) / 'example.zip'
            marker.write_bytes(b'preserve me')
            with patch('urllib.request.urlopen', return_value=io.BytesIO(self.archive)):
                self.restore()
            self.assertEqual(marker.read_bytes(), b'preserve me')

    def test_local_file_created_during_restore_is_preserved(self):
        original_link = os.link
        def concurrent_edit(source, destination):
            Path(destination).write_bytes(b'new local edit')
            original_link(source, destination)
        with patch('urllib.request.urlopen', return_value=io.BytesIO(self.archive)), patch('fetch_assets.os.link', side_effect=concurrent_edit):
            with self.assertRaisesRegex(RuntimeError, 'appeared during restore'):
                self.restore()
        self.assertEqual((self.root / 'outputs/example.bin').read_bytes(), b'new local edit')

    def test_deduplicated_member_restores_every_alias(self):
        alias = dict(self.manifest['assets'][0], path='outputs/alias.bin')
        self.manifest['assets'].append(alias)
        with patch('urllib.request.urlopen', return_value=io.BytesIO(self.archive)) as request:
            self.restore()
        request.assert_called_once()
        self.assertEqual((self.root / 'outputs/alias.bin').read_bytes(), self.payload)

    def test_research_inputs_require_all_scope(self):
        self.manifest['assets'][0]['path'] = 'work/research/example.bin'
        with patch('urllib.request.urlopen', return_value=io.BytesIO(self.archive)) as request:
            self.restore()
            request.assert_not_called()
            self.restore(all_assets=True)
        self.assertEqual((self.root / 'work/research/example.bin').read_bytes(), self.payload)

    def test_release_tag_is_url_encoded(self):
        self.manifest['tag'] = 'version/one'
        with patch('urllib.request.urlopen', return_value=io.BytesIO(self.archive)) as request:
            self.restore()
        self.assertIn('/version%2Fone/example.zip', request.call_args.args[0].full_url)


class InventoryTests(AssetFixture):
    def test_clean_checkout_does_not_destroy_release_manifest(self):
        original = (self.root / 'docs/assets.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'released inputs are missing'):
            prepare.prepare('next-fixture')
        self.assertEqual((self.root / 'docs/assets.json').read_bytes(), original)
        self.assertFalse((self.root / 'work/publication').exists())

    def test_inventory_is_staged_and_published_docs_are_preserved(self):
        self.source()
        original = (self.root / 'docs/assets.json').read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            staged = prepare.prepare('next-fixture')
        self.assertEqual(staged['tag'], 'next-fixture')
        self.assertEqual(len(staged['assets']), 1)
        self.assertEqual((self.root / 'docs/assets.json').read_bytes(), original)
        self.assertTrue((self.root / 'work/publication/plan.json').is_file())
        self.assertTrue((self.root / 'work/publication/publication-scope.json').is_file())

    def test_recorded_release_tag_cannot_be_reused(self):
        self.source()
        with self.assertRaisesRegex(ValueError, 'new release tag'):
            prepare.prepare('fixture')

    def test_changed_input_is_inventoried_for_new_release_without_rewriting_history(self):
        self.source().write_bytes(b'changed')
        original = (self.root / 'docs/assets.json').read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            staged = prepare.prepare('next-fixture')
        self.assertEqual(staged['assets'][0]['sha256'], hashlib.sha256(b'changed').hexdigest())
        self.assertEqual((self.root / 'docs/assets.json').read_bytes(), original)

    def test_inventory_rejects_new_source_symlinks(self):
        self.source()
        (self.root / 'outputs/alias.bin').symlink_to(self.root / 'outputs/example.bin')
        with self.assertRaisesRegex(ValueError, 'Symbolic links'):
            prepare.prepare('next-fixture')


class PublicationTests(AssetFixture):
    def setUp(self):
        super().setUp()
        self.stage()
        self.remote = {}
        self.draft = True
        self.fail_upload = False
        self.wrong_digest = False
        self.uploads = 0

    def mock_gh(self, *args):
        if args[0] == 'api' and '/releases/tags/' in args[1]:
            return json.dumps({'id': 17, 'tag_name': 'next-fixture', 'draft': self.draft})
        if args[0] == 'api' and '/assets?' in args[1]:
            return json.dumps([list(self.remote.values())])
        if args[:2] == ('release', 'upload'):
            self.uploads += 1
            if self.fail_upload:
                raise RuntimeError('mock upload failure')
            target = Path(args[-1])
            self.remote[target.name] = {'name': target.name, 'size': target.stat().st_size,
                'digest': 'sha256:' + ('0' * 64 if self.wrong_digest else fetch.digest(target))}
            return ''
        self.fail(f'Unexpected gh call: {args}')

    def run_publish(self):
        with patch.object(publish, 'gh', side_effect=self.mock_gh), contextlib.redirect_stdout(io.StringIO()):
            return publish.publish()

    def test_only_draft_releases_can_receive_uploads(self):
        self.draft = False
        original = (self.root / 'docs/assets.json').read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'must exist and be a draft'):
            self.run_publish()
        self.assertEqual(self.uploads, 0)
        self.assertEqual((self.root / 'docs/assets.json').read_bytes(), original)
        self.assertFalse((self.root / 'work/publication/example.zip').exists())

    def test_complete_verified_upload_promotes_manifest(self):
        receipts = self.run_publish()
        self.assertEqual(self.uploads, 1)
        self.assertEqual(receipts['verifiedPacks'], 1)
        restored = json.loads((self.root / 'docs/assets.json').read_text())
        fetch.validate_manifest(restored, require_archive_integrity=True)
        self.assertEqual(restored['tag'], 'next-fixture')
        self.assertFalse((self.root / 'work/publication/example.zip').exists())

    def test_failed_upload_retains_archive_and_previous_manifest(self):
        self.fail_upload = True
        original = (self.root / 'docs/assets.json').read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'mock upload failure'):
            self.run_publish()
        self.assertEqual((self.root / 'docs/assets.json').read_bytes(), original)
        archive = self.root / 'work/publication/example.zip'
        self.assertTrue(archive.is_file())
        staged = json.loads((self.root / 'work/publication/assets.json').read_text())
        self.assertEqual(staged['packs'][0]['sha256'], fetch.digest(archive))
        # Resume must use the same verified archive instead of overwriting it.
        self.fail_upload = False
        self.run_publish()
        self.assertFalse(archive.exists())

    def test_remote_checksum_mismatch_preserves_previous_manifest(self):
        self.wrong_digest = True
        original = (self.root / 'docs/assets.json').read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'Remote upload verification failed'):
            self.run_publish()
        self.assertEqual((self.root / 'docs/assets.json').read_bytes(), original)
        self.assertTrue((self.root / 'work/publication/example.zip').exists())

    def test_conflicting_existing_remote_asset_is_never_clobbered(self):
        self.remote['example.zip'] = {'name': 'example.zip', 'size': 1, 'digest': 'sha256:' + '0' * 64}
        original = (self.root / 'docs/assets.json').read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'Existing remote pack differs'):
            self.run_publish()
        self.assertEqual(self.uploads, 0)
        self.assertEqual((self.root / 'docs/assets.json').read_bytes(), original)

    def test_unrecognized_local_archive_is_preserved(self):
        archive = self.root / 'work/publication/example.zip'
        archive.write_bytes(b'local archive')
        with self.assertRaisesRegex(RuntimeError, 'Unrecognized local archive'):
            self.run_publish()
        self.assertEqual(archive.read_bytes(), b'local archive')
        self.assertEqual(self.uploads, 0)

    def test_archives_are_reproducible_after_source_timestamp_changes(self):
        first, second = self.root / 'first.zip', self.root / 'second.zip'
        pack = self.plan['packs'][0]
        publish.build_pack(pack, first)
        os.utime(self.root / 'outputs/example.bin', (1800000000, 1800000000))
        publish.build_pack(pack, second)
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_changed_sources_are_rejected_before_upload(self):
        (self.root / 'outputs/example.bin').write_bytes(b'changed input')
        with self.assertRaisesRegex(RuntimeError, 'Source changed'):
            self.run_publish()
        self.assertEqual(self.uploads, 0)

    def test_plan_cannot_omit_manifest_members(self):
        self.plan['packs'][0]['files'] = []
        self.plan['packs'][0]['uncompressedBytes'] = 0
        with self.assertRaises(ValueError):
            publish.validate_plan(self.staged, self.plan)

    def test_plan_cannot_duplicate_members(self):
        self.plan['packs'][0]['files'] *= 2
        with self.assertRaisesRegex(ValueError, 'Plan source differs'):
            publish.validate_plan(self.staged, self.plan)

    def test_published_tag_cannot_be_reused_even_for_a_draft(self):
        self.staged['tag'] = 'fixture'
        (self.root / 'work/publication/assets.json').write_text(json.dumps(self.staged))
        with self.assertRaisesRegex(RuntimeError, 'recorded release is immutable'):
            self.run_publish()
        self.assertEqual(self.uploads, 0)


if __name__ == '__main__':
    unittest.main()
