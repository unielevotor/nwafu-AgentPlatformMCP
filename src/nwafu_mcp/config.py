# -*- coding: utf-8 -*-
"""运行配置：环境变量读取与默认值。"""

from __future__ import annotations

import json
import os

# 学校官网（含新闻网）全文检索接口（通元 CMS）
SEARCH_URL = "https://www.nwsuaf.edu.cn/cms/web/search/index.jsp"
MAIN_SITE_ID = "32e6d9be927446ac812eab9feb030bf4"  # 西北农林科技大学主站（覆盖全校）
NEWS_SITE_ID = "3"  # 新闻网

# QQ 频道默认参数（西北农林科技大学官方频道 · 帖子广场）
GUILD_ID = "inwafu1934"
CHANNEL_ID = "670126629"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    raw = _env(name, "")
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    raw = _env(name, "")
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def get_guild_id() -> str:
    return _env("PDQQ_GUILD_ID", GUILD_ID)


def get_channel_id() -> str:
    return _env("PDQQ_CHANNEL_ID", CHANNEL_ID)


def get_timeout() -> int:
    return env_int("NWAFU_TIMEOUT", 30)


def get_min_delay() -> float:
    return env_float("PDQQ_MIN_DELAY", 0.3)


def get_max_delay() -> float:
    return env_float("PDQQ_MAX_DELAY", 0.8)


def get_cookie() -> str:
    """读取 QQ 频道 Cookie：优先 PDQQ_COOKIES，其次 NWAFU_COOKIE_FILE。"""
    cookie = _env("PDQQ_COOKIES")
    if cookie:
        return cookie
    path = _env("NWAFU_COOKIE_FILE")
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("cookie_header"):
                return str(data["cookie_header"]).strip()
        except (OSError, ValueError):
            pass
    return ""


def cookie_missing_message() -> str:
    return (
        "未配置 QQ 频道 Cookie，无法访问校园频道数据。\n\n"
        "请按以下方式配置后重试：\n"
        "1. 本地执行 `nwafu-export-cookies --out cookies.json` 导出浏览器会话；\n"
        "2. 将 cookies.json 中 cookie_header 的值写入环境变量 PDQQ_COOKIES，"
        "或设置 NWAFU_COOKIE_FILE 指向该文件；\n"
        "3. 重新启动 MCP server。\n\n"
        "说明：频道公开内容可匿名浏览，但网关要求浏览器级会话 Cookie"
        "（p_uin / uuid / EO-Bot-Js-Token），Cookie 会过期，建议定期刷新。"
    )
