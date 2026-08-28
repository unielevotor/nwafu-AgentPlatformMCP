# -*- coding: utf-8 -*-
"""本地导出 QQ 频道浏览器会话 Cookie。

腾讯频道网关要求浏览器级会话 Cookie（p_uin + uuid + EO-Bot-Js-Token）。
本脚本用 Playwright 驱动本机 Edge/Chrome 打开频道页建立会话，再把关键
Cookie 导出为 JSON，供 MCP server（PDQQ_COOKIES / NWAFU_COOKIE_FILE）使用。

用法：
    nwafu-export-cookies --out cookies.json
    nwafu-export-cookies --guild-id inwafu1934 --channel-id 670126629 --out cookies.json

依赖：pip install "mcp-for-nwafactivity[cookies]" 或 pip install playwright
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from . import config

# 网关用于识别身份的 cookie 名
IDENTITY_COOKIES = ("p_uin", "uuid", "EO-Bot-Js-Token")


def _cookie_str_to_file(cookie_str: str, path: str) -> None:
    data = {
        "cookie_header": cookie_str,
        "exported_at": int(time.time()),
        "guild_id": config.get_guild_id(),
        "channel_id": config.get_channel_id(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def export(
    guild_id: str,
    channel_id: str,
    out: str,
    headed: bool = False,
    timeout_ms: int = 90_000,
) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise SystemExit(
            "未安装 playwright，请先执行：pip install \"mcp-for-nwafactivity[cookies]\""
            " 或 pip install playwright"
        ) from e

    url = f"https://pd.qq.com/g/{guild_id}/channel/{channel_id}"
    with sync_playwright() as pw:
        browser = None
        for channel in ("msedge", "chrome", None):
            try:
                browser = pw.chromium.launch(
                    channel=channel,
                    headless=not headed,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                )
                break
            except Exception:  # noqa: BLE001
                continue
        if browser is None:
            raise SystemExit(
                "无法启动浏览器（Edge/Chrome 均失败）。请安装 Edge/Chrome，"
                "或执行 `python -m playwright install chromium` 后重试。"
            )
        try:
            context = browser.new_context(
                locale="zh-CN",
                viewport={"width": 1440, "height": 900},
            )
            context.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = window.chrome || {runtime: {}};
                """
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=20_000)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(3)

            def collect() -> list:
                found = {}
                for c in context.cookies():
                    if c["name"] in IDENTITY_COOKIES and c.get("value"):
                        found[c["name"]] = c["value"]
                return [f"{name}={found[name]}" for name in IDENTITY_COOKIES if name in found]

            # EO-Bot-Js-Token 由页面 JS 在加载过程中下发，可能稍晚出现；
            # 最多等待 45 秒，尽量把三个关键 Cookie 等齐。
            parts = collect()
            deadline = time.time() + 45
            while len(parts) < len(IDENTITY_COOKIES) and time.time() < deadline:
                time.sleep(3)
                parts = collect()

            cookie_str = "; ".join(parts)
            if not cookie_str:
                raise SystemExit(
                    "未获取到关键 Cookie（p_uin/uuid/EO-Bot-Js-Token）。"
                    "可能被风控拦截，可加 --headed 手动完成验证后重试。"
                )
            if len(parts) < len(IDENTITY_COOKIES):
                missing = [n for n in IDENTITY_COOKIES if n not in cookie_str]
                print(
                    f"警告：以下 Cookie 未获取到（{'，'.join(missing)}）。"
                    "热评接口可能不可用；可加 --headed 手动完成验证后重试。"
                )
            _cookie_str_to_file(cookie_str, out)
            return cookie_str
        finally:
            browser.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="导出 QQ 频道 Cookie")
    parser.add_argument("--guild-id", default=config.get_guild_id())
    parser.add_argument("--channel-id", default=config.get_channel_id())
    parser.add_argument("--out", default="cookies.json", help="输出 JSON 路径")
    parser.add_argument("--headed", action="store_true", help="有头模式（调试用）")
    args = parser.parse_args(argv)
    export(args.guild_id, args.channel_id, args.out, headed=args.headed)
    print(f"已导出 Cookie -> {args.out}")
    print("请把该文件中的 cookie_header 写入环境变量 PDQQ_COOKIES，")
    print("或在 MCP server 环境设置 NWAFU_COOKIE_FILE 指向该文件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
