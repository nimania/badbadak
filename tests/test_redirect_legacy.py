"""Offline migration tests; do not require network access."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import redirect_legacy


class RedirectLegacyTest(unittest.TestCase):
    def create_fixture(self, directory):
        root = Path(directory)
        root.joinpath("index.html").write_text("<html>Old homepage</html>", encoding="utf-8")
        target = root / "news" / "foo"
        target.mkdir(parents=True)
        target.joinpath("index.html").write_text(
            '<!doctype html><html><head><link rel="canonical" href="https://nimania.github.io/badbadak/news/foo/"></head><body>Old news</body></html>',
            encoding="utf-8")
        unmatched = root / "news" / "unmatched"
        unmatched.mkdir(parents=True)
        unmatched.joinpath("index.html").write_text(
            '<html><head><link rel="canonical" href="https://nimania.github.io/badbadak/news/unmatched/"></head><body>Unmigrated story</body></html>',
            encoding="utf-8")
        redirects = {f"story-{i}": f"https://badbadakmedia.wordpress.com/2026/11/11/story-{i}/"
                     for i in range(33)}
        redirects["foo"] = "https://badbadakmedia.wordpress.com/2026/11/11/foo/"
        mapping = root / "map.json"
        mapping.write_text(json.dumps({
            "site": "https://badbadakmedia.wordpress.com/",
            "redirects": redirects
        }), encoding="utf-8")
        return root, mapping

    def test_redirects_mapped_and_noindexes_unmapped(self):
        with tempfile.TemporaryDirectory() as directory:
            root, mapping = self.create_fixture(directory)
            redirect_legacy.apply(root, mapping)
            homepage = (root / "index.html").read_text()
            mapped = (root / "news" / "foo" / "index.html").read_text()
            unmatched = (root / "news" / "unmatched" / "index.html").read_text()
            generated = root / "news" / "story-0" / "index.html"
            self.assertIn('location.replace("https://badbadakmedia.wordpress.com/")', homepage)
            self.assertIn("crossword", homepage)
            self.assertIn('content="noindex, follow"', homepage)
            self.assertIn("2026/11/11/foo/", mapped)
            self.assertIn('rel="canonical"', mapped)
            self.assertIn("http-equiv=\"refresh\"", mapped)
            self.assertTrue(generated.exists())
            self.assertIn("Unmigrated story", unmatched)
            self.assertIn('content="noindex, follow"', unmatched)
            self.assertNotIn('rel="canonical"', unmatched)

    def test_missing_mapping_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root, mapping = self.create_fixture(directory)
            mapping.write_text(json.dumps({"site": "https://badbadakmedia.wordpress.com/",
                                           "redirects": {"foo": "https://badbadakmedia.wordpress.com/foo/"}}))
            with self.assertRaises(ValueError):
                redirect_legacy.apply(root, mapping)
            self.assertEqual((root / "index.html").read_text(),
                             "<html>Old homepage</html>")


if __name__ == "__main__":
    unittest.main()
