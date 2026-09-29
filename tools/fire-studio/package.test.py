"""Release graph, binary integrity and deployment-cache regression checks."""
import importlib.util
from pathlib import Path
import re
import subprocess
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('fire_package', Path(__file__).with_name('package.py'))
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class ReleaseChecks(unittest.TestCase):
    def test_plain_html_fetch_css_and_computed_script_references_are_checked(self):
        self.assertEqual(package.local_references(
            '<script src="studio.js?v=old"></script><link href="studio.css"><a href="./">', '.html'),
            ['studio.js?v=old', 'studio.css', './'])
        self.assertEqual(package.local_references(
            "import './start.js'; import('./runtime.js'); fetch('source/data.bin'); "
            "new URL('./picture.jpg', import.meta.url); const legacyScripts=['a.js','b.js']; "
            "fetch('./objects/'+name+'.bin');", '.js'),
            ['./runtime.js', './start.js', 'source/data.bin', './picture.jpg', 'a.js', 'b.js'])
        self.assertEqual(package.local_references('a{background:url(./a.png)}', '.css'), ['./a.png'])

    def test_subdirectory_deployment_rejects_escaping_and_root_urls(self):
        root = package.SOURCE
        for ref in ['../../../../secret.js', '/renderer.js']:
            with self.assertRaises(RuntimeError):
                package.dependency_for(root / 'index.html', ref, root)
        self.assertIsNone(package.dependency_for(root / 'fire.js', '/capture/test.json', root))
        self.assertEqual(package.dependency_for(root / 'pyro-gpu/index.html', '../?simulation=volume', root),
                         root.resolve() / 'index.html')

    def test_cache_keys_cannot_split_one_module_into_multiple_instances(self):
        source = ("import './presets.js?v=rc3'; import('./presets.js?v=rc5'); "
                  "import './fresh.js'; const legacyScripts=['helper.js']; "
                  "script.src=new URL(file+'?v=old',import.meta.url).href; "
                  "fetch('source/data.bin'); fetch(new URL(name, base)); "
                  "fetch('objects/'+name+'.rgba16.bin');").encode()
        with patch.object(package, 'runtime_bytes', return_value=source):
            path = package.SOURCE / 'runtime-loader.js'
            text = package.packaged_bytes(path, '0123456789abcdef').decode()
            self.assertEqual(text.count('./presets.js?v=0123456789abcdef'), 2)
            self.assertIn("'./fresh.js?v=0123456789abcdef'", text)
            self.assertIn("legacyScripts=['helper.js']", text)
            self.assertNotIn('?v=0123456789abcdef?v=', text)
            self.assertIn("fetch(new URL(name + '?v=0123456789abcdef', base))", text)
            self.assertIn("'.rgba16.bin?v=0123456789abcdef'", text)
            result = subprocess.run(['node', '--input-type=module', '--check'], input=text,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_content_fingerprint_changes_when_any_source_or_binary_changes(self):
        path = package.SOURCE / 'data.bin'
        with patch.object(package, 'runtime_bytes', side_effect=[b'first', b'second']):
            before = package.build_id([path])
            self.assertNotEqual(before, package.build_id([path]))

    def test_deployable_bytes_are_checked_against_manifest_and_extra_files_rejected(self):
        data = b'const ready = true;'
        manifest = {'version': 'test', 'build': 'test', 'openGates': [], 'files': [{
            'path': 'app.js', 'bytes': len(data), 'sha256': package.hashlib.sha256(data).hexdigest()}]}
        class MemoryArtifact:
            def __init__(self):
                self.files = {'app.js': data, 'release.json': package.json.dumps(manifest).encode()}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, name):
                return self.files[name]
            def namelist(self):
                return list(self.files)
        artifact = MemoryArtifact()
        with patch.object(package, '_directory_artifact', return_value=artifact):
            self.assertTrue(package.verify_artifact(package.REPO)['valid'])
            artifact.files['app.js'] = b'const stale = true;'
            with self.assertRaisesRegex(RuntimeError, 'do not match'):
                package.verify_artifact(package.REPO)
            artifact.files['app.js'] = data
            artifact.files['old-experiment.js'] = data
            with self.assertRaisesRegex(RuntimeError, 'unrecorded'):
                package.verify_artifact(package.REPO)

    def test_actual_release_graph_assets_and_transformed_modules(self):
        files = package.runtime_files()
        package.validate(files)
        token = package.build_id(files)
        selected = {p.resolve() for p in files}
        for path in files:
            if path.suffix != '.js':
                continue
            text = package.packaged_bytes(path, token).decode()
            result = subprocess.run(['node', '--input-type=module', '--check'], input=text,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, str(path) + result.stderr)
            for ref in package.local_references(text, '.js'):
                dependency = package.dependency_for(path, ref)
                if dependency is not None:
                    self.assertIn(dependency, selected, str(path) + ': ' + ref)
            self.assertFalse(re.search(r'[?&]v=studio-rc-', text), path)
        self.assertTrue(all('experiment' not in p.relative_to(package.SOURCE).as_posix()
                            and 'offline-flow-study' not in p.relative_to(package.SOURCE).as_posix()
                            for p in files))


if __name__ == '__main__':
    unittest.main()
