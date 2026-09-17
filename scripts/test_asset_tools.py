"""Bounded CPU checks for release restoration and path/checksum protection."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import shutil
import uuid
import unittest
from unittest.mock import patch
import zipfile
import fetch_assets as fetch

class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.test_parent = Path(__file__).resolve().parents[1] / '.asset-downloads'
        self.test_parent.mkdir(exist_ok=True)
        self.root = (self.test_parent / ('asset-test-' + uuid.uuid4().hex)).resolve()
        self.root.mkdir()
        self.old_root = fetch.ROOT
        fetch.ROOT = self.root
        (self.root/'docs').mkdir()
        self.payload = b'cybrdelic asset verification\n'
        self.data = io.BytesIO()
        with zipfile.ZipFile(self.data, 'w') as z:
            z.writestr('outputs/example.bin', self.payload)
        self.archive = self.data.getvalue()
        self.manifest = {'repository':'cybrdelic/cybr-elements', 'tag':'fixture',
            'assets':[{'path':'outputs/example.bin','bytes':len(self.payload),
                       'sha256':hashlib.sha256(self.payload).hexdigest(),
                       'pack':'example.zip','member':'outputs/example.bin'}],
            'packs':[{'name':'example.zip','bytes':len(self.archive),
                      'uncompressedBytes':len(self.payload),
                      'sha256':hashlib.sha256(self.archive).hexdigest()}]}
        self.save()

    def tearDown(self):
        fetch.ROOT = self.old_root
        assert self.root.is_relative_to(self.test_parent.resolve())
        shutil.rmtree(self.root)

    def save(self):
        (self.root/'docs/assets.json').write_text(json.dumps(self.manifest))

    def run_fetch(self, *args):
        with patch('sys.argv', ['fetch_assets.py','--site',*args]), contextlib.redirect_stdout(io.StringIO()):
            fetch.main()

    def test_restore_and_skip_verified_asset(self):
        with patch('urllib.request.urlopen', return_value=io.BytesIO(self.archive)) as request:
            self.run_fetch()
            self.assertEqual((self.root/'outputs/example.bin').read_bytes(), self.payload)
            self.run_fetch()
            self.assertEqual(request.call_count, 1)
        self.assertFalse((self.root/'.asset-downloads/example.zip').exists())

    def test_existing_changed_file_is_preserved(self):
        (self.root/'outputs').mkdir()
        p = self.root/'outputs/example.bin'
        p.write_bytes(b'local edit')
        with self.assertRaises(SystemExit):
            self.run_fetch()
        self.assertEqual(p.read_bytes(), b'local edit')

    def test_corrupt_pack_is_rejected(self):
        with patch('urllib.request.urlopen', return_value=io.BytesIO(b'bad archive')):
            with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                self.run_fetch()
        self.assertFalse((self.root/'outputs/example.bin').exists())

    def test_unsafe_paths_are_rejected(self):
        for path in ['../escape','/absolute','C:/absolute','outputs/../../escape','outputs\\escape']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                fetch.safe_target(path)

if __name__ == '__main__':
    unittest.main()
