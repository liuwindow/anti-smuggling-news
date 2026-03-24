#!/usr/bin/env python3
"""
反走私新闻聚合抓取脚本
每日 09:00 由 GitHub Actions 自动运行
输出: data/news.json
"""

import json
import re
import time
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

# ── 北京时间 ──
CST = timezone(timedelta(hours=8))

# ── 关键词过滤（命中任意一个即保留）──
KEYWORDS = [
    '走私', '缉私', '反走私', '打私', '查私',
    '海关查获', '海关查扣', '海关缉私',
    '走私毒品', '走私象牙', '走私冻品', '走私车辆',
    '跨境走私', '边境走私', '网络走私',
    '濒危物种走私', '野生动物走私',
    '洗钱', '地下钱庄',
    'smuggling', 'anti-smuggling', 'customs seizure',
    'drug trafficking', 'wildlife trafficking',
    'Interpol', 'WCO customs',
]

# ── 分类规则 ──
CATEGORY_RULES = [
    ('international', ['Interpol', 'WCO', '国际刑警', '世界海关', '跨国', '国际联合', 'international']),
    ('customs',       ['海关', '缉私', '关税', 'customs']),
    ('police',        ['公安', '警察', '刑警', '侦破', '抓获', '逮捕', 'police', 'arrest']),
    ('court',         ['法院', '检察', '判决', '起诉', '庭审', '宣判', 'court', 'sentenced']),
    ('policy',        ['规定', '条例', '法规', '政策', '通知', '公告', '修订', 'regulation', 'policy']),
    ('domestic',      []),  # 默认
]

# ── RSS 数据源 ──
RSS_SOURCES = [
    # 国内官方
    {
        'name': '海关总署',
        'url': 'http://www.customs.gov.cn/customs/xwfb/index_rss.xml',
        'category_hint': 'customs',
    },
    {
        'name': '新华社',
        'url': 'https://feeds.xinhuanet.com/news/society.xml',
        'category_hint': 'domestic',
    },
    # 备用：通过关键词搜索抓取
    {
        'name': '人民日报',
        'url': 'http://www.people.com.cn/rss/politics.xml',
        'category_hint': 'domestic',
    },
    # 国际
    {
        'name': 'Interpol News',
        'url': 'https://www.interpol.int/en/News-and-Events/News/rss',
        'category_hint': 'international',
    },
    {
        'name': 'WCO News',
        'url': 'http://www.wcoomd.org/en/media/newsroom/rss.xml',
        'category_hint': 'international',
    },
]

# ── 网页抓取源（无 RSS 时直接抓页面）──
SCRAPE_SOURCES = [
    {
        'name': '海关总署新闻',
        'url': 'http://www.customs.gov.cn/customs/xwfb/index.html',
        'item_selector': '.news-list li, .list-content li',
        'title_selector': 'a',
        'category_hint': 'customs',
    },
    {
        'name': '公安部新闻',
        'url': 'http://www.mps.gov.cn/n2254098/n4904352/index.html',
        'item_selector': '.news-list li',
        'title_selector': 'a',
        'category_hint': 'police',
    },
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; AntiSmuggling-NewsBot/1.0)',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


def keyword_match(text: str) -> bool:
    """判断文本是否包含反走私相关关键词"""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in KEYWORDS)


def classify(title: str, summary: str, hint: str = 'domestic') -> str:
    """根据标题+摘要自动分类"""
    text = title + ' ' + summary
    for cat, words in CATEGORY_RULES:
        if any(w in text for w in words):
            return cat
    return hint


def make_id(title: str, source: str) -> str:
    return hashlib.md5(f"{source}:{title}".encode()).hexdigest()[:12]


def fetch_rss(source: dict) -> list:
    """抓取 RSS 源"""
    articles = []
    try:
        log.info(f"RSS: {source['name']} <- {source['url']}")
        feed = feedparser.parse(source['url'])
        for entry in feed.entries[:30]:
            title = entry.get('title', '').strip()
            summary = BeautifulSoup(
                entry.get('summary', entry.get('description', '')), 'html.parser'
            ).get_text()[:200].strip()
            link = entry.get('link', '')

            if not keyword_match(title + ' ' + summary):
                continue

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
    except Exception as e:
        log.warning(f"RSS 抓取失败 {source['name']}: {e}")
    return articles


def fetch_scrape(source: dict) -> list:
    """直接抓取网页"""
    articles = []
    try:
        log.info(f"Scrape: {source['name']} <- {source['url']}")
        resp = requests.get(source['url'], headers=HEADERS, timeout=15)
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.select(source['item_selector'])[:20]
        for item in items:
            a = item.select_one(source['title_selector'])
            if not a:
                continue
            title = a.get_text().strip()
            href = a.get('href', '')
            if href and not href.startswith('http'):
                from urllib.parse import urljoin
                href = urljoin(source['url'], href)

            if not keyword_match(title):
                continue

            articles.append({
                'id': make_id(title, source['name']),
                'title': title,
                'summary': '',
                'url': href,
                'source': source['name'],
                'time': datetime.now(CST).strftime('%m-%d %H:%M'),
                'category': classify(title, '', source.get('category_hint', 'domestic')),
                'top': False,
            })
    except Exception as e:
        log.warning(f"网页抓取失败 {source['name']}: {e}")
    return articles


def deduplicate(articles: list) -> list:
    """去重（按 id）"""
    seen = set()
    result = []
    for a in articles:
        if a['id'] not in seen:
            seen.add(a['id'])
            result.append(a)
    return result


def mark_top(articles: list, n: int = 3) -> list:
    """将前 n 条标记为头条"""
    for i, a in enumerate(articles):
        a['top'] = (i < n)
    return articles


def main():
    all_articles = []

    # 抓 RSS
    for src in RSS_SOURCES:
        all_articles.extend(fetch_rss(src))
        time.sleep(1)

    # 抓网页
    for src in SCRAPE_SOURCES:
        all_articles.extend(fetch_scrape(src))
        time.sleep(1)

    # 去重 + 排序（按时间倒序）
    all_articles = deduplicate(all_articles)
    all_articles.sort(key=lambda x: x['time'], reverse=True)

    # 标记头条
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
    log.info(f"✅ 完成，共 {len(all_articles)} 条新闻 -> {out_path}")


if __name__ == '__main__':
    main()
