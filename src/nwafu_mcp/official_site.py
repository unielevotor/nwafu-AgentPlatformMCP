# -*- coding: utf-8 -*-
"""西北农林科技大学官网数据层。

学校主站与新闻网使用通元 CMS 全文检索接口：
  GET https://www.nwsuaf.edu.cn/cms/web/search/index.jsp
    ?query=<关键词>&siteID=<站点ID>&searchScope=0&channelID=&matchType=0
    &sortField=publishDate&order=1&position=&date=<3|6|12>&page=<页码>

siteID=32e6d9be... 为主站（索引覆盖全校各学院/部门），siteID=3 为新闻网。
响应为服务端渲染 HTML，结果项结构：
  <li><div class="search01"><a href="URL"><h2>标题</h2></a>
  <span><label>日期</label><label>来源</label></span><span>URL</span><p>摘要</p></div></li>
"""

from __future__ import annotations

import html
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import config

LOG = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# 分类 -> 检索词（用于"近期通知/活动/竞赛"等快速查询）
CATEGORY_QUERIES: Dict[str, List[str]] = {
    "通知": ["通知", "公告"],
    "活动": ["活动", "讲座", "论坛", "沙龙", "报告会", "演出", "展览", "宣讲会"],
    "竞赛": ["竞赛", "比赛", "大赛", "挑战赛", "创新创业大赛"],
    "招聘": ["招聘", "选调生", "宣讲会", "就业"],
}

# 分类 -> 客户端过滤词（keyword 做主查询时，按这些词在标题/摘要中过滤归类）
CATEGORY_FILTERS: Dict[str, List[str]] = {
    "通知": ["通知", "公告", "公示"],
    "活动": ["活动", "讲座", "论坛", "沙龙", "报告会", "演出", "展览", "宣讲"],
    "竞赛": ["竞赛", "比赛", "大赛", "挑战赛", "杯"],
    "招聘": ["招聘", "选调", "宣讲会", "就业", "岗位"],
}

CATEGORY_ALIASES = {
    "全部": "全部",
    "all": "全部",
    "通知": "通知",
    "notice": "通知",
    "公告": "通知",
    "活动": "活动",
    "activity": "活动",
    "讲座": "活动",
    "论坛": "活动",
    "竞赛": "竞赛",
    "比赛": "竞赛",
    "contest": "竞赛",
    "招聘": "招聘",
    "job": "招聘",
    "就业": "招聘",
}


def normalize_category(category: str) -> str:
    return CATEGORY_ALIASES.get(category.strip(), "全部")


def _default_headers() -> Dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.nwsuaf.edu.cn/",
    }


def _months_for_days(days: int) -> int:
    if days <= 90:
        return 3
    if days <= 180:
        return 6
    return 12


def _clean_title(title: str) -> str:
    title = re.sub(r"<[^>]+>", "", title)
    title = html.unescape(title)
    title = re.sub(r"&nbsp;|&ensp;|&emsp;", " ", title)
    title = re.sub(r"\s*[-–—]\[链\]\s*$", "", title).strip()
    return re.sub(r"\s+", " ", title).strip()


def _parse_date(raw: str) -> str:
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


def _parse_search_page(page_html: str) -> List[Dict[str, Any]]:
    """解析通元 CMS 搜索结果页，返回 [{title,url,date,source,snippet}]。"""
    items: List[Dict[str, Any]] = []
    blocks = re.findall(
        r'<li>\s*<div class="search01">\s*<a href="([^"]+)"[^>]*>\s*<h2>(.*?)</h2>\s*</a>'
        r"([\s\S]*?)</div>\s*</li>",
        page_html,
    )
    for raw_url, raw_title, rest in blocks:
        title = _clean_title(raw_title)
        if not title:
            continue
        url = html.unescape(raw_url).strip()
        labels = re.findall(r"<label>(.*?)</label>", rest)
        source = ""
        date = ""
        for lab in labels:
            text = html.unescape(re.sub(r"<[^>]+>", "", lab)).strip()
            if re.search(r"\d{4}年|\d{4}-", text):
                date = _parse_date(text)
            elif text:
                source = text
        snippet = ""
        pm = re.search(r"<p>(.*?)</p>", rest, re.S)
        if pm:
            snippet = html.unescape(re.sub(r"<[^>]+>", "", pm.group(1))).strip()
            snippet = re.sub(r"\s+", " ", snippet)
        items.append(
            {
                "title": title,
                "url": url,
                "date": date,
                "source": source,
                "snippet": snippet[:300],
            }
        )
    return items


def _days_ok(date_str: str, days: int) -> bool:
    if not date_str or days <= 0:
        return True
    try:
        y, m, d = (int(x) for x in date_str.split("-"))
        import datetime

        item = datetime.date(y, m, d)
        today = datetime.date.today()
        return (today - item).days <= days
    except (ValueError, TypeError):
        return True


def search(
    query: str,
    site_id: str = "",
    days: int = 0,
    max_results: int = 20,
    timeout: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """站内全文检索（单个关键词）。

    注意：该索引对空格分隔的多词查询会做严格 AND 匹配，基本无结果；
    需要多词检索时请使用 search_terms 逐词查询后合并。
    """
    query = query.strip()
    if not query:
        return []
    site_id = site_id or config.MAIN_SITE_ID

    timeout = timeout or config.get_timeout()
    months = _months_for_days(days) if days > 0 else ""
    params = {
        "query": query,
        "siteID": site_id,
        "searchScope": "0",
        "channelID": "",
        "matchType": "0",
        "sortField": "publishDate",
        "order": "1",
        "position": "",
        "date": str(months),
        "page": "1",
    }

    results: List[Dict[str, Any]] = []
    seen_urls = set()
    max_results = max(1, min(max_results, 50))

    for page in range(1, 6):
        if len(results) >= max_results:
            break
        params["page"] = str(page)
        try:
            resp = requests.get(
                config.SEARCH_URL,
                params=params,
                headers=_default_headers(),
                timeout=timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            if page == 1:
                raise RuntimeError(f"官网搜索请求失败：{e}") from e
            break
        items = _parse_search_page(resp.text)
        if not items:
            break
        new_count = 0
        for it in items:
            if it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            if not _days_ok(it["date"], days):
                continue
            results.append(it)
            new_count += 1
            if len(results) >= max_results:
                break
        if new_count == 0:
            break
        if len(items) < 10:
            break
        time.sleep(0.2)
    return results


def search_terms(
    terms: List[str],
    days: int = 0,
    max_results: int = 20,
) -> List[Dict[str, Any]]:
    """多词检索：逐词查询后合并，按命中词数加权排序。"""
    terms = [t.strip() for t in terms if t and t.strip()]
    if not terms:
        return []
    merged: List[Dict[str, Any]] = []
    seen = set()
    per_term = max(1, min(15, max_results))
    for term in terms[:5]:
        try:
            items = search(term, days=days, max_results=per_term)
        except RuntimeError as e:
            LOG.warning("检索词 %s 失败: %s", term, e)
            continue
        for it in items:
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            text = f"{it.get('title') or ''} {it.get('snippet') or ''}"
            it["_hits"] = sum(1 for t in terms if t and t in text)
            merged.append(it)
        time.sleep(0.15)
    merged.sort(key=lambda x: (x["_hits"], x.get("date") or ""), reverse=True)
    if len(terms) > 1:
        # 多词检索时，标题/摘要都未命中任何词的弱结果直接剔除
        with_hits = [it for it in merged if it["_hits"] > 0]
        if with_hits:
            merged = with_hits
    return merged[: max(1, min(max_results, 50))]


def _matches_category(item: Dict[str, Any], category: str) -> bool:
    terms = CATEGORY_FILTERS.get(category) or []
    text = f"{item.get('title') or ''} {item.get('snippet') or ''}"
    return any(t in text for t in terms)


def search_by_category(
    category: str = "全部",
    keyword: str = "",
    days: int = 90,
    max_results: int = 20,
) -> List[Dict[str, Any]]:
    """按分类快速检索官网最近信息；keyword 用于缩小范围（如学院名）。"""
    category = normalize_category(category)
    keyword = keyword.strip()
    results: List[Dict[str, Any]] = []
    seen_urls = set()

    if keyword:
        # 关键词做主查询，再用分类词在客户端过滤归类
        try:
            items = search(keyword, days=days, max_results=max_results)
        except RuntimeError as e:
            LOG.warning("关键词 %s 检索失败: %s", keyword, e)
            items = []
        for it in items:
            if it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            if category == "全部":
                for cat, terms in CATEGORY_FILTERS.items():
                    if any(t in f"{it.get('title') or ''} {it.get('snippet') or ''}" for t in terms):
                        it["category"] = cat
                        break
                else:
                    it["category"] = "其他"
            else:
                if not _matches_category(it, category):
                    continue
                it["category"] = category
            results.append(it)
            if len(results) >= max_results:
                break
        return results

    # 无关键词：按分类检索词逐词查询
    if category == "全部":
        queries = [q for terms in CATEGORY_QUERIES.values() for q in terms[:2]]
    else:
        queries = CATEGORY_QUERIES.get(category, CATEGORY_QUERIES["通知"])
    per_query = max(1, min(12, max_results))
    for q in queries:
        if len(results) >= max_results:
            break
        try:
            items = search(q, days=days, max_results=per_query)
        except RuntimeError as e:
            LOG.warning("检索词 %s 失败: %s", q, e)
            continue
        for it in items:
            if it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            it["category"] = category
            results.append(it)
            if len(results) >= max_results:
                break
        time.sleep(0.15)
    return results


def search_news(
    query: str,
    days: int = 0,
    max_results: int = 20,
) -> List[Dict[str, Any]]:
    """仅在新闻网范围内检索（siteID=3）。"""
    return search(query, site_id=config.NEWS_SITE_ID, days=days, max_results=max_results)
