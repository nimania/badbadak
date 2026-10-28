"""Evidence-backed book mentions shared with the independent Pishkhan catalog."""
import gzip
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from urllib.request import urlopen

PISHKHAN = 'https://nimania.github.io/pishkhan/'
BADBADAK = 'https://nimania.github.io/badbadak/'

def norm(value):
    value = unicodedata.normalize('NFKC', str(value or '')).translate(str.maketrans({'ي':'ی','ك':'ک','ۀ':'ه','ة':'ه','\u200c':' '}))
    value = re.sub(r'[\u064b-\u065f\u0670]', '', value)
    return ' '.join(re.findall(r'[\w]+', value.casefold()))

def catalog(root):
    path = Path(root) / 'data/pishkhan-book-index.json'
    try:
        with urlopen(PISHKHAN+'data/books.json', timeout=20) as response:
            data = json.load(response)
        rows = [{key:b.get(key) for key in ['slug','title_fa','creators','record_type']} for b in data['books']]
        path.write_text(json.dumps(rows, ensure_ascii=False, separators=(',',':')))
        return rows
    except Exception:
        return json.loads(path.read_text()) if path.exists() else []

def detect(article, books):
    content = article.get('title','') + '\n' + '\n'.join(b.get('text','') for b in article.get('blocks',[]) if b.get('type') in ('paragraph','heading'))
    known = {}
    for book in books:
        known.setdefault(norm(book.get('title_fa')), []).append(book)
    candidates = []
    # A quoted title explicitly called a book, novel, play or poetry collection.
    for m in re.finditer(r'(?:کتاب|رمان|نمایشنامه|نمایش‌نامه|مجموعه[ٔ\s]+(?:داستان|شعر))\s*(?:با\s+نام|با\s+عنوان|به\s+نام|به\s+عنوان)?\s*[«"]([^«»"\n]{2,100})[»"]', content):
        candidates.append((m.group(1), '', m.start(), m.end()))
    # A named literary work with its author. The evidence itself identifies it.
    for m in re.finditer(r'«([^«»\n]{2,100})»\s+(?:اثر|نوشتهٔ|نوشته‌ی|نوشته\s+ی)\s+([^،؛.!؟\n]{3,55})', content):
        if re.search(r'کتاب|رمان|تراژدی|نمایشنامه|داستان|شعر', content[max(0,m.start()-110):m.start()]):
            candidates.append((m.group(1), m.group(2).strip(), m.start(), m.end()))
    # Catalog titles only count in a nearby literary context; never substring-match e.g. بوستان چیتگر.
    for m in re.finditer(r'«([^«»\n]{2,100})»', content):
        if norm(m.group(1)) in known and re.search(r'(?<![آ-ی])(?:کتاب|رمان|نمایشنامه|نویسنده)(?![آ-ی])',content[max(0,m.start()-100):m.end()+100]):
            if not re.search(r'چند|چهار|هم.?نام',content[max(0,m.start()-50):m.start()]):
                candidates.append((m.group(1), '', m.start(), m.end()))
    result = {}
    for title, author, start, end in candidates:
        key = norm(title)
        if not key or len(key)<3:
            continue
        matches = known.get(key, [])
        if len(matches)>1 and author:
            matches = [b for b in matches if any(norm(author)==norm(c.get('name_fa')) for c in b.get('creators') or [])]
        if len(matches)>1:
            # Ambiguous editions/authors: do not guess which distinct book is meant.
            continue
        match = matches[0] if matches else None
        slug = match['slug'] if match else 'news-book-'+hashlib.sha256(key.encode()).hexdigest()[:16]
        creators = match.get('creators') or [] if match else ([{'name_fa':author,'role_fa':'نویسنده','slug':'news-person-'+hashlib.sha256(norm(author).encode()).hexdigest()[:12]}] if author else [])
        result[slug] = {'slug':slug, 'title_fa':match.get('title_fa') if match else title, 'creators':creators, 'existing_catalog_book':bool(match), 'evidence_excerpt':content[max(0,start-100):min(len(content),end+160)]}
    return list(result.values())

def enrich_articles(articles, books, root):
    grouped = {}
    for article in articles.values():
        mentions = detect(article, books)
        article['books'] = mentions
        news_slug = re.sub(r'[^A-Za-z0-9_-]', '_', str(article['id']))
        news_url = BADBADAK+'news/'+news_slug+'/'
        for book in mentions:
            entry = grouped.setdefault(book['slug'], {**book, 'mentions':[]})
            entry['mentions'].append({'kind':'badbadak','source_name':'بادبادک / '+article['source'], 'headline_fa':article['title'], 'summary_fa':book['evidence_excerpt'], 'url':news_url,'original_source_url':article['url'],'published_at':article.get('published',''),'evidence_excerpt':book['evidence_excerpt']})
    payload = {'schema_version':1, 'source_site':BADBADAK, 'books':list(grouped.values())}
    (Path(root)/'data/book-mentions.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')))
    return payload
