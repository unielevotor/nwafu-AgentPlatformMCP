# -*- coding: utf-8 -*-
"""西北农林科技大学校园信息 MCP 服务器。

提供四个工具：
  1. campus_channel_summary  —— 校园 QQ 频道近期热门帖子智能总结（分类 + 引用来源）
  2. official_site_recent    —— 官网最近通知/活动/竞赛/招聘快速查询与总结（支持关键词缩小范围）
  3. official_site_search    —— 官网全文检索（自定义关键词）
  4. campus_question_search  —— 跨"官网 + 校园频道"的自定义问题检索

运行：`nwafu-mcp`（stdio 传输，适配 Claude Desktop / Cursor / 各类 MCP 客户端）
"""

from __future__ import annotations

import logging
import re
from typing import List

from mcp.server.fastmcp import FastMCP

from . import classify, config, format, official_site, qq_channel

LOG = logging.getLogger(__name__)

mcp = FastMCP(
    "nwafu-campus-tools",
    instructions=(
        "西北农林科技大学校园信息工具集：总结校园 QQ 频道近期热门帖子、"
        "查询学校官网的通知/活动/竞赛/招聘，并支持跨站自定义检索。"
        "所有工具输出均为 Markdown 排版，重要信息会附上来源帖子/原文标题与链接。"
    ),
)


# ---------------------------------------------------------------- 工具 1

@mcp.tool(description=(
    "抓取西北农林科技大学官方 QQ 频道（https://pd.qq.com/g/inwafu1934）"
    "近期帖子，按互动量（点赞+评论）排名出热度榜，并自动归类为"
    "活动/竞赛/通知/推荐/贴士/求助/其他，输出 Markdown 总结；"
    "每条重要信息都附来源帖子标题与链接。"
))
def campus_channel_summary(
    window_hours: int = 72,
    max_posts: int = 60,
    top_n: int = 8,
    include_comments: bool = False,
    comment_top_n: int = 3,
) -> str:
    """总结校园 QQ 频道近期热门帖子。

    Args:
        window_hours: 只看最近多少小时内的帖子（默认 72）。
        max_posts: 最多抓取帖子数（默认 60，20 的倍数更高效）。
        top_n: 热度榜展示条数（默认 8）。
        include_comments: 是否为热度榜前列帖子抓取热评（会稍慢，默认关闭）。
        comment_top_n: 每帖热评条数（默认 3）。

    Returns:
        Markdown 格式的总结报告。
    """
    try:
        return _channel_summary_impl(
            window_hours=window_hours,
            max_posts=max_posts,
            top_n=top_n,
            include_comments=include_comments,
            comment_top_n=comment_top_n,
        )
    except qq_channel.QQChannelError as e:
        return f"⚠️ {e}"
    except Exception as e:  # noqa: BLE001
        LOG.exception("campus_channel_summary 失败")
        return f"⚠️ 频道总结失败：{e}\n\n请稍后重试；如持续失败可检查网络或刷新 Cookie。"


def _channel_summary_impl(
    window_hours: int,
    max_posts: int,
    top_n: int,
    include_comments: bool,
    comment_top_n: int,
) -> str:
    cookie = config.get_cookie()
    guild_id = config.get_guild_id()
    channel_id = config.get_channel_id()
    client = qq_channel.QQChannelClient(cookie, guild_id, channel_id)

    window_hours = max(1, min(window_hours, 24 * 30))
    max_posts = max(10, min(max_posts, 200))
    top_n = max(1, min(top_n, 15))
    since_ts = None
    if window_hours:
        import time as _time

        since_ts = int(_time.time()) - window_hours * 3600

    max_pages = max(1, (max_posts + 19) // 20)
    feeds = client.fetch_feeds(
        max_pages=max_pages,
        limit=max_posts,
        since_timestamp=since_ts,
    )
    if not feeds:
        return (
            f"近 {window_hours} 小时内频道暂无新帖子（或未抓取到数据）。"
            "可调大 `window_hours` 或 `max_posts` 后重试。"
        )

    for item in feeds:
        item["_score"] = classify.hot_score(item)
    feeds.sort(key=lambda x: (x["_score"], x["publish_time"]), reverse=True)

    hot = feeds[:top_n]
    if include_comments and hot:
        for item in hot:
            try:
                item["hot_comments"] = client.fetch_hot_comments(
                    item["_feed_id"], top_n=comment_top_n
                )
            except Exception as e:  # noqa: BLE001
                LOG.warning("热评获取失败 %s: %s", item["_feed_id"], e)
                item["hot_comments"] = []

    groups = classify.group_by_category(feeds, per_category=5)
    important = [it for it in feeds if classify.is_important(it)][:8]

    meta = {
        "fetched_at": format.now_str(),
        "guild_id": guild_id,
        "channel_id": channel_id,
        "window_hours": window_hours,
        "post_count": len(feeds),
    }
    return format.build_channel_report(meta, hot, groups, important)


# ---------------------------------------------------------------- 工具 2

@mcp.tool(description=(
    "查询西北农林科技大学官网（https://www.nwafu.edu.cn/）最近的活动、竞赛、"
    "通知、招聘等官方信息并输出 Markdown 总结。支持传入关键词（如学院名）"
    "缩小检索范围，例如 keyword='植保学院' 只返回植保学院相关通知。"
))
def official_site_recent(
    category: str = "全部",
    keyword: str = "",
    days: int = 90,
    max_results: int = 20,
) -> str:
    """快速查询官网最近信息。

    Args:
        category: 分类：全部 / 通知 / 活动 / 竞赛 / 招聘（也接受 公告/讲座/比赛 等别名）。
        keyword: 缩小范围的关键词，如“植保学院”“教务处”“奖学金”。
        days: 只看最近多少天（默认 90；支持 1–365）。
        max_results: 最多返回条数（默认 20，上限 50）。

    Returns:
        Markdown 格式的结果列表与要点提示。
    """
    try:
        cat = official_site.normalize_category(category)
        items = official_site.search_by_category(
            category=cat,
            keyword=keyword,
            days=max(1, min(days, 365)),
            max_results=max(1, min(max_results, 50)),
        )
        meta = {
            "fetched_at": format.now_str(),
            "category": cat,
            "keyword": keyword,
            "days": max(1, min(days, 365)),
        }
        return format.build_official_report(meta, items)
    except Exception as e:  # noqa: BLE001
        LOG.exception("official_site_recent 失败")
        return f"⚠️ 官网查询失败：{e}\n\n请稍后重试，或检查网络连接。"


# ---------------------------------------------------------------- 工具 3

@mcp.tool(description=(
    "对西北农林科技大学官网（含新闻网）执行关键词全文检索，"
    "返回 Markdown 排版的结果列表（标题/日期/来源/摘要/原文链接）。"
))
def official_site_search(
    query: str,
    keyword: str = "",
    days: int = 90,
    max_results: int = 20,
) -> str:
    """官网全文检索。

    Args:
        query: 核心关键词，如“奖学金”“运动会”“选调生”。
        keyword: 附加检索词（如学院名），会与 query 分别检索后合并结果。
        days: 只看最近多少天（0 = 不限时间，默认 90）。
        max_results: 最多返回条数（默认 20，上限 50）。

    Returns:
        Markdown 格式的检索结果。
    """
    try:
        days = max(0, min(days, 365))
        terms = [t for t in re.split(r"[,，;；\s]+", query or "") if t.strip()]
        if keyword.strip():
            terms.append(keyword.strip())
        terms = list(dict.fromkeys(terms))
        limit = max(1, min(max_results, 50))
        if len(terms) > 1:
            items = official_site.search_terms(terms, days=days, max_results=limit)
        else:
            items = official_site.search(
                terms[0] if terms else "", days=days, max_results=limit
            )
        meta = {
            "fetched_at": format.now_str(),
            "category": "检索",
            "keyword": " ".join(terms),
            "days": days or 0,
        }
        return format.build_official_report(meta, items)
    except Exception as e:  # noqa: BLE001
        LOG.exception("official_site_search 失败")
        return f"⚠️ 官网检索失败：{e}\n\n请稍后重试，或检查网络连接。"


# ---------------------------------------------------------------- 工具 4

_STOPWORDS = {
    "的", "了", "吗", "呢", "啊", "吧", "呀", "哦", "是", "在", "和", "与",
    "或", "及", "等", "都", "也", "很", "就", "要", "会", "能", "我", "你",
    "他", "她", "它", "自己",
}

# 提词时先剥离的通用短语（长句替换为空格）
_GENERIC_PHRASES = [
    "最近有没有", "有没有什么", "有没有", "请问一下", "请问", "什么时候",
    "怎么才能", "怎么样", "怎么", "如何", "为什么", "哪里", "哪儿",
    "最近", "学校", "西农", "农大", "咱们", "我们", "你们", "这个", "那个",
    "一下", "知道", "可以", "需要", "应该", "想", "问", "什么", "哪些",
    "关于", "对于", "还有", "麻烦", "谢谢",
]

_GENERIC_TERMS = {
    "最近", "有没有", "请问", "怎么", "如何", "什么", "哪里", "通知", "公告",
    "活动", "比赛", "学校", "西农", "时间", "那个", "这个", "一下", "需要",
    "可以", "知道", "时候", "方面", "事情", "信息", "问题", "要求", "相关",
}


def _derive_keywords(question: str) -> List[str]:
    """从中文自然语言问题中提取检索词。

    先剥离通用短语，再对剩余文本生成 3–5 字窗口候选；
    内部（非边界对齐）的冗余子词被剔除，按（长度、边界、位置）优选 3 个。
    """
    q = question
    for phrase in sorted(_GENERIC_PHRASES, key=len, reverse=True):
        q = q.replace(phrase, " ")
    q = re.sub(r"[^\u4e00-\u9fff0-9a-zA-Z]+", " ", q)
    tokens = [t for t in q.split() if len(t) >= 2]

    candidates: dict = {}  # cand -> (pos, token_len)
    for t in tokens:
        if len(t) <= 5:
            candidates.setdefault(t, (0, len(t)))
        else:
            for n in (5, 4, 3):
                for i in range(len(t) - n + 1):
                    cand = t[i : i + n]
                    if cand not in candidates:
                        candidates[cand] = (i, len(t))
    filtered = {
        c: pos
        for c, (pos, _token_len) in candidates.items()
        if c not in _GENERIC_TERMS and not c.isdigit()
    }
    # 剔除被其他更长候选"内部包含"的冗余词（边界对齐的子词保留）
    non_redundant = {
        c: pos
        for c, pos in filtered.items()
        if not any(
            len(other) > len(c)
            and c in other
            and not _aligned_subgram(c, pos, other, filtered[other])
            for other in filtered
        )
    }

    def boundary_bonus(cand: str, pos: int) -> int:
        token_len = candidates[cand][1]
        return 1 if pos == 0 or pos + len(cand) == token_len else 0

    ranked = sorted(
        non_redundant.items(),
        key=lambda kv: (-len(kv[0]), -boundary_bonus(kv[0], kv[1]), kv[1], kv[0]),
    )
    return [c for c, _ in ranked[:3]]


def _aligned_subgram(cand: str, cpos: int, other: str, opos: int) -> bool:
    """判断 cand 是否为 other 的边界对齐子词（共享开头或结尾）。"""
    c_end = cpos + len(cand)
    o_end = opos + len(other)
    return cpos == opos or c_end == o_end


def _bigrams(text: str) -> set:
    chars = [c for c in text if c.isalnum() or "\u4e00" <= c <= "\u9fff"]
    return {chars[i] + chars[i + 1] for i in range(len(chars) - 1)}


def _match_channel_items(
    feeds: List[dict],
    query_text: str,
    explicit_keywords: List[str],
    limit: int = 10,
) -> List[dict]:
    scored: List[dict] = []
    keywords = [k for k in explicit_keywords if len(k) >= 2]
    query_bigrams = _bigrams(query_text)
    for item in feeds:
        text = f"{item.get('title') or ''} {item.get('content') or ''}"
        score = 0
        for kw in keywords:
            if kw and kw in text:
                score += 3 + min(len(kw), 8)
        if not keywords:
            overlap = len(_bigrams(text) & query_bigrams)
            score += overlap
        if score > 0:
            item = dict(item)
            item["_score"] = score * 100 + classify.hot_score(item)
            scored.append(item)
    scored.sort(key=lambda x: x["_score"], reverse=True)
    return scored[:limit]


@mcp.tool(description=(
    "对“学校官网 + 校园 QQ 频道”两个信息源做自定义问题检索："
    "先自动从问题中提取关键词，在官网全文索引与频道近期帖子中检索，"
    "合并输出 Markdown 结果，每条均附来源标题与链接。"
))
def campus_question_search(
    question: str,
    keywords: str = "",
    days: int = 90,
    max_results: int = 20,
    include_channel: bool = True,
) -> str:
    """跨站自定义问题检索。

    Args:
        question: 用户的问题，如“最近有没有奖学金评选通知”。
        keywords: 可选，显式指定检索词，用空格或逗号分隔（如“奖学金 评选”）；
                  留空则自动从问题中提取。
        days: 官方渠道只看最近多少天（默认 90）。
        max_results: 官方渠道最多返回条数（默认 20）。
        include_channel: 是否同时检索校园频道近期帖子（默认 True）。

    Returns:
        Markdown 格式的合并检索结果。
    """
    try:
        question = (question or "").strip()
        if not question:
            return "请提供要检索的问题，例如：“最近有没有奖学金评选通知”。"
        explicit = [
            k.strip()
            for k in re.split(r"[,，;；\s]+", keywords or "")
            if k.strip()
        ]
        auto = _derive_keywords(question)
        used_keywords = explicit or auto
        days = max(0, min(days, 365))

        limit = max(1, min(max_results, 50))
        if len(used_keywords) > 1:
            official_items = official_site.search_terms(
                used_keywords, days=days, max_results=limit
            )
        else:
            official_items = official_site.search(
                used_keywords[0] if used_keywords else question,
                days=days,
                max_results=limit,
            )

        channel_items: List[dict] = []
        if include_channel:
            try:
                cookie = config.get_cookie()
                if cookie:
                    client = qq_channel.QQChannelClient(cookie)
                    feeds = client.fetch_feeds(max_pages=4, limit=80)
                    channel_items = _match_channel_items(
                        feeds, question, used_keywords, limit=10
                    )
            except qq_channel.QQChannelError as e:
                LOG.warning("频道检索跳过：%s", e)
            except Exception as e:  # noqa: BLE001
                LOG.warning("频道检索异常：%s", e)

        meta = {
            "fetched_at": format.now_str(),
            "question": question,
            "keywords_display": "，".join(used_keywords[:6]),
            "days": days,
        }
        return format.build_search_report(meta, official_items, channel_items)
    except Exception as e:  # noqa: BLE001
        LOG.exception("campus_question_search 失败")
        return f"⚠️ 综合检索失败：{e}\n\n请稍后重试，或检查网络连接。"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
