# -*- coding: utf-8 -*-
"""本地 QQ 频道 Cookie 守护程序。

周期性用 Playwright 打开频道页刷新会话 Cookie（p_uin / uuid / EO-Bot-Js-Token），
写入本地 cookies.json，并可选择启动一个 HTTP 端点，供 MCP server 通过
PDQQ_COOKIE_URL 自动拉取——这样无需手动复制 PDQQ_COOKIES。

用法：
    nwafu-cookie-keeper --interval 600 --out cookies.json
    nwafu-cookie-keeper --serve 127.0.0.1:8765 --token 换成随机长令牌 --out cookies.json
"""

from __future__ import annotations

import argparse
import hmac
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config
from .export_cookies import export

LOG = logging.getLogger(__name__)


class CookieKeeper:
    """持有最新 Cookie 并周期性刷新。"""

    def __init__(self, guild_id: str, channel_id: str, out: str, token: str = "") -> None:
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.out = out
        self.token = token
        self.state: dict = {"cookie_header": "", "updated_at": 0}

    def refresh(self) -> bool:
        try:
            cookie = export(
                guild_id=self.guild_id,
                channel_id=self.channel_id,
                out=self.out,
                headed=False,
            )
            self.state["cookie_header"] = cookie
            self.state["updated_at"] = int(time.time())
            LOG.info("Cookie 刷新成功（%s）", self.out)
            return True
        except SystemExit as e:
            LOG.warning("Cookie 刷新失败: %s", e)
        except Exception as e:  # noqa: BLE001
            LOG.warning("Cookie 刷新异常: %s", e)
        return False


class CookieHandler(BaseHTTPRequestHandler):
    """GET /cookie → {"cookie_header": "...", "updated_at": ...}（可选 Bearer 鉴权）。"""

    keeper: CookieKeeper = None  # type: ignore[assignment]

    def _authorized(self) -> bool:
        if not self.keeper.token:
            return True
        auth = self.headers.get("Authorization", "")
        expected = f"Bearer {self.keeper.token}"
        return hmac.compare_digest(auth.encode("utf-8"), expected.encode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/cookie":
            self.send_error(404)
            return
        if not self._authorized():
            body = json.dumps({"error": "unauthorized"}, ensure_ascii=False).encode("utf-8")
            self.send_response(401)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        state = self.keeper.state
        body = json.dumps(
            {
                "cookie_header": state.get("cookie_header", ""),
                "updated_at": state.get("updated_at", 0),
                "ok": bool(state.get("cookie_header")),
            },
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        LOG.info("%s - %s", self.address_string(), fmt % args)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="nwafu-cookie-keeper",
        description="本地 QQ 频道 Cookie 守护程序：自动刷新并可选暴露 HTTP 端点",
    )
    parser.add_argument("--interval", type=int, default=600, help="刷新间隔秒数（默认 600）")
    parser.add_argument("--out", default="cookies.json", help="Cookie 输出 JSON 路径")
    parser.add_argument("--guild-id", default=config.get_guild_id())
    parser.add_argument("--channel-id", default=config.get_channel_id())
    parser.add_argument(
        "--serve",
        default="",
        help="可选：启动 HTTP 端点，如 127.0.0.1:8765（供 PDQQ_COOKIE_URL 拉取）",
    )
    parser.add_argument("--token", default="", help="HTTP 端点 Bearer 令牌（建议设置）")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    keeper = CookieKeeper(args.guild_id, args.channel_id, args.out, args.token)
    keeper.refresh()

    if args.serve:
        host, _, port = args.serve.rpartition(":")
        try:
            server = ThreadingHTTPServer((host, int(port)), CookieHandler)
        except OSError as e:
            LOG.error("无法监听 %s: %s", args.serve, e)
            return 1
        CookieHandler.keeper = keeper
        threading.Thread(target=server.serve_forever, daemon=True).start()
        LOG.info(
            "Cookie HTTP 端点已启动：http://%s:%s/cookie（鉴权：%s）",
            host,
            port,
            "已开启" if args.token else "未开启（仅建议本机/内网）",
        )

    LOG.info("Cookie 守护运行中，每 %d 秒刷新一次；按 Ctrl+C 退出", args.interval)
    try:
        while True:
            time.sleep(max(60, args.interval))
            keeper.refresh()
    except KeyboardInterrupt:
        LOG.info("已退出")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
