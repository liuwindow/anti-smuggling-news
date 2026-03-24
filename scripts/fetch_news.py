#!/usr/bin/env python3
"""
反走私新闻抓取脚本 v3
使用 GDELT 全球新闻数据 + NewsAPI.org 免费 API
"""

import json, re, time, hashlib, logging, urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

CST = timezone(timedelta(hours=8))

KEYWORDS_EN = [
    'smuggling', 'smuggler', 'contraband', 'drug trafficking',
    'wildlife trafficking', 'ivory', 'poaching', 'customs seizure',
    'illegal trade', 'counterfeit goods', 'money laundering',
    'human trafficking', 'drugs seized', 'cocaine', 'heroin',
    'methamphetamine', 'fentanyl', 'arms trafficking',
]

KEYWORDS_CN = [
    '走私', '缉私', '打私', '偷逃税', '洗钱',
    '象牙', '濒危物种', '毒品', '冻品',
]

CATEGORY_RULES = [
    ('international', ['Interpol', 'WCO', '跨国', 'overseas', 'international']),
    ('customs',       ['customs', 'seizure', 'border', '海关', '缉私']),
    ('police',        ['police', 'arrest', '公安', '抓获', '侦破']),
    ('court',         ['court', 'sentenced', '法院', '判决']),
    ('policy',        ['regulation', 'policy', '规定', '条例']),
    ('domestic',      []),
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 AntiSmuggling-NewsBot/1.0',
}


def keyword_match(text):
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in KEYWORDS_EN + KEYWORDS_CN)


def classify(title, summary, hint='domestic'):
    text = title + ' ' + summary
    for cat, words in CATEGORY_RULES:
        if any(w in text for w in words):
            return cat
    return hint


def make_id(title, source):
    return hashlib.md5(f"{source}:{title}".encode()).hexdigest()[:12]


def fetch_gdelt(keyword='smuggling', max_results=50):
    """GDELT Global News API - 免费，无需API Key"""
    articles = []
    try:
        # GDELT Doc API
        url = (
            f"https://api.gdeltproject.org/api/v2/docseg/docseg?"
            f"query={urllib.parse.quote(keyword)}&"
            f"maxrecords={max_results}&"
            f"format=json&"
            f"sort=DateDesc&"
            f"lang=English"
        )
        log.info(f"GDELT: querying '{keyword}'")
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            log.warning(f"GDELT HTTP {resp.status_code}")
            return articles

        data = resp.json()
        articles_data = data.get('articles', [])
        log.info(f"GDELT '{keyword}': {len(articles_data)} articles")

        for art in articles_data[:30]:
            title = art.get('title', '').strip()
            if not title or not keyword_match(title):
                continue
            summary = art.get('seendate', '')[:50]
            url_art = art.get('url', '')
            source = art.get('domain', '')
            raw_date = art.get('seendate', '')
            # Format date
            if raw_date and len(raw_date) >= 8:
                time_str = raw_date[4:6] + '-' + raw_date[6:8] + ' ' + raw_date[8:10] + ':' + raw_date[10:12]
            else:
                time_str = datetime.now(CST).strftime('%m-%d %H:%M')

            articles.append({
                'id': make_id(title, source),
                'title': title,
                'summary': summary,
                'url': url_art,
                'source': source,
                'time': time_str,
                'category': classify(title, '', source),
                'top': False,
            })
    except Exception as e:
        log.warning(f"GDELT failed: {e}")
    return articles


def fetch_newsapi(keyword, api_key=None):
    """NewsAPI.org - 免费额度每天100条"""
    if not api_key:
        return []
    articles = []
    try:
        url = (
            f"https://newsapi.org/v2/everything?"
            f"q={urllib.parse.quote(keyword)}&"
            f"language=en&"
            f"sortBy=publishedAt&"
            f"pageSize=30&"
            f"apiKey={api_key}"
        )
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            log.warning(f"NewsAPI HTTP {resp.status_code}")
            return articles
        data = resp.json()
        for art in data.get('articles', []):
            title = art.get('title', '')
            if not title or not keyword_match(title):
                continue
            articles.append({
                'id': make_id(title, art.get('source', {}).get('name', '')),
                'title': title,
                'summary': art.get('description', '')[:200],
                'url': art.get('url', ''),
                'source': art.get('source', {}).get('name', ''),
                'time': art.get('publishedAt', '')[:16].replace('T', ' '),
                'category': classify(title, art.get('description', '')),
                'top': False,
            })
    except Exception as e:
        log.warning(f"NewsAPI failed: {e}")
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

    # GDELT - multiple search queries
    queries = [
        'smuggling seizure customs',
        'drug trafficking arrest',
        'wildlife trafficking ivory',
        'customs police raid',
        'contraband border',
    ]

    for q in queries:
        articles = fetch_gdelt(q, max_results=30)
        all_articles.extend(articles)
        log.info(f"  -> total so far: {len(all_articles)}")
        time.sleep(0.5)

    # NewsAPI (if key provided via env)
    api_key = os.environ.get('NEWSAPI_KEY', '')
    if api_key:
        for q in ['smuggling customs', 'drug trafficking', 'wildlife crime']:
            all_articles.extend(fetch_newsapi(q, api_key))
            time.sleep(0.5)

    # 去重 + 排序
    all_articles = deduplicate(all_articles)
    all_articles.sort(key=lambda x: x['time'], reverse=True)
    all_articles = mark_top(all_articles, n=3)

    # 输出
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
    import os
    main()
