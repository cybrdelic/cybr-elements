"""Check the included showcase and regression suite; --media fully decodes its films."""
from __future__ import annotations
import argparse
import ast
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "outputs/cybrdelic-type"
PLAYER = SITE / "elements/motion/bending/sigils/02"
ASSETS = ROOT / "docs/media/current-assets.json"


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if "data-optional" in attrs:
            return
        for key in ("src", "href", "poster"):
            if attrs.get(key):
                self.paths.append(attrs[key])


def local_reference(page: Path, reference: str) -> Path | None:
    url = urlsplit(reference)
    if url.scheme or url.netloc or not url.path:
        return None
    path = SITE / unquote(url.path.lstrip("/")) if url.path.startswith("/") else page.parent / unquote(url.path)
    path = path.resolve()
    if not path.is_relative_to(SITE.resolve()):
        raise ValueError(f"Reference escapes showcase: {reference}")
    if path.is_dir():
        path /= "index.html"
    return path


def check_assets():
    inventory = json.loads(ASSETS.read_text(encoding="utf-8"))
    for row in inventory["assets"]:
        path = ROOT / row["path"]
        if not path.is_file():
            raise ValueError(f"Missing included asset: {row['path']}")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if path.stat().st_size != row["bytes"] or digest != row["sha256"]:
            raise ValueError(f"Included asset changed: {row['path']}; review before updating current-assets.json")
    print(f"Verified {len(inventory['assets'])} included media/font assets.", flush=True)
    return [ROOT / row["path"] for row in inventory["assets"] if row["path"].endswith(".mp4")]


def check_pages():
    pages = [SITE / "index.html", PLAYER / "index.html", SITE / "typefaces/index.html",
             SITE / "elements/water/index.html", SITE / "elements/motion/water/index.html"]
    files = []
    for page in pages:
        parser = References()
        parser.feed(page.read_text(encoding="utf-8"))
        for reference in parser.paths:
            path = local_reference(page, reference)
            if path and not path.is_file():
                raise ValueError(f"Broken showcase reference in {page.relative_to(ROOT)}: {reference}")
            if path and path.suffix in (".css", ".js", ".mjs"):
                files.append(path)
    for css in {path for path in files if path.suffix == ".css"}:
        for reference in re.findall(r"url\([\"']?([^\"')]+)", css.read_text(encoding="utf-8")):
            path = local_reference(css, reference)
            if path and not path.is_file():
                raise ValueError(f"Broken stylesheet reference: {reference}")
    manifest = json.loads((PLAYER / "films.json").read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != 1 or set(manifest.get("elements", {})) != {"fire", "water", "earth", "air", "ice", "lava", "lightning"}:
        raise ValueError("The player manifest must define the seven current materials")
    for name, element in manifest["elements"].items():
        for version in ("current", "previous"):
            if version not in element:
                continue
            asset = element[version]
            for field in ("file", "poster"):
                path = local_reference(PLAYER / "index.html", asset[field])
                if not path or not path.is_file() or path.parent != PLAYER:
                    raise ValueError(f"Invalid {name}/{version} asset: {asset[field]}")
            if asset["duration"] <= 0 or asset["fps"] <= 0:
                raise ValueError(f"Invalid {name}/{version} timing")
    node = shutil.which("node")
    if node:
        for script in {path for path in files if path.suffix in (".js", ".mjs")}:
            subprocess.run([node, "--check", str(script)], check=True)
    print("Showcase and font-page references passed.", flush=True)


def decode_media(movies):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise ValueError("--media requires ffmpeg and ffprobe on PATH")
    frames = 0
    for movie in movies:
        result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                 "-show_entries", "stream=width,height,nb_frames:format=duration",
                                 "-of", "json", str(movie)], check=True, capture_output=True, text=True)
        probe = json.loads(result.stdout)
        if not probe.get("streams") or float(probe["format"]["duration"]) <= 0:
            raise ValueError(f"Invalid film: {movie.name}")
        stream = probe["streams"][0]
        if (stream.get("width"), stream.get("height")) != (1920, 1080):
            raise ValueError(f"Unexpected film resolution: {movie.name}")
        subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-threads", "2", "-i", str(movie),
                        "-map", "0:v:0", "-f", "null", "-"], check=True, timeout=180)
        frames += int(stream.get("nb_frames", 0))
        print(f"Decoded {movie.name}.", flush=True)
    print(f"Fully decoded {len(movies)} films ({frames} frames).", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media", action="store_true")
    args = parser.parse_args()
    try:
        for script in (ROOT / "scripts").glob("*.py"):
            ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
        movies = check_assets()
        check_pages()
        subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "scripts", "-p", "test_*.py"], cwd=ROOT, check=True)
        if args.media:
            decode_media(movies)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Check failed: {exc}\n")
    print("Project checks passed.", flush=True)


if __name__ == "__main__":
    main()
