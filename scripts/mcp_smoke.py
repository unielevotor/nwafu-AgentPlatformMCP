# -*- coding: utf-8 -*-
"""端到端 MCP 协议冒烟测试。

启动 nwafu-mcp stdio server，用官方 mcp 客户端 SDK 连接，列出工具并逐个调用。
需要网络与频道 Cookie（NWAFU_COOKIE_FILE 或 PDQQ_COOKIES 环境变量）。

用法：
    $env:NWAFU_COOKIE_FILE = "cookies.json"
    python scripts/mcp_smoke.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "nwafu_mcp"],
        cwd=str(ROOT),
        env=env,
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"== MCP 工具列表（{len(tools.tools)} 个）==")
            for t in tools.tools:
                print(f"  - {t.name}: {t.description.splitlines()[0][:80]}")

            calls = [
                (
                    "campus_channel_summary",
                    {"window_hours": 168, "max_posts": 40, "top_n": 5},
                ),
                (
                    "official_site_recent",
                    {"category": "通知", "keyword": "植保学院", "days": 90, "max_results": 8},
                ),
                (
                    "official_site_search",
                    {"query": "奖学金", "days": 180, "max_results": 8},
                ),
                (
                    "campus_question_search",
                    {"question": "最近有没有奖学金评选通知", "days": 180, "max_results": 8},
                ),
            ]
            for name, args in calls:
                print(f"\n===== 调用 {name}{args} =====")
                result = await session.call_tool(name, args)
                for content in result.content:
                    if hasattr(content, "text") and content.text:
                        lines = content.text.splitlines()
                        print("\n".join(lines[:45]))
                        if len(lines) > 45:
                            print(f"...（共 {len(lines)} 行，已截断）")


if __name__ == "__main__":
    asyncio.run(main())
