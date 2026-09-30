import unittest
from check import local_reference, References, SITE


class ReferenceTests(unittest.TestCase):
    def test_queries_and_optional_links(self):
        parser = References()
        parser.feed('<video src="movie.mp4?version=2" poster="poster.jpg"></video><a data-optional href="archive.zip">Archive</a>')
        self.assertEqual(parser.paths, ["movie.mp4?version=2", "poster.jpg"])
        self.assertEqual(local_reference(SITE / "index.html", "movie.mp4?version=2"), SITE / "movie.mp4")

    def test_external_links_and_escape(self):
        self.assertIsNone(local_reference(SITE / "index.html", "https://github.com/cybrdelic/cybr-elements"))
        with self.assertRaises(ValueError):
            local_reference(SITE / "index.html", "../../secret")


if __name__ == "__main__":
    unittest.main()
