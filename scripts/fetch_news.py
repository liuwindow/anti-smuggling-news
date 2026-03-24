#!/usr/bin/env python3
"""
反走私新闻抓取脚本 v4
通过 Bing News 搜索 + 网页抓取获取全球反走私新闻
"""

import json, re, time, hashlib, logging, urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

CST = timezone(timedelta(hours=8))

KEYWORDS = [
    'smuggling', 'smuggler', 'contraband', 'drug trafficking',
    'wildlife trafficking', 'ivory', 'poaching', 'customs seizure',
    'illegal trade', 'counterfeit goods', 'money laundering',
    'human trafficking', 'cocaine seized', 'heroin seized',
    'fentanyl smuggling', 'arms trafficking', 'Interpol',
    'WCO customs', 'border patrol seized',
]

CATEGORY_RULES = [
    ('international', ['Interpol', 'WCO', 'overseas', 'international', 'foreign']),
    ('customs',       ['customs', 'seizure', 'border', 'port', 'airport']),
    ('police',        ['police', 'arrest', 'detained', 'raided', 'bust']),
    ('court',         ['court', 'sentenced', 'trial', 'prosecutor']),
    ('policy',        ['regulation', 'policy', 'law', 'ban']),
    ('domestic',      []),
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def keyword_match(text):
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in KEYWORDS)


def classify(title, summary, hint='domestic'):
    text = title + ' ' + summary
    for cat, words in CATEGORY_RULES:
        if any(w in text.lower() for w in words):
            return cat
    return hint


def make_id(title, source):
    return hashlib.md5(f"{source}:{title}".encode()).hexdigest()[:12]


def search_bing_news(query, max_results=20):
    """通过 Bing News 搜索获取新闻"""
    articles = []
    try:
        url = (
            f"https://www.bing.com/news/search?"
            f"q={urllib.parse.quote(query)}&"
            f"&first=0&"
            f"FORMAT=RSS"
        )
        log.info(f"Bing News: {query}")
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            log.warning(f"Bing HTTP {resp.status_code}")
            return articles

        text = resp.text
        # Parse RSS-like items from Bing News
        items = re.findall(r'<item>(.*?)</item>', text, re.DOTALL)
        if not items:
            # Try regex for bing's format
            items = re.findall(r'doc\.(.*?)/doc>', text, re.DOTALL)

        count = 0
        for item in items:
            if count >= max_results:
                break
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', item)
            link_match = re.search(r'<link[^>]*>([^<]+)</link>', item)
            desc_match = re.search(r'<description[^>]*>([^<]+)</description>', item)
            pub_match = re.search(r'<pubDate[^>]*>([^<]+)</pubDate>', item)
            source_match = re.search(r'<source[^>]*>([^<]+)</source>', item)

            title = title_match.group(1).strip() if title_match else ''
            if not title or not keyword_match(title):
                continue

            link = link_match.group(1).strip() if link_match else ''
            desc = desc_match.group(1).strip() if desc_match else ''
            # Clean HTML from description
            desc = re.sub(r'<[^>]+>', '', desc)[:200]
            pub = pub_match.group(1).strip() if pub_match else ''
            source = source_match.group(1).strip() if source_match else 'Bing News'

            # Parse date
            if pub:
                try:
                    dt = datetime.strptime(pub[:25], '%a, %d %b %Y %H:%M:%S')
                    dt = dt.replace(tzinfo=timezone.utc).astimezone(CST)
                    time_str = dt.strftime('%m-%d %H:%M')
                except:
                    time_str = datetime.now(CST).strftime('%m-%d %H:%M')
            else:
                time_str = datetime.now(CST).strftime('%m-%d %H:%M')

            articles.append({
                'id': make_id(title, source),
                'title': title,
                'summary': desc,
                'url': link,
                'source': source,
                'time': time_str,
                'category': classify(title, desc),
                'top': False,
            })
            count += 1
            log.info(f"  + {title[:60]}")

        log.info(f"  Bing '{query}': {len(articles)} articles")
    except Exception as e:
        log.warning(f"Bing News failed '{query}': {e}")
    return articles


def fetch_reuters_rss():
    """Reuters RSS"""
    articles = []
    try:
        url = 'https://feeds.reuters.com/reuters/worldNews'
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            log.warning(f"Reuters HTTP {resp.status_code}")
            return articles

        items = re.findall(r'<item>(.*?)</item>', resp.text, re.DOTALL)
        for item in items[:30]:
            title_m = re.search(r'<title><!\[CDATA\[([^\]]+)\]\]></title>', item)
            if not title_m:
                title_m = re.search(r'<title>([^<]+)</title>', item)
            title = title_m.group(1).strip() if title_m else ''
            if not keyword_match(title):
                continue
            link = re.search(r'<link>([^<]+)</link>', item)
            desc = re.search(r'<description><!\[CDATA\[([^\]]+)\]\]></description>', item)
            pub = re.search(r'<pubDate>([^<]+)</pubDate>', item)
            source = 'Reuters'
            articles.append({
                'id': make_id(title, source),
                'title': title,
                'summary': desc.group(1)[:200] if desc else '',
                'url': link.group(1) if link else '',
                'source': source,
                'time': pub.group(1)[:16] if pub else '',
                'category': classify(title, desc.group(1) if desc else ''),
                'top': False,
            })
    except Exception as e:
        log.warning(f"Reuters failed: {e}")
    return articles


def deduplicate(articles):
    seen = set()
    result = []
    for a in articles:
        if a['id'] not in seen:
            seen.add(a['id'])
            result.append(a)
    return result


def mark_top(articles, n=3):
    for i, a in enumerate(articles):
        a['top'] = (i < n)
    return articles


def main():
    all_articles = []

    # Bing News searches
    queries = [
        'customs smuggling seizure 2026',
        'drug trafficking arrest 2026',
        'wildlife trafficking ivory poachers',
        'Interpol anti-smuggling operation',
        'border police smuggling bust',
        'contraband drugs seized customs',
    ]

    for q in queries:
        arts = search_bing_news(q, max_results=15)
        all_articles.extend(arts)
        time.sleep(0.5)

    # Reuters
    reuters = fetch_reuters_rss()
    all_articles.extend(reuters)

    # 去重 + 排序
    all_articles = deduplicate(all_articles)
    all_articles.sort(key=lambda x: x['time'], reverse=True)
    all_articles = mark_top(all_articles, n=3)

    output = {
        'updated': datetime.now(CST).strftime('%Y-%m-%d %H:%M'),
        'count': len(all_articles),
        'articles': all_articles,
    }

    out_path = Path(__file__).parent.parent / 'data' / 'news.json'
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    log.info(f"Done! {len(all_articles)} articles -> {out_path}")


if __name__ == '__main__':
    main()
