#!/usr/bin/env python3
"""
反走私新闻聚合抓取脚本 v2
使用 Google News / Bing News RSS + 国际新闻源
解决 GitHub Actions 访问国内网站 403 的问题
"""

import json, re, time, hashlib, logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import feedparser
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

CST = timezone(timedelta(hours=8))

# ── 关键词（中英双语）──
KEYWORDS = [
    '走私', '缉私', '反走私', '打私',
    '海关查获', '海关缉私',
    'smuggling', 'anti-smuggling', 'customs seizure',
    'drug trafficking', 'wildlife trafficking', 'contraband',
    'Interpol', 'WCO customs', 'seizure',
]

CATEGORY_RULES = [
    ('international', ['Interpol', 'WCO', '跨国', '国际联合', 'international', 'overseas']),
    ('customs',       ['海关', '缉私', 'customs', 'seizure', 'border']),
    ('police',        ['公安', '警察', '侦破', '抓获', 'arrest', 'police']),
    ('court',         ['法院', '检察', '判决', 'sentenced', 'court']),
    ('policy',        ['规定', '条例', '法规', 'policy', 'regulation']),
    ('domestic',      []),
]

RSS_SOURCES = [
    # 国际新闻源（可从 GitHub Actions 访问）
    {
        'name': 'Reuters World',
        'url': 'https://feeds.reuters.com/reuters/worldnews',
        'category_hint': 'international',
    },
    {
        'name': 'AP News World',
        'url': 'https://feeds.apnews.com/apnews/worldnews',
        'category_hint': 'international',
    },
    # Google News RSS（搜索结果）
    {
        'name': 'Google News - Smuggling',
        'url': 'https://news.google.com/rss/search?q=smuggling+OR+anti-smuggling+OR+customs+seizure&hl=en-US&gl=US&ceid=US:en',
        'category_hint': 'international',
    },
    {
        'name': 'Google News - Wildlife',
        'url': 'https://news.google.com/rss/search?q=wildlife+trafficking+OR+ivory+smuggling&hl=en-US&gl=US&ceid=US:en',
        'category_hint': 'international',
    },
    {
        'name': 'Google News - Drug',
        'url': 'https://news.google.com/rss/search?q=drug+trafficking+china+OR+asia&hl=en-US&gl=US&ceid=US:en',
        'category_hint': 'international',
    },
    # 国内可访问的新闻聚合
    {
        'name': 'BBC World',
        'url': 'http://feeds.bbci.co.uk/news/world/rss.xml',
        'category_hint': 'international',
    },
    {
        'name': 'Al Jazeera',
        'url': 'https://www.aljazeera.com/xml/rss/all.xml',
        'category_hint': 'international',
    },
    # 英文中国新闻（可替代国内源）
    {
        'name': 'SCMP China News',
        'url': 'https://www.scmp.com/rss/world/asia/china/feed',
        'category_hint': 'domestic',
    },
    {
        'name': 'Sixth Tone',
        'url': 'https://www.sixthtone.com/rss.xml',
        'category_hint': 'domestic',
    },
    # 英文反走私专业来源
    {
        'name': 'WCO News',
        'url': 'https://www.wcoomd.org/en/media/press-room/wco-news.rss',
        'category_hint': 'international',
    },
    {
        'name': 'Interpol Notices',
        'url': 'https://www.interpol.int/How-we-work/Notices/View-UN-Notices/rss',
        'category_hint': 'international',
    },
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; AntiSmuggling-NewsBot/1.0; +https://github.com/liuwindow/anti-smuggling-news)',
    'Accept-Language': 'en-US,en;q=0.9',
}


def keyword_match(text: str) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in KEYWORDS)


def classify(title: str, summary: str, hint: str = 'domestic') -> str:
    text = title + ' ' + summary
    for cat, words in CATEGORY_RULES:
        if any(w in text for w in words):
            return cat
    return hint


def make_id(title: str, source: str) -> str:
    return hashlib.md5(f"{source}:{title}".encode()).hexdigest()[:12]


def fetch_rss(source: dict) -> list:
    articles = []
    try:
        log.info(f"RSS: {source['name']}")
        feed = feedparser.parse(source['url'], headers=HEADERS, timeout=15)
        for entry in feed.entries[:40]:
            title = entry.get('title', '').strip()
            # 清理 HTML
            summary = ''
            raw_summary = entry.get('summary') or entry.get('description') or ''
            if raw_summary:
                summary = BeautifulSoup(raw_summary, 'html.parser').get_text()[:200].strip()
            
            link = ''
            for lk in ['link', 'id']:
                v = entry.get(lk, '')
                if v and v.startswith('http'):
                    link = v
                    break

            if not keyword_match(title + ' ' + summary):
                continue

            # 解析时间
            pub = entry.get('published_parsed') or entry.get('updated_parsed')
            if pub:
                dt = datetime(*pub[:6], tzinfo=timezone.utc).astimezone(CST)
                time_str = dt.strftime('%m-%d %H:%M')
            else:
                time_str = datetime.now(CST).strftime('%m-%d %H:%M')

            articles.append({
                'id': make_id(title, source['name']),
                'title': title,
                'summary': summary,
                'url': link,
                'source': source['name'],
                'time': time_str,
                'category': classify(title, summary, source.get('category_hint', 'domestic')),
                'top': False,
            })
            log.info(f"  + {title[:60]}")
        log.info(f"  -> {len(articles)} articles from {source['name']}")
    except Exception as e:
        log.warning(f"RSS failed {source['name']}: {e}")
    return articles


def deduplicate(articles: list) -> list:
    seen = set()
    result = []
    for a in articles:
        if a['id'] not in seen:
            seen.add(a['id'])
            result.append(a)
    return result


def mark_top(articles: list, n: int = 3) -> list:
    for i, a in enumerate(articles):
        a['top'] = (i < n)
    return articles


def main():
    all_articles = []

    for src in RSS_SOURCES:
        articles = fetch_rss(src)
        all_articles.extend(articles)
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
    main()
