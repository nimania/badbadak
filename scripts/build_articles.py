#!/usr/bin/env python3
"""Fetch licensed source articles and publish readable, attributed local pages."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse, unquote_plus
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
from book_mentions import catalog as book_catalog, enrich_articles

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
CACHE = DATA / 'article-index.json'
SOURCES = [('7sobh-feed.json', 'هفت صبح'), ('rokna-feed.json', 'رکنا'), ('bartarinha-feed.json', 'برترین‌ها')]
ALLOWED = {'7sobh.com', 'rokna.net', 'bartarinha.ir', 'pendar.io', 'meshki.media', 'nimania.github.io'}
REMOVE = 'aside,script,style,noscript,nav,footer,form,button,.noprint,.zxc,.webgardi_parent,.related-news,.related,.news-bottom-link,.featured-news-box,.random_play,.article_tags,.share_links,.newsinfo,.news_header_cnt,.news_info,.article_header,.br-ad-wrap,.google-preferred-source,.google_preferred_source_parent'

def slug(identifier):
    return re.sub(r'[^A-Za-z0-9_-]', '_', str(identifier))

def text(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()

def safe_url(value, base=''):
    value = urljoin(base, value or '')
    return value if urlparse(value).scheme in ('http', 'https') else ''

def image_key(url):
    parsed = urlparse(safe_url(url))
    host = (parsed.hostname or '').removeprefix('www.')
    if host in {'cdn.7sobh.com', 'cdn.bartarinha.ir', 'cdn.rokna.net'}:
        match = re.search(r'/(?:thumbnail|servev2|serve)/([^/]+)/', parsed.path)
        if match:
            return (host, match.group(1), unquote_plus(parsed.path.rsplit('/', 1)[-1]))
    return (host, parsed.path, parsed.query)

def fetch_url(url):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; Badbadak/1.0)', 'Accept': 'text/html,application/json'})
    with urlopen(req, timeout=18) as response:
        return response.read(5_000_000), response.url, response.status

def parse_article(raw, url):
    soup = BeautifulSoup(raw, 'html.parser')
    title_node = soup.select_one('h1')
    title = text(title_node.get_text(' ', strip=True)) if title_node else ''
    image = soup.select_one('meta[property="og:image"]')
    hero = safe_url(image.get('content'), url) if image else ''
    container = None
    for selector in ['[itemprop="articleBody"]', '.article-body', '.article_body', '.entry-content', '.news-text', '.story-body', '.article-content', 'article']:
        candidates = soup.select(selector)
        if candidates:
            container = max(candidates, key=lambda c: len(c.get_text(' ', strip=True)))
            break
    if container is None:
        player = soup.select_one('iframe.vod_file')
        player_url = safe_url(player.get('src'), url) if player else ''
        if player_url and urlparse(player_url).hostname in {'mcdn.rokna.net'}:
            description = soup.select_one('meta[property="og:description"]')
            media_url = player_url
            try:
                player_raw, _, _ = fetch_url(player_url)
                player_soup = BeautifulSoup(player_raw, 'html.parser')
                source = player_soup.select_one('video source[src]')
                direct = safe_url(source.get('src'), player_url) if source else ''
                if urlparse(direct).hostname == 'mcdn.rokna.net' and urlparse(direct).path.lower().endswith('.mp4'):
                    media_url = direct
            except Exception:
                pass
            blocks = [{'type': 'video', 'url': media_url, 'player_url': player_url, 'text': title}]
            if description and description.get('content'):
                blocks.insert(0, {'type': 'paragraph', 'text': description['content']})
            return title, hero, blocks
        raise ValueError('Article body was not found')
    for node in container.select(REMOVE):
        node.decompose()
    blocks = []
    seen_images = {image_key(hero)} if hero else set()
    for node in container.find_all(['p', 'h2', 'h3', 'h4', 'li', 'blockquote', 'img']):
        if node.name == 'img':
            src = safe_url(node.get('data-src') or node.get('src'), url)
            if src and image_key(src) not in seen_images:
                seen_images.add(image_key(src))
                blocks.append({'type': 'image', 'url': src, 'text': text(node.get('alt'))})
            continue
        # Emit parent block only once, preserving text and its original order.
        if any(p.name in ('p', 'h2', 'h3', 'h4', 'li', 'blockquote') for p in node.parents if p is not container):
            continue
        content = node.get_text(' ', strip=True)
        if content:
            blocks.append({'type': 'heading' if node.name.startswith('h') else 'paragraph', 'text': content})
    if not blocks:
        content = container.get_text('\n', strip=True)
        blocks = [{'type': 'paragraph', 'text': line} for line in content.splitlines() if line.strip()]
    if not blocks:
        raise ValueError('Source article has no readable body')
    return title, hero, blocks

def inputs():
    rows = []
    for filename, source in SOURCES:
        p = DATA / filename
        for row in json.loads(p.read_text()) if p.exists() else []:
            if row.get('id') and row.get('url'):
                rows.append({'id': row['id'], 'title': row.get('title', ''), 'url': row['url'], 'source': source, 'summary': row.get('summary', ''), 'image': row.get('image', ''), 'published': row.get('published', '')})
    p = DATA / 'stories.json'
    for row in json.loads(p.read_text()) if p.exists() else []:
        if row.get('id'):
            rows.append({'id': row['id'], 'title': row.get('headline_fa', ''), 'url': 'https://pendar.io/story/' + str(row['id']) + '/', 'source': 'پندار', 'summary': row.get('summary_fa', ''), 'image': row.get('image_url', ''), 'published': row.get('published_at', '')})
    p = DATA / 'meshki-news-feed.json'
    payload = json.loads(p.read_text()) if p.exists() else {}
    for row in payload.get('items', []):
        if row.get('id') and row.get('page'):
            rows.append({'id': row['id'], 'title': row.get('titleFa', ''), 'url': 'https://meshki.media/haber/' + str(row['id']) + '/', 'source': 'مشکی‌مدیا', 'summary': row.get('summaryFa', ''), 'image': row.get('image', ''), 'published': row.get('published', '')})
    return list({str(row['id']): row for row in rows}.values())

def collect(row, previous):
    old = previous.get(str(row['id']), {})
    now = datetime.now(timezone.utc)
    checked = old.get('checked_at')
    if checked and old.get('blocks') and old.get('url') == row['url']:
        if (now - datetime.fromisoformat(checked)).total_seconds() < 86400:
            return {**row, **old, 'summary': row['summary'], 'published': row['published']}
    result = {**old, **row, 'checked_at': now.isoformat()}
    try:
        if urlparse(row['url']).hostname.removeprefix('www.') not in ALLOWED:
            raise ValueError('Unsupported source host')
        raw, final_url, status = fetch_url(row['url'])
        if urlparse(final_url).hostname.removeprefix('www.') not in ALLOWED:
            raise ValueError('Unexpected source redirect')
        try:
            title, hero, blocks = parse_article(raw, final_url)
        except ValueError:
            if row['source'] != 'پندار':
                raise
            detail_raw, _, _ = fetch_url('https://pendar.io/data/story/' + str(row['id']) + '.json')
            detail = json.loads(detail_raw)
            title, hero = detail.get('headline_fa', row['title']), detail.get('image_url', '')
            blocks = []
            for label, key in [(None, 'summary_fa'), ('چه اتفاقی افتاد؟', 'what_happened_fa'), ('چرا اهمیت دارد؟', 'why_it_matters_fa'), ('آنچه معلوم است', 'facts'), ('آنچه هنوز روشن نیست', 'uncertainties'), ('نقاط توافق', 'agreements'), ('نقاط اختلاف', 'disagreements')]:
                value = detail.get(key)
                if not value:
                    continue
                if label:
                    blocks.append({'type': 'heading', 'text': label})
                for item in value if isinstance(value, list) else [value]:
                    if isinstance(item, str) and item.strip():
                        blocks.append({'type': 'paragraph', 'text': item})
            if not blocks:
                raise ValueError('No Pendar article body')
        result.update(title=title or row['title'], image=hero or row['image'], blocks=blocks, canonical_source=final_url, status='ok', http_status=status, fetched_at=now.isoformat(), error=None)
    except Exception as exc:
        result.update(status='cached' if old.get('blocks') else 'unavailable', error=type(exc).__name__, http_status=exc.code if isinstance(exc, HTTPError) else None)
    return result

def build_page(row):
    blocks = row.get('blocks', [])
    paragraphs = []
    seen_images = {image_key(row['image'])} if row.get('image') else set()
    for block in blocks:
        if block['type'] == 'video':
            u = safe_url(block.get('url'))
            if urlparse(u).hostname == 'mcdn.rokna.net':
                if urlparse(u).path.lower().endswith('.mp4'):
                    poster = safe_url(row.get('image'))
                    poster_attr = ' poster="' + escape(poster, quote=True) + '"' if poster else ''
                    paragraphs.append('<video class="bb-article-video" controls playsinline preload="metadata" style="display:block;width:100%;max-height:70vh;background:#111;border-radius:8px;margin:24px 0;object-fit:contain"' + poster_attr + '><source src="' + escape(u, quote=True) + '" type="video/mp4">مرورگر شما پخش این ویدئو را پشتیبانی نمی‌کند.</video>')
                else:
                    paragraphs.append('<iframe class="bb-article-video" style="display:block;width:100%;height:min(70vh,650px);border:0;margin:24px 0" title="' + escape(block.get('text', 'ویدئوی خبر'), quote=True) + '" src="' + escape(u, quote=True) + '" loading="lazy" allowfullscreen sandbox="allow-scripts allow-same-origin" referrerpolicy="no-referrer"></iframe>')
                fallback = safe_url(block.get('player_url') or u)
                paragraphs.append('<p class="bb-video-fallback"><a href="' + escape(fallback, quote=True) + '" target="_blank" rel="noopener noreferrer">اگر پخش نشد، ویدئو را در منبع باز کنید ↗</a></p>')
        elif block['type'] == 'image':
            u = safe_url(block.get('url'))
            if u and image_key(u) not in seen_images:
                seen_images.add(image_key(u))
                paragraphs.append('<figure><img src="' + escape(u, quote=True) + '" alt="' + escape(block.get('text', ''), quote=True) + '" loading="lazy" referrerpolicy="no-referrer"></figure>')
        else:
            tag = 'h2' if block['type'] == 'heading' else 'p'
            paragraphs.append('<' + tag + '>' + escape(block.get('text', '')) + '</' + tag + '>')
    body = ''.join(paragraphs)
    if row.get('status') == 'cached':
        body = '<p class="bb-article-notice">نسخهٔ ذخیره‌شدهٔ متن؛ بررسی تازهٔ منبع موقتاً انجام نشد.</p>' + body
    if not blocks:
        body = '<p class="bb-article-notice">متن کامل این خبر هنوز از منبع دریافت نشده است.</p>' + ('<p>' + escape(row.get('summary', '')) + '</p>' if row.get('summary') else '')
    book_links = ''.join('<li><a href="https://nimania.github.io/pishkhan/#/book/' + escape(b['slug'], quote=True) + '">' + escape(b['title_fa']) + '</a></li>' for b in row.get('books', []))
    if book_links:
        body += '<section class="bb-related-books"><h2>کتاب‌های این خبر در پیشخوان</h2><ul>' + book_links + '</ul></section>'
    title = escape(row['title'])
    source = escape(row['source'])
    original = escape(safe_url(row.get('canonical_source') or row['url']), quote=True)
    hero = safe_url(row.get('image'))
    has_video = any(b.get('type') == 'video' for b in blocks)
    hero_html = '<img class="bb-article-hero" src="' + escape(hero, quote=True) + '" alt="" referrerpolicy="no-referrer">' if hero and not has_video else ''
    video_intro = ''
    if has_video:
        caption = row.get('summary') or ('در تصویر این کلیپ، یک مرسدس‌بنز کلاسیک روی غلتک‌های یک دستگاه دیده می‌شود؛ نما روی بدنه و چرخ عقب خودرو متمرکز است.' if row['id'] == 'rokna:77fea61e1150' else 'موضوع این ویدئو: ' + row['title'])
        label = 'توضیح منبع' if row.get('summary') else 'توضیح بادبادک بر پایهٔ عنوان و تصویر ویدئو'
        video_intro = '<section class="bb-video-summary"><h2>دربارهٔ ویدئو</h2><p>' + escape(caption) + '</p><small>' + label + '</small></section>'
    published = escape(str(row.get('published', '')))
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} | بادبادک</title><meta name="description" content="{escape(row.get('summary', '')[:220], quote=True)}"><link rel="canonical" href="https://nimania.github.io/badbadak/news/{slug(row['id'])}/"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&amp;display=swap"><link rel="stylesheet" href="../../badbadak.css?rev=20261028-video-books"><style>body{{margin:0;background:#fafbf9}}</style></head><body><main id="badbadak-view"><div class="bb-newspaper bb-article-shell"><header class="bb-masthead"><a class="bb-masthead-logo" href="../../">بادبادک</a><a href="../../">بازگشت به خبرها ←</a></header><article class="bb-full-article"><p class="bb-article-source">به نقل از <a href="{original}" target="_blank" rel="noopener noreferrer">{source}</a></p><h1>{title}</h1><time datetime="{published}" class="bb-article-date">{published}</time>{video_intro}{hero_html}<div class="bb-article-body">{body}</div><footer class="bb-article-footer"><a href="{original}" target="_blank" rel="noopener noreferrer">اصل خبر در {source} ↗</a><p>متن از منبع دریافت شده است؛ نام منبع و پیوند اصلی حفظ شده‌اند.</p><a href="../../">بازگشت به بادبادک ←</a></footer></article></div></main></body></html>'''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-only', action='store_true')
    args = parser.parse_args()
    previous = json.loads(CACHE.read_text()).get('articles', {}) if CACHE.exists() else {}
    rows = inputs()
    if args.build_only:
        current = [{**row, **previous.get(str(row['id']), {})} for row in rows]
    else:
        with ThreadPoolExecutor(max_workers=10) as pool:
            current = list(pool.map(lambda row: collect(row, previous), rows))
    articles = {**previous, **{str(row['id']): row for row in current}}
    book_payload = enrich_articles(articles, book_catalog(ROOT), ROOT)
    for row in articles.values():
        target = ROOT / 'news' / slug(row['id']) / 'index.html'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(build_page(row), encoding='utf-8')
    stats = {key: sum(r.get('status') == key for r in current) for key in ['ok', 'cached', 'unavailable']}
    result = {'generated_at': datetime.now(timezone.utc).isoformat(), 'counts': stats, 'articles': articles}
    CACHE.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(json.dumps({'pages': len(articles), 'current': len(current), **stats}))

if __name__ == '__main__':
    main()
