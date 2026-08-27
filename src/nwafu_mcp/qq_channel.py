# -*- coding: utf-8 -*-
"""腾讯频道（QQ 频道）公开帖子数据层。

接口规律（此前抓包验证）：
  POST https://pd.qq.com/qunng/guild/gotrpc/noauth/trpc.qchannel.commreader.ComReader/<Method>
  x-oidb: {"uint32_service_type": 11 时间线 | 5 评论}
  Cookie: 浏览器会话 cookie（p_uin + uuid + EO-Bot-Js-Token）

匿名可读公开内容，但网关要求浏览器级会话 Cookie；纯 requests 模式需要
先用 `nwafu-export-cookies` 在本地导出。
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional

import requests

from . import config

LOG = logging.getLogger(__name__)

API_BASE_NOAUTH = "https://pd.qq.com/qunng/guild/gotrpc/noauth"
CLIENT_APP_ID = "537246381"

OIDB_SERVICE_TYPE = {
    "GetChannelTimelineFeeds": 11,
    "GetFeedComments": 5,
}

USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Edge/126.0.0.0 Safari/537.36"
    ),
]


def _pick_ua() -> str:
    return random.choice(USER_AGENTS)


def _text_of_rich(rich: Any) -> str:
    """提取 richContents / contents 结构的纯文本。"""
    if not isinstance(rich, dict):
        return ""
    parts: List[str] = []
    for c in rich.get("contents") or []:
        if not isinstance(c, dict):
            continue
        tc = c.get("text_content")
        if isinstance(tc, dict) and tc.get("text"):
            parts.append(str(tc["text"]))
        elif isinstance(tc, str) and tc:
            parts.append(tc)
    return "".join(parts)


def _text_of_content_with_style(cws: Any) -> str:
    """提取 content_with_style（富文本段落）的纯文本。"""
    if not isinstance(cws, dict):
        return ""
    parts: List[str] = []
    for para in cws.get("paragraphs") or []:
        if not isinstance(para, dict):
            continue
        for elem in para.get("elems") or []:
            if not isinstance(elem, dict):
                continue
            t = elem.get("text") or {}
            tc = t.get("text_content")
            if isinstance(tc, dict) and tc.get("text"):
                parts.append(str(tc["text"]))
    return "".join(parts)


def _extract_feed(feed: Dict[str, Any], guild: str, channel_id: str) -> Dict[str, Any]:
    feed_id = str(feed.get("id") or "")
    title = _text_of_rich(feed.get("title"))
    content = _text_of_content_with_style(feed.get("content_with_style"))
    if not content:
        content = _text_of_rich(feed.get("contents"))
    if not content and title:
        content = title

    poster = feed.get("poster") or {}
    author = str(poster.get("nick") or "未知用户")
    try:
        publish_time = int(feed.get("createTime") or 0)
    except (TypeError, ValueError):
        publish_time = 0

    total_prefer = feed.get("total_prefer") or {}
    try:
        like_count = int(
            total_prefer.get("prefer_count")
            or total_prefer.get("prefer_count_without_like")
            or (feed.get("total_like") or {}).get("like_count")
            or 0
        )
    except (TypeError, ValueError):
        like_count = 0

    try:
        comment_count = int(feed.get("commentCount") or 0)
    except (TypeError, ValueError):
        comment_count = 0
    if not comment_count and feed.get("discussion_num"):
        try:
            comment_count = int(feed.get("discussion_num"))
        except (TypeError, ValueError):
            pass

    subc = f"?subc={channel_id}" if channel_id else ""
    return {
        "title": title,
        "content": content,
        "author": author,
        "publish_time": publish_time,
        "source_url": f"https://pd.qq.com/g/{guild}/post/{feed_id}{subc}",
        "comment_count": comment_count,
        "like_count": like_count,
        "_feed_id": feed_id,
    }


def _extract_hot_comments(payload: Dict[str, Any], top_n: int = 3) -> List[Dict[str, Any]]:
    data = payload.get("data") or {}
    parsed: List[Dict[str, Any]] = []
    for c in data.get("vecComment") or []:
        like_info = c.get("likeInfo") or {}
        post_user = c.get("postUser") or {}
        try:
            create_time = int(c.get("createTime") or 0)
        except (TypeError, ValueError):
            create_time = 0
        try:
            like_count = int(like_info.get("count") or 0)
        except (TypeError, ValueError):
            like_count = 0
        parsed.append(
            {
                "author": str(post_user.get("nick") or "匿名用户"),
                "content": _text_of_rich(c.get("richContents"))
                or str(c.get("content") or ""),
                "like_count": like_count,
                "create_time": create_time,
            }
        )
    parsed.sort(key=lambda x: (x["like_count"], x["create_time"]), reverse=True)
    return parsed[:top_n]


class QQChannelError(RuntimeError):
    pass


class QQChannelClient:
    """轻量客户端：拉取频道时间线帖子与热评。"""

    def __init__(
        self,
        cookie: str,
        guild_id: str = "",
        channel_id: str = "",
        timeout: Optional[int] = None,
        min_delay: Optional[float] = None,
        max_delay: Optional[float] = None,
    ) -> None:
        self.cookie = cookie.strip()
        self.guild = (guild_id or config.get_guild_id()).strip()
        self.channel_id = (channel_id or config.get_channel_id()).strip()
        self.timeout = timeout or config.get_timeout()
        self.min_delay = min_delay if min_delay is not None else config.get_min_delay()
        self.max_delay = max_delay if max_delay is not None else config.get_max_delay()
        if not self.cookie:
            raise QQChannelError(config.cookie_missing_message())
        if not self.guild or not self.channel_id:
            raise QQChannelError("缺少 guild_id / channel_id")
        self.user_agent = _pick_ua()
        self.is_numeric_guild = bool(re.fullmatch(r"\d+", self.guild))

    # ---- 请求 ----
    def _guild_field(self) -> Dict[str, str]:
        return {"guild_id": self.guild} if self.is_numeric_guild else {"guild_number": self.guild}

    def _headers(self, method: str, referer: str) -> Dict[str, str]:
        sec_ch_ua = (
            '"Not=A?Brand";v="99", "Microsoft Edge";v="126", "Chromium";v="126"'
            if "Edg/" in self.user_agent
            else '"Not=A?Brand";v="99", "Chromium";v="126", "Google Chrome";v="126"'
        )
        return {
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/json",
            "Cookie": self.cookie,
            "Origin": "https://pd.qq.com",
            "Referer": referer,
            "User-Agent": self.user_agent,
            "X-QQ-Client-AppId": CLIENT_APP_ID,
            "x-oidb": json.dumps(
                {"uint32_service_type": OIDB_SERVICE_TYPE[method]},
                ensure_ascii=False,
            ),
            "sec-ch-ua": sec_ch_ua,
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }

    def _post(self, method: str, body: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{API_BASE_NOAUTH}/trpc.qchannel.commreader.ComReader/{method}"
        referer = f"https://pd.qq.com/g/{self.guild}/channel/{self.channel_id}"
        headers = self._headers(method, referer)
        last_payload: Optional[Dict[str, Any]] = None
        for attempt in range(1, 4):
            try:
                resp = requests.post(
                    url,
                    headers=headers,
                    data=json.dumps(body, ensure_ascii=False),
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                payload = resp.json()
                last_payload = payload
                if payload.get("retcode") == 0:
                    return payload
                raise QQChannelError(
                    f"{method} retcode={payload.get('retcode')} "
                    f"msg={payload.get('message') or payload.get('tipMsg') or ''}"
                )
            except QQChannelError:
                if attempt < 3:
                    time.sleep(2 * 2 ** (attempt - 1) + random.uniform(0, 1.5))
                continue
            except Exception as e:  # noqa: BLE001
                LOG.warning("%s 第 %d 次请求异常: %s", method, attempt, e)
                if attempt < 3:
                    time.sleep(2 * 2 ** (attempt - 1) + random.uniform(0, 1.5))
                continue
        if last_payload:
            raise QQChannelError(
                f"{method} 重试 3 次仍失败 retcode={last_payload.get('retcode')} "
                f"msg={last_payload.get('message') or last_payload.get('tipMsg') or ''}"
            )
        raise QQChannelError(f"{method} 请求失败（网络异常或超时）")

    def _throttle(self) -> None:
        delay = random.uniform(self.min_delay, self.max_delay)
        if delay > 0:
            time.sleep(delay)

    # ---- 业务 ----
    def _timeline_body(self, attch_info: str) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "count": 20,
            "from": 7,
            "feedAttchInfo": attch_info,
            "sortOption": 1,  # 按发布时间
            "need_top_info": False,
        }
        if self.is_numeric_guild:
            body["channelSign"] = {
                "guild_id": self.guild,
                "channel_id": self.channel_id,
            }
        else:
            body["guild_number"] = self.guild
            body["channelSign"] = {"channel_id": self.channel_id}
        return body

    def fetch_feeds(
        self,
        max_pages: int = 4,
        limit: int = 0,
        since_timestamp: Optional[int] = None,
        fetch_comments: bool = False,
        comment_top_n: int = 3,
    ) -> List[Dict[str, Any]]:
        """分页拉取子版块时间线；可选为每帖附加热评。"""
        items: List[Dict[str, Any]] = []
        seen = set()
        attch_info = ""
        stopped = False
        max_pages = max(1, min(max_pages, 10))

        for _page in range(1, max_pages + 1):
            payload = self._post("GetChannelTimelineFeeds", self._timeline_body(attch_info))
            data = payload.get("data") or {}
            feeds = data.get("vecFeed") or []
            if not feeds:
                break

            hit_old = False
            for feed in feeds:
                feed_id = str(feed.get("id") or "")
                if not feed_id or feed_id in seen:
                    continue
                # 只保留目标子版块的帖子
                sign = (feed.get("channelInfo") or {}).get("sign") or {}
                if sign.get("channel_id") and str(sign["channel_id"]) != self.channel_id:
                    continue
                try:
                    publish_time = int(feed.get("createTime") or 0)
                except (TypeError, ValueError):
                    publish_time = 0
                if since_timestamp and publish_time <= since_timestamp:
                    hit_old = True
                    continue
                seen.add(feed_id)
                item = _extract_feed(feed, self.guild, self.channel_id)
                if fetch_comments:
                    try:
                        item["hot_comments"] = self.fetch_hot_comments(feed_id, comment_top_n)
                    except Exception as e:  # noqa: BLE001
                        LOG.warning("帖子 %s 热评获取失败: %s", feed_id, e)
                        item["hot_comments"] = []
                items.append(item)
                if limit and len(items) >= limit:
                    stopped = True
                    break

            if hit_old and not stopped:
                break
            if stopped:
                break
            attch_info = data.get("feedAttchInfo") or ""
            if data.get("isFinish") or not attch_info:
                break
            self._throttle()
        return items

    def fetch_hot_comments(self, feed_id: str, top_n: int = 3) -> List[Dict[str, Any]]:
        body = {
            "feedId": feed_id,
            "listNum": 20,
            "from": 1,
            "src": 0,
            "attchInfo": "",
            "needInsertCommentID": "",
            "needInsertReplyID": "",
            "channelSign": self._guild_field(),
            "extInfo": {
                "mapInfo": [
                    {"key": "qc-tabid", "value": ""},
                    {"key": "qc-pageid", "value": ""},
                ]
            },
            "rankingType": 1,
            "replyListNum": 1,
        }
        payload = self._post("GetFeedComments", body)
        return _extract_hot_comments(payload, top_n=top_n)


def fetch_recent_feeds(
    cookie: str,
    max_pages: int = 4,
    limit: int = 0,
    since_timestamp: Optional[int] = None,
    fetch_comments: bool = False,
    comment_top_n: int = 3,
) -> List[Dict[str, Any]]:
    """便捷入口：抓取最近帖子列表。"""
    client = QQChannelClient(cookie)
    return client.fetch_feeds(
        max_pages=max_pages,
        limit=limit,
        since_timestamp=since_timestamp,
        fetch_comments=fetch_comments,
        comment_top_n=comment_top_n,
    )
