#!/usr/bin/env python3
"""Import Badbadak source articles as native WordPress posts. Dry run by default."""
import argparse
import base64
import hashlib
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/article-index.json"
RULES = [
    ("سریال‌های ترکی", "turkish-series", r"سریال ترکی|ترکیه"),
    ("چهره‌ها", "celebrities", r"بازیگر|خواننده|سینما|هنرمند|کنسرت|سلبریتی"),
    ("آرایش و زیبایی", "beauty", r"آرایش|زیبایی|پوست|رنگ مو"),
    ("سلامت", "health", r"سلامت|پزشکی|بیماری|درمان"),
    ("مد و استایل", "fashion", r"پوشاک|لباس|استایل|فشن"),
    ("خوراکی", "food", r"غذا|رستوران|آشپزی|قهوه|شیرینی"),
    ("جنجال و حوادث", "buzz", r"حادثه|تصادف|جنجال|حاشیه|قتل"),
    ("تکنولوژی", "technology", r"فناوری|هوش مصنوعی|تکنولوژی|آیفون"),
    ("سفر", "travel", r"گردشگری|هتل|سفر"),
]


def category(row):
    if row.get("source") == "مشکی‌مدیا":
        return ("سریال‌های ترکی", "turkish-series")
    title = row.get("title") or ""
    for name, slug, rx in RULES:
        if re.search(rx, title):
            return name, slug
    return ("تازه‌ها", "latest")


def slug(row):
    # Match existing GitHub /news/<id>/ URLs and the 34 migrated WordPress drafts.
    raw = re.sub(r"[^A-Za-z0-9_-]", "_", str(row["id"]))[:160]
    return raw or "badbadak-" + hashlib.sha256(str(row["id"]).encode()).hexdigest()[:20]


def safe_url(url):
    text = str(url or "").strip()
    parsed = urllib.parse.urlparse(text)
    return text if parsed.scheme in ("http", "https") and parsed.netloc else ""


def html_body(row):
    chunks = []
    hero = safe_url(row.get("image"))
    if hero:
        chunks.append('<figure><img src="' + html.escape(hero, quote=True) + '" loading="lazy" alt=""></figure>')
    if row.get("summary"):
        chunks.append("<p><strong>" + html.escape(row["summary"]) + "</strong></p>")
    for block in row.get("blocks") or []:
        kind = block.get("type")
        content = html.escape(str(block.get("text") or ""))
        if kind in ("paragraph", "heading") and content:
            tag = "h2" if kind == "heading" else "p"
            chunks.append("<" + tag + ">" + content + "</" + tag + ">")
        elif kind == "image":
            url = safe_url(block.get("url"))
            if url and url != hero:
                chunks.append('<figure><img src="' + html.escape(url, quote=True) + '" alt="' + content + '"></figure>')
        elif kind == "video":
            url = safe_url(block.get("player_url") or block.get("url"))
            if url:
                chunks.append('<p><a href="' + html.escape(url, quote=True) + '">تماشای ویدئو در منبع</a></p>')
    original = safe_url(row.get("canonical_source") or row.get("url"))
    if original:
        chunks.append('<p>منبع: <a href="' + html.escape(original, quote=True) +
                      '" rel="noopener noreferrer">' + html.escape(row.get("source") or "منبع اصلی") + "</a></p>")
    return "\n".join(chunks)


def load_articles():
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    collection = payload.get("articles", {})
    records = collection.values() if isinstance(collection, dict) else collection
    rows = [r for r in records if isinstance(r, dict) and r.get("id") and r.get("title") and
            r.get("blocks") and r.get("status") in ("ok", "cached")]
    return sorted(rows, key=lambda row: row.get("published") or "", reverse=True)


class Wordpress:
    def __init__(self):
        self.base = os.environ["WP_URL"].rstrip("/") + "/wp-json/wp/v2"
        user = os.environ["WP_USER"]
        password = os.environ["WP_APP_PASSWORD"].replace(" ", "")
        auth = base64.b64encode((user + ":" + password).encode()).decode()
        self.headers = {"Authorization": "Basic " + auth, "Accept": "application/json",
                        "User-Agent": "Badbadak-Migration/1.0"}
        self.categories = {}

    def request(self, method, endpoint, payload=None):
        data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        headers = dict(self.headers)
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + endpoint, method=method, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            details = error.read(750).decode("utf-8", "replace")
            raise RuntimeError(f"WordPress {error.code} at {endpoint}: {details}") from error

    def category_id(self, name, key):
        if key not in self.categories:
            query = "/categories?" + urllib.parse.urlencode({"slug": key, "per_page": 1})
            found = self.request("GET", query)
            item = found[0] if found else self.request("POST", "/categories", {"name": name, "slug": key})
            self.categories[key] = int(item["id"])
        return self.categories[key]

    def save(self, row, publish=False, update=False):
        name, category_key = category(row)
        post_slug = slug(row)
        query = "/posts?" + urllib.parse.urlencode({"slug": post_slug, "context": "edit", "per_page": 1})
        existing = self.request("GET", query)
        if existing and not update:
            return "exists", existing[0].get("link", "")
        data = {"title": row["title"], "slug": post_slug, "content": html_body(row),
                "excerpt": str(row.get("summary") or "")[:280],
                "categories": [self.category_id(name, category_key)]}
        if existing:
            data["status"] = existing[0]["status"]
            saved = self.request("POST", "/posts/" + str(existing[0]["id"]), data)
            return "updated", saved.get("link", "")
        data["status"] = "publish" if publish else "draft"
        saved = self.request("POST", "/posts", data)
        return "created", saved.get("link", "")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write to WordPress; otherwise dry run")
    parser.add_argument("--publish", action="store_true", help="Publish new posts (draft by default)")
    parser.add_argument("--update", action="store_true", help="Update existing imported posts")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    if args.publish and not args.apply:
        parser.error("--publish requires --apply")
    if args.limit <= 0:
        parser.error("--limit must be positive")
    rows = load_articles()[:args.limit]
    if not args.apply:
        print(json.dumps({"mode": "dry-run", "count": len(rows), "sample": [
            {"title": r["title"], "slug": slug(r), "category": category(r)[0]}
            for r in rows[:10]
        ]}, ensure_ascii=False, indent=2))
        return
    for key in ("WP_URL", "WP_USER", "WP_APP_PASSWORD"):
        if not os.environ.get(key):
            parser.error("Missing environment variable: " + key)
    wp = Wordpress()
    results = {"created": 0, "updated": 0, "exists": 0, "failed": 0}
    for row in rows:
        try:
            outcome, link = wp.save(row, publish=args.publish, update=args.update)
            results[outcome] += 1
            print(json.dumps({"outcome": outcome, "id": row["id"], "url": link}, ensure_ascii=False))
        except Exception as error:
            results["failed"] += 1
            print(json.dumps({"outcome": "failed", "id": row["id"], "error": str(error)}, ensure_ascii=False))
    print(json.dumps({"summary": results}, ensure_ascii=False))
    if results["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
