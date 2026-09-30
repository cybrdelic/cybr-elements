"""Exercise the HTTP responses browsers use for playback and seeking."""
from functools import partial
from http.server import ThreadingHTTPServer
import tempfile
from pathlib import Path
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from serve import ShowcaseHandler, byte_range, PLAYER


class RangeTests(unittest.TestCase):
    def test_ranges(self):
        for header, expected in [("bytes=0-4", (0, 4)), ("bytes=8-", (8, 9)),
                                 ("bytes=-3", (7, 9)), ("bytes=3-99", (3, 9)),
                                 ("bytes=-99", (0, 9))]:
            with self.subTest(header=header):
                self.assertEqual(byte_range(header, 10), expected)

    def test_invalid_ranges(self):
        for header in ["bytes=", "bytes=-0", "bytes=10-", "bytes=4-2", "bytes=0-1,4-5", "items=0-4"]:
            with self.subTest(header=header), self.assertRaises(ValueError):
                byte_range(header, 10)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        (cls.root / "clip.mp4").write_bytes(b"0123456789")
        (cls.root / PLAYER.strip("/")).mkdir(parents=True)
        (cls.root / PLAYER.strip("/") / "index.html").write_text("included showcase")
        class QuietHandler(ShowcaseHandler):
            def log_message(self, *args):
                pass
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(cls.root)))
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def test_root_routes_to_included_player_and_keeps_state(self):
        with urlopen(self.url + "/?element=water") as response:
            self.assertEqual(response.read(), b"included showcase")
            self.assertTrue(response.url.endswith(PLAYER + "?element=water"))

    def test_seek_returns_only_requested_bytes(self):
        with urlopen(Request(self.url + "/clip.mp4", headers={"Range": "bytes=2-5"})) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.headers["Content-Range"], "bytes 2-5/10")
            self.assertEqual(response.headers["Content-Length"], "4")
            self.assertEqual(response.read(), b"2345")

    def test_head_and_invalid_range(self):
        with urlopen(Request(self.url + "/clip.mp4", method="HEAD", headers={"Range": "bytes=-2"})) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.read(), b"")
        with self.assertRaises(HTTPError) as caught:
            urlopen(Request(self.url + "/clip.mp4", headers={"Range": "bytes=100-"}))
        self.assertEqual(caught.exception.code, 416)
        self.assertEqual(caught.exception.headers["Content-Range"], "bytes */10")

    def test_stale_if_range_requests_full_file(self):
        with urlopen(Request(self.url + "/clip.mp4", headers={"Range": "bytes=0-1", "If-Range": '"old"'})) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"0123456789")


if __name__ == "__main__":
    unittest.main()
