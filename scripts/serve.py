"""Serve the included showcase with seekable media, using only the standard library."""
from __future__ import annotations
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "outputs/cybrdelic-type"
PLAYER = "/elements/motion/bending/sigils/02/"


def byte_range(header: str, size: int) -> tuple[int, int]:
    """Resolve one RFC byte range; invalid or unsatisfiable ranges raise ValueError."""
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
    if not match or not any(match.groups()) or size <= 0:
        raise ValueError("Unsupported range")
    first, last = match.groups()
    if not first:
        length = int(last)
        if length <= 0:
            raise ValueError("Empty suffix")
        return max(0, size - length), size - 1
    start = int(first)
    end = min(int(last), size - 1) if last else size - 1
    if start >= size or start > end:
        raise ValueError("Unsatisfiable range")
    return start, end


class ShowcaseHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      ".mjs": "text/javascript", ".woff2": "font/woff2",
                      ".mp4": "video/mp4", ".gz": "application/gzip"}

    def list_directory(self, path):
        self.send_error(404, "No page at this path")
        return None

    def send_head(self):
        self._remaining = None
        url = urlsplit(self.path)
        destinations = {"/": PLAYER, "/archive/": "/elements/motion/"}
        if url.path in destinations:
            destination = destinations[url.path]
            if url.query:
                destination += "?" + url.query
            self.send_response(302)
            self.send_header("Location", destination)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        path = Path(self.translate_path(self.path))
        if not path.resolve().is_relative_to(Path(self.directory).resolve()):
            self.send_error(403, "Path outside showcase")
            return None
        if path.is_dir():
            for name in ("index.html", "index.htm"):
                index = path / name
                if index.exists() and not index.resolve().is_relative_to(Path(self.directory).resolve()):
                    self.send_error(403, "Path outside showcase")
                    return None
        if not path.is_file() or "Range" not in self.headers:
            return super().send_head()
        try:
            file = path.open("rb")
        except OSError:
            self.send_error(404, "File not found")
            return None
        stat = os.fstat(file.fileno())
        size = stat.st_size
        modified = self.date_time_string(stat.st_mtime)
        if self.headers.get("If-Range", modified) != modified:
            file.close()
            return super().send_head()
        try:
            start, end = byte_range(self.headers["Range"], size)
        except ValueError:
            file.close()
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Last-Modified", modified)
        self.end_headers()
        file.seek(start)
        self._remaining = end - start + 1
        return file

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def copyfile(self, source, outputfile):
        try:
            if self._remaining is None:
                shutil.copyfileobj(source, outputfile)
                return
            remaining = self._remaining
            while remaining:
                data = source.read(min(256 * 1024, remaining))
                if not data:
                    break
                outputfile.write(data)
                remaining -= len(data)
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer((args.host, args.port), partial(ShowcaseHandler, directory=str(SITE)))
    except OSError as exc:
        parser.exit(1, f"Cannot start showcase: {exc}\n")
    print(f"CYBR Elements: http://{args.host}:{server.server_port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
