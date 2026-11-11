#!/usr/bin/env python3
"""Migrate legacy GitHub Pages URLs to the WordPress primary site.

For the 34 known WordPress posts, emit instant HTML/JS redirects to exact
permalinks. Keep all other old articles readable but noindex to avoid duplicate
search results while the WordPress publishing pipeline is completed.

GitHub Pages cannot send real HTTP 301 responses: this emits zero-delay meta
refresh, canonical, JS redirects and noindex signals instead.
"""
import argparse
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAPPING = ROOT / "data" / "wordpress-redirect-map.json"
CROSSWORD = "https://blankuapp.github.io/PersianCrossword/"


def redirect_page(destination, title, preserve_crossword=False):
    target = html.escape(destination, quote=True)
    heading = html.escape(title)
    js = (
        'if(location.hash.includes("crossword")){'
        'location.replace("'+CROSSWORD+'");'
        '}else{location.replace('+json.dumps(destination)+');}'
        if preserve_crossword else
        'location.replace('+json.dumps(destination)+');'
    )
    return f'''<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, follow">
<link rel="canonical" href="{target}">
<title>{heading} | بادبادک</title>
<script>{js}</script>
<meta http-equiv="refresh" content="0; url={target}">
</head><body style="font-family:Tahoma,sans-serif;direction:rtl;text-align:center;margin:4rem auto;max-width:45rem">
<h1>{heading}</h1><p>بادبادک به نشانی جدید منتقل شده است.</p>
<p><a href="{target}">ورود به نسخهٔ جدید بادبادک</a></p>
</body></html>
'''


def noindex_legacy(content):
    # Keep URLs alive for not-yet-imported articles; do not falsely redirect a
    # story to a different article or the homepage.
    content = re.sub(r'<link\s+rel=["\x27]canonical["\x27][^>]*>', '',
                     content, flags=re.I)
    if re.search(r'<meta\s+name=["\x27]robots["\x27]', content, flags=re.I):
        content = re.sub(r'<meta\s+name=["\x27]robots["\x27][^>]*>',
                         '<meta name="robots" content="noindex, follow">',
                         content, count=1, flags=re.I)
    else:
        content = re.sub(r'<head>', '<head><meta name="robots" content="noindex, follow">',
                         content, count=1, flags=re.I)
    return content


def apply(root, mapping_file):
    cfg = json.loads(mapping_file.read_text(encoding="utf-8"))
    site = cfg["site"].rstrip("/") + "/"
    redirects = cfg["redirects"]
    if not site.startswith("https://") or not site.endswith(".wordpress.com/"):
        raise ValueError("Target must be a WordPress.com HTTPS address")
    if not redirects or len(redirects) < 30:
        raise ValueError("Missing WordPress redirects; refusing a partial migration")
    for slug, url in redirects.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", slug) or not url.startswith(site):
            raise ValueError("Invalid redirect mapping: " + slug)

    root_index = root / "index.html"
    if not root_index.exists():
        raise FileNotFoundError(root_index)

    mapped = 0
    remaining = 0
    for old_page in (root / "news").glob("*/index.html"):
        slug = old_page.parent.name
        destination = redirects.get(slug)
        if destination:
            old_page.write_text(redirect_page(destination, "در حال انتقال به خبر"),
                                encoding="utf-8")
            mapped += 1
        else:
            content = old_page.read_text(encoding="utf-8")
            old_page.write_text(noindex_legacy(content), encoding="utf-8")
            remaining += 1

    # Also generate a redirect for any imported article missing from the
    # currently bundled static snapshot.
    for slug, destination in redirects.items():
        path = root / "news" / slug / "index.html"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(redirect_page(destination, "در حال انتقال به خبر"),
                            encoding="utf-8")
            mapped += 1
    root_index.write_text(redirect_page(site, "بادبادک", preserve_crossword=True),
                          encoding="utf-8")
    print(json.dumps({"redirected": mapped, "legacy_noindex": remaining,
                      "primary": site}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    args = parser.parse_args()
    apply(args.root, args.mapping)
