"""Offline contract tests for the WordPress -> GitHub static publisher."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_from_wordpress as publisher


class FakeResponse(io.BytesIO):
    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode("utf-8"))
        self.headers = {"X-WP-TotalPages": "1"}


def fake_api(request, timeout=35):
    url = request.full_url
    if "/posts?" in url:
        return FakeResponse([{
            "id": 12,
            "slug": "7sobh_75f3849b9c04",
            "title": {"rendered": "خبر <strong>نمونه</strong>"},
            "excerpt": {"rendered": "<p>خلاصه آزمایشی</p>"},
            "content": {"rendered": '<p onclick="evil()">متن خبر</p>'
                        '<img src="https://media.example/photo.jpg" onerror="evil()">'
                        '<script>alert("untrusted")</script>'
                        '<p><a href="javascript:alert(1)">پیوند نامعتبر</a></p>'},
            "categories": [2],
            "date": "2026-11-11T11:30:00",
            "date_gmt": "2026-11-11T08:00:00",
            "_embedded": {}
        }])
    if "/categories?" in url:
        return FakeResponse([{"id": 2, "slug": "celebrities"}])
    raise AssertionError("Unexpected request: " + url)


class WordPressStaticTest(unittest.TestCase):
    @patch.object(publisher.urllib.request, "urlopen", side_effect=fake_api)
    def test_build_writes_post_and_homepage_feed(self, _):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory)
            publisher.build("https://example.wordpress.com", dest)
            article = dest / "news" / "7sobh_75f3849b9c04" / "index.html"
            feed_file = dest / "data" / "wordpress-posts.json"
            self.assertTrue(article.exists())
            self.assertTrue(feed_file.exists())
            page = article.read_text(encoding="utf-8")
            self.assertIn('rel="canonical"', page)
            self.assertIn("https://nimania.github.io/badbadak/news/7sobh_75f3849b9c04/", page)
            self.assertNotIn("<script", page)
            self.assertNotIn("onerror", page)
            self.assertNotIn("onclick", page)
            self.assertNotIn("javascript:alert", page)
            feed = json.loads(feed_file.read_text(encoding="utf-8"))
            self.assertEqual(len(feed["posts"]), 1)
            self.assertEqual(feed["posts"][0]["bb_category"], "celeb")
            self.assertEqual(feed["posts"][0]["id"], "7sobh_75f3849b9c04")

    @patch.object(publisher.urllib.request, "urlopen", return_value=FakeResponse([]))
    def test_empty_wordpress_feed_fails_closed(self, _):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory)
            with self.assertRaises(RuntimeError):
                publisher.build("https://example.wordpress.com", dest)
            self.assertFalse((dest / "data" / "wordpress-posts.json").exists())

    def test_url_sanitization_blocks_javascript(self):
        self.assertEqual(
            publisher.safe_url("javascript:alert(1)", "https://example.wordpress.com/"),
            "",
        )


if __name__ == "__main__":
    unittest.main()
