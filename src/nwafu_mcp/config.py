# -*- coding: utf-8 -*-
"""运行配置：环境变量读取与默认值。"""

from __future__ import annotations

import json
import logging
import os
import time

import requests

LOG = logging.getLogger(__name__)

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
    """读取 QQ 频道 Cookie：PDQQ_COOKIES → NWAFU_COOKIE_FILE → PDQQ_COOKIE_URL。"""
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
    url = get_cookie_url()
    if url:
        return fetch_remote_cookie(
            url,
            token=get_cookie_token(),
            ttl=get_cookie_refresh_ttl(),
        )
    return ""


def get_cookie_url() -> str:
    """远程 Cookie 提供者地址（如本机 nwafu-cookie-keeper 的 /cookie 端点）。"""
    return _env("PDQQ_COOKIE_URL")


def get_cookie_token() -> str:
    """访问远程 Cookie 提供者的 Bearer 令牌（可选）。"""
    return _env("PDQQ_COOKIE_TOKEN")


def get_cookie_refresh_ttl() -> int:
    """远程 Cookie 缓存有效期（秒），默认 600（10 分钟）。"""
    return env_int("PDQQ_COOKIE_REFRESH_TTL", 600)


# 远程 Cookie 内存缓存：{url: {"value": str, "fetched_at": float}}
_REMOTE_COOKIE_CACHE: dict = {}


def fetch_remote_cookie(url: str, token: str = "", ttl: int = 600) -> str:
    """从远程地址获取 cookie_header；带 TTL 缓存，失败时回退到旧缓存。"""
    now = time.time()
    cached = _REMOTE_COOKIE_CACHE.get(url)
    if cached and cached.get("value") and now - cached.get("fetched_at", 0) < ttl:
        return cached["value"]

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.get(url, headers=headers, timeout=get_timeout())
        resp.raise_for_status()
        text = resp.text.strip()
        value = ""
        try:
            data = resp.json()
            if isinstance(data, dict):
                value = str(data.get("cookie_header") or data.get("cookie") or "").strip()
        except ValueError:
            pass
        if not value:
            value = text
        if value:
            _REMOTE_COOKIE_CACHE[url] = {"value": value, "fetched_at": now}
            return value
    except Exception as e:  # noqa: BLE001
        LOG.warning("远程 Cookie 获取失败 %s: %s", url, e)
    if cached and cached.get("value"):
        return cached["value"]  # 刷新失败时用旧值兜底
    return ""


def cookie_missing_message() -> str:
    return (
        "未配置 QQ 频道 Cookie，无法访问校园频道数据。\n\n"
        "请按以下方式配置后重试：\n"
        "1. 本地执行 `nwafu-export-cookies --out cookies.json` 导出浏览器会话；\n"
        "2. 将 cookies.json 中 cookie_header 的值写入环境变量 PDQQ_COOKIES，"
        "或设置 NWAFU_COOKIE_FILE 指向该文件；\n"
        "3. 或运行 `nwafu-cookie-keeper --serve 127.0.0.1:8765` 自动刷新，"
        "并把 PDQQ_COOKIE_URL 指向其 /cookie 端点；\n"
        "4. 重新启动 MCP server。\n\n"
        "说明：频道公开内容可匿名浏览，但网关要求浏览器级会话 Cookie"
        "（p_uin / uuid / EO-Bot-Js-Token），Cookie 会过期，建议定期刷新。"
    )
