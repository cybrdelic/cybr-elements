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
VERSION = '0.1.0-rc.20'
TEXT_EXTENSIONS = {'.js', '.html', '.css', '.svg', '.md', '.json'}
WOOD_DIRECTORIES = ['forest-tree/structure', 'logs', 'house', 'wood-sigil']
OPEN_GATES = [
    'Live browser motion and sustained completed-frame performance on the demo GPU',
    'Mobile GPU memory, compatibility and sustained performance',
    'Original/offline detail comparison and Volume smoke/flame motion review',
    'Experimental adaptive flow, brick pool and precise receivers: complete-frame speed, quality and memory replacement gates',
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
    files += [tree / name for name in ['source-space.js', 'manifest.json', 'vertices.bin', 'indices.bin', 'bark-color.png', 'bark-micro.png', 'bark-roughness.png', 'preview.jpg', 'wood-solid.rgba16.bin', 'flux-metadata.rgba32.bin', 'flux-metadata.rgba32.bin.json']]
    for directory in WOOD_DIRECTORIES:
        base = SOURCE / 'pyro-gpu/objects' / directory
        files.append(base / 'manifest.json')
        files += [path for path, _ in manifest_records(base)]
    return sorted(set(files))


def local_references(text, suffix):
    """Literal file references, including URLs without an initial './'.

    Computed object names and preview URLs are checked through the exported
    preset catalog and binary manifests below. Capture endpoints are APIs.
    """
    refs = re.findall(r'''(?:\bfrom\s*|\bimport\s*\(\s*)['"]([^'"]+)['"]''', text)
    refs += re.findall(r'''\bimport\s*['"]([^'"]+)['"]''', text)
    refs += re.findall(r'''\bfetch\s*\(\s*['"]([^'"]+)['"]\s*[,)]''', text)
    # A deferred asset URL uses its asset-directory base, not this module's
    # directory. Its files are strictly checked through the wood manifests.
    refs += [ref for ref, base in re.findall(r'''\bnew URL\s*\(\s*['"]([^'"]+)['"]\s*,\s*([^)]*)\)''', text)
             if base.strip() == 'import.meta.url' or ref.startswith('/')]
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
  ...(p.object ? [fileURLToPath(new URL('./objects/'+(p.object==='cybr-tree'?'forest-tree/wood-solid.rgba16.bin':['logs','house','wood-sigil'].includes(p.object)?p.object+'/solid.rgba16.bin':p.object+'.rgba16.bin'), %s))] : [])
])));""" % (json.dumps((SOURCE / 'pyro-gpu/presets.js').as_uri()),
              json.dumps((SOURCE / 'pyro-gpu/presets.js').as_uri()))
    result = subprocess.run(['node', '--input-type=module', '-e', script],
                            capture_output=True, text=True, check=True)
    paths = [Path(p).resolve() for p in json.loads(result.stdout)]
    for directory in WOOD_DIRECTORIES:
        base = SOURCE / 'pyro-gpu/objects' / directory
        paths += [path.resolve() for path, _ in manifest_records(base)]
    return sorted(set(paths))


def manifest_records(base):
    manifest = json.loads((base / 'manifest.json').read_text())
    records = []
    for name, entry in manifest['files'].items():
        path = (base / name).resolve()
        if Path(name).is_absolute() or not path.is_relative_to(base.resolve()):
            raise RuntimeError('Unsafe wood asset manifest path: ' + name)
        records.append((path, entry))
    return records


def validate_binary_assets(selected):
    problems = []
    manifest = json.loads((SOURCE / 'pyro-gpu/objects/manifest.json').read_text())
    records = [(SOURCE / 'pyro-gpu/objects' / (m['id'] + '.rgba16.bin'), m)
               for m in manifest['models']]
    tree = SOURCE / 'pyro-gpu/objects/forest-tree'
    records += manifest_records(tree)
    for directory in WOOD_DIRECTORIES:
        base = SOURCE / 'pyro-gpu/objects' / directory
        records += manifest_records(base)
    for path, entry in records:
        if path.resolve() not in selected:
            problems.append('Asset manifest references omitted ' + str(path.relative_to(SOURCE)))
            continue
        data = runtime_bytes(path)
        if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            problems.append('Binary asset differs from its manifest: ' + str(path.relative_to(SOURCE)))
    for directory in ['forest-tree', 'logs', 'house', 'wood-sigil']:
        base = SOURCE / 'pyro-gpu/objects' / directory
        metadata_path = base / 'flux-metadata.rgba32.bin'
        stats = json.loads(metadata_path.with_suffix('.bin.json').read_text())
        source = SOURCE / stats['sourceRuntimePath']
        if source.resolve() not in selected:
            problems.append('Flux metadata source omitted: ' + stats['sourceRuntimePath'])
        elif hashlib.sha256(source.read_bytes()).hexdigest() != stats['sourceSha256']:
            problems.append('Stale wood flux source: ' + directory)
        if metadata_path.stat().st_size != 64**3*16 or hashlib.sha256(metadata_path.read_bytes()).hexdigest() != stats['sha256']:
            problems.append('Invalid wood flux metadata: ' + directory)
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
    if Path(url.path).suffix not in {'.js', '.css', '.svg', '.bin', '.png', '.jpg', '.json'}:
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
    deferred = re.findall(r'''\bnew URL\s*\(\s*['"]([^'"]+)['"]\s*,\s*base\s*\)''', text)
    for ref in list(dict.fromkeys(local_references(text, path.suffix) + deferred)):
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
    for fragment in ['/solid.rgba16.bin', 'forest-tree/wood-solid.rgba16.bin',
                     'flux-metadata.rgba32.bin', '../flux-metadata.rgba32.bin']:
        text = text.replace("'" + fragment + "'", "'" + fragment + '?v=' + token + "'")
    # ForestMesh constructs URLs through a local helper; version its dynamic
    # binary, JSON and texture requests without changing the manifest lookup key.
    text = text.replace('fetch(new URL(name, base))',
                        "fetch(new URL(name + '?v=" + token + "', base))")
    # Original's wood loader keeps raw filenames as manifest dictionary keys.
    # Version only the request expression, including its computed thermal path.
    # These narrowly scoped forms refer to the manifest-validated wood assets.
    suffix = json.dumps('?v=' + token)
    if path.name == 'wood-structure-gl.js':
        text = re.sub(r'''(\bfetch\s*\(\s*base\s*\+\s*)(['"])manifest\.json\2(\s*\))''',
                      lambda m: m[1] + json.dumps(version_url('manifest.json', token)) + m[3], text)
        text = re.sub(r'''(\bfetch\s*\(\s*)(base\s*\+\s*file|asset\.base\s*\+\s*name|thermalPath)(\s*\))''',
                      lambda m: m[1] + m[2] + ' + ' + suffix + m[3], text)
        text = re.sub(r'''(\bfetch\s*\(\s*(['"])pyro-gpu/objects/forest-tree/\2\s*\+\s*name)(\s*\))''',
                      lambda m: m[1] + ' + ' + suffix + m[3], text)
    if path.name == 'forest-mesh.js':
        text = re.sub(r'''(\bfetch\s*\(\s*new URL\s*\(\s*(['"])\./objects/forest-tree/\2\s*\+\s*name)(\s*,\s*import\.meta\.url\s*\)\s*\))''',
                      lambda m: m[1] + ' + ' + suffix + m[3], text)
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
    """Execute startup, transitions and sustained scheduling on this runtime."""
    environment = dict(os.environ, FIRE_STUDIO_ROOT=str(root.resolve()))
    for runner in ['original-startup.test.mjs', 'control-transition.test.mjs', 'volume-reset.test.mjs', 'volume-lighting.test.mjs', 'volume-optical-mask.test.mjs', 'volume-longrun.test.mjs',
                   'adaptive-flow.test.mjs', 'adaptive-pressure.test.mjs', 'adaptive-runtime.test.mjs', 'adaptive-lifecycle.test.mjs',
                   'brick-pool.test.mjs', 'pooled-coupling.test.mjs', 'lighting-work.test.mjs',
                   'fuel-ground.test.mjs', 'floor-fuel.test.mjs', 'sigil-guide.test.mjs', 'scene-light-presets.test.mjs', 'smoke-lifecycle.test.mjs', 'original-smoke.test.mjs',
                   'simulation-modes.test.mjs', 'simulation-look.test.mjs', 'sparse-app.test.mjs',
                   'wood-thermo.test.mjs', 'wood-flux.test.mjs', 'wood-structure.test.mjs', 'wood-state-sampling.test.mjs',
                   'telemetry.test.mjs', 'wood-gas-mixing.test.mjs', 'wood-volume-source.test.mjs', 'wood-combustion.test.mjs',
                   'original-wood.test.mjs', 'floor-wood.test.mjs', 'volume-startup.test.mjs',
                   'powers-catalog.test.mjs', 'original-powers.test.mjs', 'volume-powers.test.mjs',
                   'powers-state.test.mjs', 'ability-lifecycle.test.mjs', 'powers-impact-reservation.test.mjs', 'volume-power-gestures.test.mjs', 'power-contact.test.mjs', 'wood-uniformity.test.mjs', 'brick-pool-uniformity.test.mjs']:
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
                                        input=data.decode('utf-8-sig'), capture_output=True, text=True, encoding='utf-8')
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
