"""Collect entertainment/lifestyle headlines from bartarinha.ir for Badbadak.

Tries RSS first (/fa/rss, /rss, /feed), falls back to HTML scraping.
Outputs a JSON feed compatible with the Badbadak frontend.

Usage:
    python -m scripts.collect_bartarinha --out public/data/bartarinha-feed.json
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (compatible; Badbadak/1.0; +https://pendar.io/badbadak/)"
SITE = "https://www.bartarinha.ir"
RSS_PATHS = ["/fa/rss", "/rss", "/feed", "/fa/rss/allnews"]
# Categories that match Badbadak's entertainment/lifestyle focus
WANTED_CATS = {
    "سرگرمی", "سبک زندگی", "بازیگران", "سلبریتی", "چهره‌ها", "هنرمندان",
    "سینما", "موسیقی", "مد و زیبایی", "گردشگری", "جالب", "جالبترین",
    "ورزشی", "فوتبال", "سلامت", "آشپزی", "تکنولوژی", "حیوانات",
}
MAX_ITEMS = 30


def _fetch(url: str, timeout: int = 15) -> bytes:
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    return urlopen(req, timeout=timeout).read(3_000_000)


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _item_id(url: str) -> str:
    return "bartarinha:" + hashlib.sha1(url.encode()).hexdigest()[:12]


def _parse_date(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return ""


def _extract_image(entry_or_soup, link: str = "") -> str:
    """Extract image URL from RSS entry or HTML meta tags."""
    # RSS media:content / media:thumbnail / enclosure
    if hasattr(entry_or_soup, "findall"):
        for ns in ("http://search.yahoo.com/mrss/", "media"):
            for tag in ("content", "thumbnail"):
                el = entry_or_soup.find(f"{{{ns}}}{tag}")
                if el is not None and el.get("url"):
                    return el.get("url")
        enc = entry_or_soup.find("enclosure")
        if enc is not None and str(enc.get("type", "")).startswith("image"):
            return enc.get("url", "")
    return ""


# ── RSS collection ──────────────────────────────────────────────────────

def _try_rss() -> list[dict] | None:
    """Try each RSS path; return items from the first that works."""
    for path in RSS_PATHS:
        url = SITE + path
        try:
            raw = _fetch(url, timeout=12)
            text = raw.decode("utf-8", errors="replace")
            # Quick sanity check — must look like XML with items/entries
            if "<item" not in text.lower() and "<entry" not in text.lower():
                continue
            return _parse_rss(raw, url)
        except Exception:
            continue
    return None


def _parse_rss(raw: bytes, feed_url: str) -> list[dict]:
    root = ET.fromstring(raw)
    atom_ns = "http://www.w3.org/2005/Atom"
    media_ns = "http://search.yahoo.com/mrss/"
    items = root.findall(".//item")
    if not items:
        items = root.findall(f".//{{{atom_ns}}}entry")

    rows: list[dict] = []
    for el in items[:MAX_ITEMS]:
        title = _clean(
            el.findtext("title")
            or el.findtext(f"{{{atom_ns}}}title")
            or ""
        )
        link = (
            el.findtext("link")
            or (el.find(f"{{{atom_ns}}}link") or {}).get("href", "")  # type: ignore[union-attr]
            or ""
        ).strip()
        if not title or not link:
            continue
        link = urljoin(SITE, link)
        summary = _clean(
            el.findtext("description")
            or el.findtext(f"{{{atom_ns}}}summary")
            or el.findtext(f"{{{atom_ns}}}content")
            or ""
        )
        published = _parse_date(
            el.findtext("pubDate")
            or el.findtext(f"{{{atom_ns}}}published")
            or el.findtext(f"{{{atom_ns}}}updated")
            or ""
        )
        image = _extract_image(el, link)

        # Category tags
        cats = []
        for cat_el in el.findall("category"):
            if cat_el.text:
                cats.append(cat_el.text.strip())
        for cat_el in el.findall(f"{{{atom_ns}}}category"):
            term = cat_el.get("term") or cat_el.text or ""
            if term.strip():
                cats.append(term.strip())

        rows.append({
            "id": _item_id(link),
            "title": title,
            "url": link,
            "summary": summary[:500],
            "image": image,
            "published": published,
            "categories": cats,
            "source": "bartarinha.ir",
        })
    return rows


# ── HTML fallback ───────────────────────────────────────────────────────

def _scrape_html() -> list[dict]:
    """Scrape homepage and section pages for article links."""
    from bs4 import BeautifulSoup

    pages = [SITE, SITE + "/fa/news"]
    seen: set[str] = set()
    rows: list[dict] = []
    host = urlparse(SITE).netloc.lower().removeprefix("www.")

    bad_parts = (
        "/tag/", "/category/", "/author/", "/page/", "/search",
        "/login", "/contact", "/about", "/cart", "/product/",
    )

    for page_url in pages:
        try:
            raw = _fetch(page_url, timeout=20)
        except Exception as exc:
            print(f"bartarinha: could not fetch {page_url}: {exc}", file=sys.stderr)
            continue

        soup = BeautifulSoup(raw, "html.parser")

        # Try to find article links in content areas first, then all links
        anchors = []
        for container in soup.select(
            "article, main, .post, .news-item, .news-list, "
            ".content, .entry, [class*=article], [class*=news], "
            "[class*=card], [class*=item]"
        ):
            anchors.extend(container.find_all("a", href=True))
        anchors += soup.find_all("a", href=True)

        for a in anchors:
            title = _clean(a.get_text(" ", strip=True) or a.get("title") or "")
            if len(title) < 14 or len(title) > 300:
                continue

            link = urljoin(page_url, a["href"])
            u = urlparse(link)
            if u.scheme not in {"http", "https"}:
                continue
            if u.netloc.lower().removeprefix("www.") != host:
                continue
            if any(p in u.path.lower() for p in bad_parts) or u.path in {"", "/"}:
                continue
            link = f"{u.scheme}://{u.netloc}{u.path}"
            if link in seen:
                continue
            seen.add(link)
            rows.append({
                "id": _item_id(link),
                "title": title,
                "url": link,
                "summary": "",
                "image": "",
                "published": "",
                "categories": [],
                "source": "bartarinha.ir",
            })
            if len(rows) >= MAX_ITEMS:
                break
        if len(rows) >= MAX_ITEMS:
            break

    return rows


# ── Image enrichment ────────────────────────────────────────────────────

def _enrich_item(item: dict) -> dict:
    """Fetch article page to grab og:image and meta description if missing."""
    if item.get("image") and item.get("summary"):
        return item
    try:
        raw = _fetch(item["url"], timeout=10)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw, "html.parser")

        if not item.get("image"):
            og = (
                soup.find("meta", attrs={"property": "og:image"})
                or soup.find("meta", attrs={"name": "twitter:image"})
            )
            if og and og.get("content"):
                item = {**item, "image": urljoin(item["url"], og["content"])}

        if not item.get("summary"):
            desc = (
                soup.find("meta", attrs={"property": "og:description"})
                or soup.find("meta", attrs={"name": "description"})
            )
            if desc and desc.get("content"):
                item = {**item, "summary": _clean(desc["content"])[:500]}

        if not item.get("published"):
            pub = (
                soup.find("meta", attrs={"property": "article:published_time"})
                or soup.find("meta", attrs={"itemprop": "datePublished"})
            )
            if pub and pub.get("content"):
                item = {**item, "published": _parse_date(pub["content"])}
    except Exception:
        pass
    return item


# ── Main ────────────────────────────────────────────────────────────────

def collect() -> list[dict]:
    """Collect articles: try RSS first, fall back to HTML scraping."""
    items = _try_rss()
    transport = "rss"
    if items is None:
        print("bartarinha: no RSS feed found, falling back to HTML scraping", file=sys.stderr)
        items = _scrape_html()
        transport = "html"
    if not items:
        print("bartarinha: no items collected", file=sys.stderr)
        return []

    print(f"bartarinha: collected {len(items)} items via {transport}")

    # Enrich items that lack images (fetch og:image from article pages)
    need_enrich = [i for i in items if not i.get("image")]
    if need_enrich:
        with ThreadPoolExecutor(max_workers=6) as pool:
            enriched = list(pool.map(_enrich_item, need_enrich[:20]))
        enriched_by_id = {x["id"]: x for x in enriched}
        items = [enriched_by_id.get(x["id"], x) for x in items]

    return items


def main():
    parser = argparse.ArgumentParser(description="Collect bartarinha.ir feed for Badbadak")
    parser.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args()

    items = collect()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Merge with existing data to preserve items across builds
    existing: list[dict] = []
    if out.exists():
        try:
            existing = json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Keep existing items not in new batch (for continuity), up to 60 total
    new_ids = {x["id"] for x in items}
    merged = items + [x for x in existing if x.get("id") not in new_ids]
    merged = merged[:60]

    out.write_text(json.dumps(merged, ensure_ascii=False, indent=None), encoding="utf-8")
    print(f"bartarinha: wrote {len(merged)} items to {out}")


if __name__ == "__main__":
    main()
