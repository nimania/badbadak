#!/usr/bin/env python3
"""Build public GitHub Pages articles from published native WordPress posts.

WordPress is the editorial source of truth; GitHub Pages serves the static output.
Requires an indexable-or-noindexed *public* WordPress REST API endpoint.
Never reads drafts or private posts. Fails closed if the feed is missing/empty.
"""
import argparse
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ROOT = "https://nimania.github.io/badbadak/"
ALLOWED = {"p", "h2", "h3", "h4", "ul", "ol", "li", "blockquote",
           "strong", "em", "b", "i", "a", "img", "figure", "figcaption",
           "div", "span", "br", "hr", "time", "code", "pre"}
VOID = {"img", "br", "hr"}
CATEGORY_MAP = {
    "celebrities": "celeb", "turkish-series": "turkish",
    "beauty": "beauty", "health": "health", "fashion": "style",
    "food": "food", "buzz": "buzz", "technology": "tech",
    "travel": "travel", "latest": "buzz",
}

def safe_url(value, base="", allow_fragment=False):
    if not value:
        return ""
    value = urllib.parse.urljoin(base, str(value).strip())
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme in ("https", "http") and parsed.netloc:
        return value
    if allow_fragment and value.startswith("#"):
        return value
    return ""

class ContentCleaner(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=False)
        self.base, self.parts, self.first_image = base, [], ""
    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED:
            return
        raw = dict(attrs)
        accepted = []
        if tag == "a":
            href = safe_url(raw.get("href"), self.base, allow_fragment=True)
            if href:
                accepted += [('href', href), ('rel', 'noopener noreferrer')]
        if tag == "img":
            src = safe_url(raw.get("src"), self.base)
            if not src:
                return
            if not self.first_image:
                self.first_image = src
            accepted += [('src', src), ('alt', raw.get('alt', '')[:200]), ('loading', 'lazy')]
        if tag == "time" and raw.get("datetime"):
            accepted.append(('datetime', raw['datetime']))
        params = "".join(" %s=\"%s\"" % (key, html.escape(str(val), quote=True))
                         for key, val in accepted)
        self.parts.append("<" + tag + params + ">")
    def handle_endtag(self, tag):
        if tag in ALLOWED and tag not in VOID:
            self.parts.append("</" + tag + ">")
    def handle_data(self, data):
        self.parts.append(html.escape(data, quote=False))
    def handle_entityref(self, name):
        self.parts.append("&" + name + ";")
    def handle_charref(self, name):
        self.parts.append("&#" + name + ";")
    def get_html(self):
        return "".join(self.parts)

class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)
    def text(self):
        return html.unescape(" ".join(self.parts)).strip()

def plain(value):
    parser = PlainText()
    parser.feed(value or "")
    return re.sub(r"\s+", " ", parser.text()).strip()

def fetch_posts(site):
    base = site.rstrip("/") + "/"
    url = urllib.parse.urljoin(base, "wp-json/wp/v2/posts")
    output = []
    for page in range(1, 51):
        query = urllib.parse.urlencode({"per_page": 100, "page": page,
                                        "status": "publish", "_embed": "1"})
        request = urllib.request.Request(url + "?" + query,
                                         headers={"User-Agent": "Badbadak-Static-Publisher/1.0",
                                                  "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=35) as response:
            batch = json.load(response)
        if not isinstance(batch, list):
            raise ValueError("WordPress posts endpoint did not return a list")
        output.extend(batch)
        if len(batch) < 100:
            break
    return output

def article_html(post, clean, slug):
    title = html.escape(plain(post.get("title", {}).get("rendered", "")))
    canonical = PUBLIC_ROOT + "news/" + slug + "/"
    published = html.escape(post.get("date", "")[:10])
    body = clean.get_html()
    desc = html.escape(plain(post.get("excerpt", {}).get("rendered", ""))[:155], quote=True)
    return """<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="%s">
<link rel="canonical" href="%s">
<link rel="icon" href="../../assets/badbadak-logo.png">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap">
<link rel="stylesheet" href="../../badbadak.css">
<title>%s | بادبادک</title>
<style>
body{background:#eef1f7;color:#26304d;font-family:Vazirmatn,Tahoma,sans-serif}
.bb-article-static{max-width:850px;margin:2rem auto;padding:clamp(1rem,4vw,3rem);
background:white;border:1px solid #d8dee8;border-radius:18px;line-height:2.1}
.bb-article-static img{max-width:100%%;height:auto;border-radius:10px}
.bb-article-static h1{font-size:clamp(1.5rem,4vw,2.3rem);line-height:1.6}
.bb-article-static a{color:#3e559b}
.bb-article-static figure{margin:1.5rem 0}
.bb-article-static header{border-bottom:3px solid #ec7b26}
</style></head><body><main class="bb-article-static">
<header><a href="../../">بادبادک</a><p>چهره‌ها، سبک زندگی و سرگرمی</p></header>
<article><h1>%s</h1><time datetime="%s">%s</time><div class="bb-article-body">%s</div></article>
<footer><a href="../../">بازگشت به بادبادک</a> ·
<a href="https://pendar.io/">پندار</a> ·
<a href="https://nimania.github.io/jan-kalam/">جان کلام</a></footer>
</main></body></html>""" % (desc, canonical, title, title, published, published, body)

def build(site, dest):
    posts = fetch_posts(site)
    if not posts:
        raise RuntimeError("No published WordPress posts: refusing an empty cutover")
    category_labels = {}
    category_request = urllib.request.Request(
        site.rstrip("/") + "/wp-json/wp/v2/categories?per_page=100",
        headers={"User-Agent": "Badbadak-Static-Publisher/1.0"})
    with urllib.request.urlopen(category_request, timeout=35) as response:
        categories = json.load(response)
    category_labels = {int(c["id"]): c.get("slug") for c in categories}
    feed = []
    for post in posts:
        post_id = int(post["id"])
        slug = str(post.get("slug") or "wp-%s" % post_id)
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,160}", slug):
            slug = "wp-%s" % post_id
        title = plain(post.get("title", {}).get("rendered", ""))
        if not title:
            continue
        content = post.get("content", {}).get("rendered", "")
        cleaner = ContentCleaner(site.rstrip("/") + "/")
        cleaner.feed(content)
        html_file = dest / "news" / slug / "index.html"
        html_file.parent.mkdir(parents=True, exist_ok=True)
        html_file.write_text(article_html(post, cleaner, slug), encoding="utf-8")
        image = cleaner.first_image
        for media in post.get("_embedded", {}).get("wp:featuredmedia", []):
            image = safe_url(media.get("source_url"), site) or image
            if image:
                break
        keys = [category_labels.get(c, "") for c in post.get("categories", [])]
        category = next((CATEGORY_MAP[key] for key in keys if key in CATEGORY_MAP), "buzz")
        feed.append({
            "id": slug, "bb_origin": "wordpress", "bb_category": category,
            "headline_fa": title,
            "summary_fa": plain(post.get("excerpt", {}).get("rendered", ""))[:360],
            "image_url": image,
            "published_at": post.get("date_gmt") or post.get("date") or "",
            "bb_source": "بادبادک",
            "wp_id": post_id
        })
    if not feed:
        raise RuntimeError("No valid WordPress posts: refusing an empty cutover")
    feed.sort(key=lambda x: x["published_at"], reverse=True)
    output = dest / "data" / "wordpress-posts.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"source": "wordpress", "generated_at":
        datetime.now(timezone.utc).isoformat(), "posts": feed}, ensure_ascii=False,
        indent=2) + "\n", encoding="utf-8")
    print("Built %d WordPress posts into %s" % (len(feed), dest))

if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--site", default=os.environ.get("BADBADAK_WP_API_URL", ""))
    cli.add_argument("--dest", type=Path, default=ROOT)
    args = cli.parse_args()
    if not args.site.startswith("https://"):
        cli.error("Set BADBADAK_WP_API_URL to the public HTTPS WordPress backend URL")
    build(args.site, args.dest)
