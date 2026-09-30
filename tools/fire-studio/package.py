"""Package only Fire Studio's runtime assets. No historical experiments or QA captures."""
import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qsl, urlencode
from zipfile import ZipFile, ZIP_DEFLATED

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / 'outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'
VERSION = '0.1.0-rc.9'
TEXT_EXTENSIONS = {'.js', '.html', '.css', '.svg', '.md', '.json'}
OPEN_GATES = [
    'Live browser motion and sustained completed-frame performance on the demo GPU',
    'Mobile GPU memory, compatibility and sustained performance',
    'Original/offline detail comparison and Volume smoke/flame motion review',
]


def runtime_bytes(path):
    data = path.read_bytes()
    # GitHub Pages serves Git blobs, which normalize text line endings.
    # Hash and write the same canonical bytes on Windows and Linux.
    if path.suffix in TEXT_EXTENSIONS:
        data = data.replace(b'\r\n', b'\n')
    return data


def runtime_files():
    files = [SOURCE / 'index.html', SOURCE / 'studio.css', SOURCE / 'icon.svg', SOURCE / 'README.md']
    files += list(SOURCE.glob('*.js'))
    files += list((SOURCE / 'pyro-gpu').glob('*.js'))
    files += [SOURCE / 'pyro-gpu/library.css', SOURCE / 'pyro-gpu/index.html']
    files += [SOURCE / 'source' / name for name in ['source-native.rgba8.bin', 'halfwidth-native.r8.bin']]
    files += list((SOURCE / 'pyro-gpu/source-previews').glob('*.jpg'))
    files += list((SOURCE / 'pyro-gpu/objects').glob('*.rgba16.bin'))
    files += list((SOURCE / 'pyro-gpu/objects').glob('*.jpg'))
    files += [SOURCE / 'pyro-gpu/objects/manifest.json']
    tree = SOURCE / 'pyro-gpu/objects/forest-tree'
    files += [tree / name for name in ['source-space.js', 'manifest.json', 'vertices.bin', 'indices.bin', 'bark-color.png', 'bark-micro.png', 'preview.jpg']]
    return sorted(set(files))


def local_references(text, suffix):
    """Literal file references, including URLs without an initial './'.

    Computed object names and preview URLs are checked through the exported
    preset catalog and binary manifests below. Capture endpoints are APIs.
    """
    refs = re.findall(r'''(?:\bfrom\s*|\bimport\s*\(\s*)['"]([^'"]+)['"]''', text)
    refs += re.findall(r'''\bimport\s*['"]([^'"]+)['"]''', text)
    refs += re.findall(r'''(?:\bfetch\s*\(\s*|\bnew URL\s*\(\s*)['"]([^'"]+)['"]\s*[,)]''', text)
    if suffix == '.html':
        refs += re.findall(r'''(?:src|href)\s*=\s*["']([^"']+)["']''', text)
    if suffix == '.css':
        refs += re.findall(r'''url\(\s*['"]?([^'"\s)]+)['"]?\s*\)''', text)
    # The Original runtime loads these classic shader modules by name.
    script_list = re.search(r'\blegacyScripts\s*=\s*\[([^]]*)\]', text)
    if script_list:
        refs += re.findall(r'''['"]([^'"]+\.js)['"]''', script_list[1])
    return list(dict.fromkeys(refs))


def dependency_for(path, ref, root=SOURCE):
    url = urlsplit(ref)
    if url.scheme or url.netloc or not url.path:
        return None
    if url.path.startswith('/capture/'):
        return None
    if url.path.startswith('/'):
        raise RuntimeError('Root-relative runtime URL cannot be deployed under /firesim/: ' + ref)
    dependency = (path.parent / unquote(url.path)).resolve()
    if not dependency.is_relative_to(root.resolve()):
        raise RuntimeError('Runtime URL escapes the package: ' + ref)
    if dependency.is_dir() or url.path.endswith('/'):
        # A directory used as the base of new URL() is not an index-page asset.
        if path.suffix == '.html':
            return dependency / 'index.html'
        return None
    return dependency


def catalog_assets():
    script = """import {FIRE_PRESETS} from %s;
import {fileURLToPath} from 'node:url';
console.log(JSON.stringify(FIRE_PRESETS.flatMap(p => [
  ...(p.preview ? [fileURLToPath(p.preview)] : []),
  ...(p.object ? [fileURLToPath(new URL('./objects/'+p.object+'.rgba16.bin', %s))] : [])
])));""" % (json.dumps((SOURCE / 'pyro-gpu/presets.js').as_uri()),
              json.dumps((SOURCE / 'pyro-gpu/presets.js').as_uri()))
    result = subprocess.run(['node', '--input-type=module', '-e', script],
                            capture_output=True, text=True, check=True)
    return [Path(p).resolve() for p in json.loads(result.stdout)]


def validate_binary_assets(selected):
    problems = []
    manifest = json.loads((SOURCE / 'pyro-gpu/objects/manifest.json').read_text())
    records = [(SOURCE / 'pyro-gpu/objects' / (m['id'] + '.rgba16.bin'), m)
               for m in manifest['models']]
    tree = SOURCE / 'pyro-gpu/objects/forest-tree'
    records += [(tree / name, entry) for name, entry in
                json.loads((tree / 'manifest.json').read_text())['files'].items()
                if (tree / name).resolve() in selected]
    for path, entry in records:
        if path.resolve() not in selected:
            problems.append('Asset manifest references omitted ' + str(path.relative_to(SOURCE)))
            continue
        data = path.read_bytes()
        if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            problems.append('Binary asset differs from its manifest: ' + str(path.relative_to(SOURCE)))
    for name, expected in [('source-native.rgba8.bin', 896 * 504 * 4),
                           ('halfwidth-native.r8.bin', 896 * 504)]:
        path = SOURCE / 'source' / name
        if path.stat().st_size != expected:
            problems.append('Invalid native source texture byte count: ' + name)
    return problems


def build_id(files, snapshot=None):
    digest = hashlib.sha256()
    digest.update(VERSION.encode())
    for path in files:
        digest.update(path.relative_to(SOURCE).as_posix().encode())
        digest.update(b'\0')
        digest.update(snapshot[path] if snapshot is not None else runtime_bytes(path))
    return digest.hexdigest()[:16]


def version_url(ref, token):
    url = urlsplit(ref)
    if url.scheme or url.netloc or not url.path or url.path.endswith('/'):
        return ref
    if Path(url.path).suffix not in {'.js', '.css', '.svg', '.bin', '.png', '.jpg'}:
        return ref
    query = dict(parse_qsl(url.query, keep_blank_values=True))
    query['v'] = token
    return url._replace(query=urlencode(query)).geturl()


def packaged_bytes(path, token, data=None):
    """Use one content-derived cache key for every static module/asset URL.

    This operates only on the package, preserving editable runtime sources.
    One key also prevents duplicate ES module instances from mixed rc versions.
    """
    data = runtime_bytes(path) if data is None else data
    if path.suffix not in {'.js', '.html', '.css'}:
        return data
    text = data.decode('utf-8-sig')
    # Also covers the runtime-loader's computed classic-script URL suffix.
    text = re.sub(r'([?&]v=)[A-Za-z0-9_.-]+', lambda m: m[1] + token, text)
    script_list = re.search(r'\blegacyScripts\s*=\s*\[([^]]*)\]', text)
    computed_scripts = set(re.findall(r'''['"]([^'"]+\.js)['"]''', script_list[1])) if script_list else set()
    for ref in local_references(text, path.suffix):
        if ref in computed_scripts:
            continue
        revised = version_url(ref, token)
        if revised != ref:
            text = text.replace('"' + ref + '"', '"' + revised + '"')
            text = text.replace("'" + ref + "'", "'" + revised + "'")
            if path.suffix == '.css':
                text = text.replace('url(' + ref + ')', 'url(' + revised + ')')
    # These dynamic names are restricted by the validated object catalog.
    text = text.replace("'.rgba16.bin'", "'.rgba16.bin?v=" + token + "'")
    text = text.replace("'.jpg'", "'.jpg?v=" + token + "'")
    # ForestMesh constructs URLs through a local helper; version its dynamic
    # binary, JSON and texture requests without changing the manifest lookup key.
    text = text.replace('fetch(new URL(name, base))',
                        "fetch(new URL(name + '?v=" + token + "', base))")
    return text.encode('utf-8')


def reachable_scripts(files):
    selected = {p.resolve() for p in files}
    pending = [SOURCE / 'index.html', SOURCE / 'pyro-gpu/index.html']
    visited = set()
    while pending:
        path = pending.pop().resolve()
        if path in visited or path not in selected:
            continue
        visited.add(path)
        if path.suffix not in {'.js', '.html', '.css'}:
            continue
        for ref in local_references(path.read_text(encoding='utf-8-sig'), path.suffix):
            try:
                dependency = dependency_for(path, ref)
            except RuntimeError:
                continue  # validate() supplies the useful dependency error.
            if dependency is not None:
                pending.append(dependency)
    return visited


def validate(files):
    missing = [str(p.relative_to(SOURCE)) for p in files if not p.is_file()]
    if missing:
        raise RuntimeError('Missing runtime assets: ' + ', '.join(missing))
    selected = set(p.resolve() for p in files)
    problems = []
    for path in files:
        if path.suffix == '.js':
            result = subprocess.run(['node', '--check', str(path)], capture_output=True, text=True)
            if result.returncode:
                problems.append(str(path.relative_to(SOURCE)) + ': ' + result.stderr[:500])
        if path.suffix not in ['.js', '.html', '.css']:
            continue
        text = path.read_text(encoding='utf-8-sig')
        for ref in local_references(text, path.suffix):
            try:
                dependency = dependency_for(path, ref)
            except RuntimeError as error:
                problems.append(str(path.relative_to(SOURCE)) + ': ' + str(error))
                continue
            if dependency is not None and dependency not in selected:
                problems.append(str(path.relative_to(SOURCE)) + ' references omitted ' + ref)
    for path in catalog_assets():
        if path not in selected:
            problems.append('Preset catalog references omitted ' + str(path.relative_to(SOURCE)))
    problems += validate_binary_assets(selected)
    reachable = reachable_scripts(files)
    for path in files:
        if path.suffix == '.js' and path.resolve() not in reachable:
            problems.append('Unused script selected for release: ' + str(path.relative_to(SOURCE)))
    if problems:
        raise RuntimeError('\n'.join(problems))
    validate_startup(SOURCE)


def validate_startup(root):
    """Execute boot, transition and reset behavior against the selected runtime."""
    environment = dict(os.environ, FIRE_STUDIO_ROOT=str(root.resolve()))
    for runner in ['original-startup.test.mjs', 'control-transition.test.mjs', 'volume-reset.test.mjs', 'volume-lighting.test.mjs']:
        result = subprocess.run(
            ['node', str(Path(__file__).with_name(runner))],
            env=environment, capture_output=True, text=True, timeout=30,
        )
        if result.returncode:
            details = (result.stdout + result.stderr)[-10000:]
            raise RuntimeError(runner + ' failed:\n' + details)


def verify_artifact(destination):
    """Verify the bytes that will be deployed, rather than the editable source."""
    destination = destination.resolve()
    with ZipFile(destination) if destination.suffix == '.zip' else _directory_artifact(destination) as artifact:
        manifest = json.loads(artifact.read('release.json'))
        expected = {'release.json'}
        for entry in manifest['files']:
            name = entry['path']
            path = Path(name)
            if path.is_absolute() or '..' in path.parts or ':' in name or name in expected:
                raise RuntimeError('Unsafe or repeated release path: ' + name)
            expected.add(name)
            data = artifact.read(name)
            if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
                raise RuntimeError('Release bytes do not match the manifest: ' + name)
            if path.suffix == '.js':
                result = subprocess.run(['node', '--input-type=module', '--check'],
                                        input=data.decode('utf-8-sig'), capture_output=True, text=True)
                if result.returncode:
                    raise RuntimeError(name + ': ' + result.stderr[:500])
        names = artifact.namelist()
        if len(names) != len(set(names)) or set(names) != expected:
            raise RuntimeError('Release contains missing, duplicate or unrecorded files.')
    return {'valid': True, 'version': manifest['version'], 'build': manifest['build'],
            'files': len(manifest['files']), 'openGates': manifest['openGates']}


class _directory_artifact:
    def __init__(self, root):
        self.root = root

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, name):
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root):
            raise RuntimeError('Release path escapes artifact directory: ' + name)
        return path.read_bytes()

    def namelist(self):
        return [p.relative_to(self.root).as_posix() for p in self.root.rglob('*') if p.is_file()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--verify', type=Path, help='Verify a previously built runtime directory or ZIP.')
    parser.add_argument('--out', type=Path, default=REPO / 'releases' / ('fire-studio-' + VERSION))
    args = parser.parse_args()
    if args.verify:
        verification = verify_artifact(args.verify)
        if args.verify.is_dir():
            validate_startup(args.verify)
            verification['originalStartup'] = 'passed-dom-webgl-fixture'
            verification['transitionsAndResets'] = 'passed-runtime-contract-fixtures'
        print(json.dumps(verification))
        return
    files = runtime_files()
    validate(files)
    # Read each source once, so concurrent edits cannot make the copied bytes
    # differ from the manifest generated earlier in this build.
    snapshot = {p: runtime_bytes(p) for p in files}
    token = build_id(files, snapshot)
    payloads = {p: packaged_bytes(p, token, snapshot[p]) for p in files}
    entries = [{'path': p.relative_to(SOURCE).as_posix(), 'bytes': len(payloads[p]),
                'sha256': hashlib.sha256(payloads[p]).hexdigest()} for p in files]
    if args.check:
        print(json.dumps({'valid': True, 'version': VERSION, 'build': token,
                          'files': len(entries), 'bytes': sum(e['bytes'] for e in entries)}))
        return
    destination = args.out.resolve()
    if not destination.is_relative_to(REPO.resolve()):
        raise RuntimeError('Output must stay inside the repository.')
    archive = Path(str(destination) + '.zip')
    if destination.exists() or archive.exists():
        raise RuntimeError('Output already exists. Choose a new --out path; existing builds are preserved.')
    destination.mkdir(parents=True)
    for source, entry in zip(files, entries):
        target = destination / entry['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payloads[source])
    (destination / 'release.json').write_text(json.dumps({
        'version': VERSION, 'build': token, 'status': 'release-candidate', 'entry': 'index.html',
        'files': entries, 'openGates': OPEN_GATES,
    }, indent=2), encoding='utf-8', newline='\n')
    validate_startup(destination)
    with ZipFile(archive, 'w', ZIP_DEFLATED) as bundle:
        for file in sorted(destination.rglob('*')):
            if file.is_file():
                bundle.write(file, file.relative_to(destination))
    print(json.dumps({'directory': str(destination), 'archive': str(archive), 'files': len(entries), 'archiveBytes': archive.stat().st_size}))


if __name__ == '__main__':
    main()
