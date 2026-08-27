# -*- coding: utf-8 -*-
"""Markdown 报告排版：频道总结、官网查询、综合检索。"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from .classify import CATEGORY_ORDER, hot_score, is_important

CATEGORY_ICONS = {
    "活动": "🎪",
    "竞赛": "🏆",
    "通知": "📌",
    "推荐": "⭐",
    "贴士": "💡",
    "求助": "💬",
    "其他": "📦",
}


def now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def fmt_ts(ts: int) -> str:
    if not ts:
        return ""
    try:
        return datetime.datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
    except (OSError, ValueError):
        return ""


def fmt_ts_full(ts: int) -> str:
    if not ts:
        return ""
    try:
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (OSError, ValueError):
        return ""


def clip(text: str, limit: int = 120) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def link_label(text: str) -> str:
    return (text or "").replace("[", "【").replace("]", "】").replace("\n", " ")


def md_link(text: str, url: str) -> str:
    text = link_label(text)
    if not url:
        return f"**{text}**"
    return f"[{text}]({url})"


def _engagement(item: Dict[str, Any]) -> str:
    parts = []
    likes = int(item.get("like_count") or 0)
    comments = int(item.get("comment_count") or 0)
    if likes:
        parts.append(f"👍{likes}")
    if comments:
        parts.append(f"💬{comments}")
    return " · ".join(parts)


def _item_brief(item: Dict[str, Any], with_date: bool = True) -> str:
    title = item.get("title") or "(无标题)"
    eng = _engagement(item)
    date = ""
    if with_date and item.get("publish_time"):
        date = fmt_ts(int(item["publish_time"]))
    meta = " · ".join(x for x in [eng, date] if x)
    prefix = f"（{meta}）" if meta else ""
    return f"**{title}**{prefix}"


def build_channel_report(
    meta: Dict[str, Any],
    hot: List[Dict[str, Any]],
    groups: Dict[str, List[Dict[str, Any]]],
    important: List[Dict[str, Any]],
) -> str:
    lines: List[str] = []
    lines.append("# 🎓 西农校园频道 · 近期热门总结")
    lines.append("")
    lines.append(
        f"> 数据来源：[西北农林科技大学官方 QQ 频道](https://pd.qq.com/g/{meta.get('guild_id', 'inwafu1934')})"
    )
    lines.append(
        f"> 抓取时间：{meta.get('fetched_at', now_str())}"
        f" ｜ 时间窗口：近 {meta.get('window_hours', 72)} 小时"
        f" ｜ 帖子数：{meta.get('post_count', 0)}"
    )

    if not hot:
        lines.append("")
        lines.append("近期暂无新帖（或时间窗口内无帖子），可稍后再试或调大 `window_hours`。")
        return "\n".join(lines)

    lines.append("")
    lines.append("## 🔥 热度榜")
    for i, item in enumerate(hot, 1):
        brief = _item_brief(item)
        snippet = clip(item.get("content") or "", 90)
        lines.append(f"{i}. {brief}")
        if snippet and snippet != (item.get("title") or ""):
            lines.append(f"   {snippet}")
        lines.append(f"   来源：{md_link(item.get('title') or '原帖', item.get('source_url') or '')}")

    ordered = [c for c in CATEGORY_ORDER if c in groups] + [
        c for c in groups if c not in CATEGORY_ORDER
    ]
    for cat in ordered:
        items = groups[cat]
        icon = CATEGORY_ICONS.get(cat, "📦")
        lines.append("")
        lines.append(f"## {icon} {cat}（{len(items)}）")
        for item in items:
            brief = _item_brief(item)
            snippet = clip(item.get("content") or "", 100)
            lines.append(f"- {brief}")
            if snippet and snippet != (item.get("title") or ""):
                lines.append(f"  {snippet}")
            lines.append(f"  来源：{md_link(item.get('title') or '原帖', item.get('source_url') or '')}")

    if important:
        lines.append("")
        lines.append("## ⚠️ 重点信息（建议优先查看）")
        for item in important:
            author = item.get("author") or ""
            date = fmt_ts_full(int(item["publish_time"])) if item.get("publish_time") else ""
            meta_txt = " · ".join(x for x in [author, date] if x)
            lines.append(
                f"- {md_link(item.get('title') or '原帖', item.get('source_url') or '')}"
                f"（{meta_txt}）"
            )
            snippet = clip(item.get("content") or "", 100)
            if snippet and snippet != (item.get("title") or ""):
                lines.append(f"  {snippet}")

    lines.append("")
    lines.append(
        "> 说明：以上内容来自校园频道公开帖子，重要信息请点击来源帖核对原文；"
        "热门程度按点赞与评论量估算。"
    )
    return "\n".join(lines)


def build_official_report(
    meta: Dict[str, Any],
    items: List[Dict[str, Any]],
) -> str:
    lines: List[str] = []
    lines.append("# 📢 西北农林科技大学官网 · 近期信息查询")
    lines.append("")
    cond = (
        f"分类：{meta.get('category', '全部')}"
        f" ｜ 关键词：{meta.get('keyword') or '无'}"
        f" ｜ 时间范围：近 {meta.get('days', 90)} 天"
    )
    lines.append(
        f"> 查询条件：{cond} ｜ 抓取时间：{meta.get('fetched_at', now_str())}"
        f" ｜ 结果数：{len(items)}"
    )

    if not items:
        lines.append("")
        lines.append("未检索到符合条件的近期信息。可尝试：")
        lines.append("- 放宽时间范围（增大 `days`）；")
        lines.append("- 去掉或更换关键词（如直接搜“通知”“活动”）；")
        lines.append("- 更换分类（通知 / 活动 / 竞赛 / 招聘 / 全部）。")
        return "\n".join(lines)

    # 按分类展示（搜索结果中每项带 category）
    by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for it in items:
        cat = it.get("category") or meta.get("category") or "全部"
        by_cat.setdefault(cat, []).append(it)

    for cat, cat_items in by_cat.items():
        lines.append("")
        lines.append(f"## {CATEGORY_ICONS.get(cat, '📄')} {cat}（{len(cat_items)}）")
        for i, it in enumerate(cat_items, 1):
            title = link_label(it.get("title") or "(无标题)")
            date = it.get("date") or ""
            source = it.get("source") or "学校官网"
            lines.append(f"{i}. **{title}**（{date} · {source}）")
            if it.get("snippet"):
                lines.append(f"   {clip(it['snippet'], 140)}")
            if it.get("url"):
                lines.append(f"   [查看原文]({it['url']})")

    urgent = [
        it
        for it in items
        if any(kw in f"{it.get('title') or ''} {it.get('snippet') or ''}" for kw in ("截止", "报名", "即日", "紧急", "开始"))
    ]
    if urgent:
        lines.append("")
        lines.append("## ⏰ 时效性提示")
        for it in urgent[:8]:
            lines.append(
                f"- {md_link(it.get('title') or '(无标题)', it.get('url') or '')}"
                f"（{it.get('date') or ''}）"
            )

    lines.append("")
    lines.append("> 说明：信息来自西北农林科技大学官网及新闻网全文检索，请以官方原文为准。")
    return "\n".join(lines)


def build_search_report(
    meta: Dict[str, Any],
    official_items: List[Dict[str, Any]],
    channel_items: List[Dict[str, Any]],
) -> str:
    lines: List[str] = []
    lines.append("# 🔍 西农校园信息 · 自定义检索")
    lines.append("")
    lines.append(
        f"> 问题：{meta.get('question') or ''}"
        f" ｜ 检索词：{meta.get('keywords_display') or '（自动提取）'}"
        f" ｜ 抓取时间：{meta.get('fetched_at', now_str())}"
    )
    lines.append(
        f"> 结果：官方渠道 {len(official_items)} 条 ｜ 校园频道 {len(channel_items)} 条"
    )

    if not official_items and not channel_items:
        lines.append("")
        lines.append("未找到相关内容。可尝试：")
        lines.append("- 更换更简洁的关键词（如“奖学金”“选课”“校车”）；")
        lines.append("- 扩大时间范围（`days` 默认 90 天）；")
        lines.append("- 在 `keywords` 参数中显式给出 1–3 个关键词。")
        return "\n".join(lines)

    if official_items:
        lines.append("")
        lines.append(f"## 🏛️ 官方渠道（官网/新闻网 · {len(official_items)} 条）")
        for i, it in enumerate(official_items[:15], 1):
            title = link_label(it.get("title") or "(无标题)")
            date = it.get("date") or ""
            source = it.get("source") or "学校官网"
            lines.append(f"{i}. **{title}**（{date} · {source}）")
            if it.get("snippet"):
                lines.append(f"   {clip(it['snippet'], 130)}")
            if it.get("url"):
                lines.append(f"   [查看原文]({it['url']})")

    if channel_items:
        lines.append("")
        lines.append(f"## 💬 校园频道（QQ · {len(channel_items)} 条）")
        for i, item in enumerate(channel_items[:15], 1):
            brief = _item_brief(item)
            lines.append(f"{i}. {brief}")
            snippet = clip(item.get("content") or "", 100)
            if snippet and snippet != (item.get("title") or ""):
                lines.append(f"   {snippet}")
            lines.append(f"   来源：{md_link(item.get('title') or '原帖', item.get('source_url') or '')}")

    lines.append("")
    lines.append(
        "> 提示：以上为关键词检索命中的原文条目。官方渠道信息权威性更高，"
        "重要事项请打开原文核对时间、地点与报名方式。"
    )
    return "\n".join(lines)
