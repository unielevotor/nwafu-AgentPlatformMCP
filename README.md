# mcp-for-nwafactivity · 西北农林科技大学校园信息 MCP 工具集

一套符合 [MCP 协议](https://modelcontextprotocol.io) 的智能体工具集，为部署在
任意智能体平台上的 Agent 提供西农校园信息能力：

1. **校园频道热门总结**：总结西北农林科技大学官方 QQ 频道
   （[pd.qq.com/g/inwafu1934](https://pd.qq.com/g/inwafu1934)）近期热门帖子，
   自动归类为「活动 / 竞赛 / 通知 / 推荐 / 贴士 / 求助」等，重要信息附来源标题与链接。
2. **官网快速查询**：查询学校官网（[www.nwafu.edu.cn](https://www.nwafu.edu.cn/)）
   最近的通知、活动、竞赛、招聘，支持输入「植保学院」「教务处」等关键词缩小范围。
3. **跨站自定义检索**：自动拆解问题关键词，在官网全文索引与校园频道近期帖子中
   检索并合并输出，排版为易读的 Markdown。

## 工具列表

| 工具 | 用途 | 关键参数 |
| --- | --- | --- |
| `campus_channel_summary` | 校园频道近期热门帖子总结（热度榜 + 分类 + 来源引用） | `window_hours`、`max_posts`、`top_n`、`include_comments` |
| `official_site_recent` | 官网最近通知/活动/竞赛/招聘查询与总结 | `category`、`keyword`（如学院名）、`days`、`max_results` |
| `official_site_search` | 官网全文检索 | `query`、`keyword`、`days`、`max_results` |
| `campus_question_search` | 跨「官网 + 校园频道」自定义问题检索 | `question`、`keywords`、`days`、`include_channel` |

## 快速开始（本地）

```powershell
cd nwafu-mcp
uv sync --extra dev --extra cookies
uv run mcp-for-nwafactivity
```

频道类工具需要 QQ 频道会话 Cookie（`p_uin` / `uuid` / `EO-Bot-Js-Token`），
首次使用请先导出并配置：

```powershell
uv run nwafu-export-cookies --out cookies.json
$env:NWAFU_COOKIE_FILE = "F:\path\to\cookies.json"
# 或把 cookies.json 中的 cookie_header 填入环境变量 PDQQ_COOKIES
```

不想手动维护 Cookie？见下文「Cookie 自动化」。

## 部署到魔搭社区（可托管部署）

项目已发布到 PyPI。魔搭 STDIO 托管只支持 `npx` / `uvx`，且只能拉取已发布包，
因此服务配置如下：

```json
{
  "mcpServers": {
    "nwafu-campus": {
      "command": "uvx",
      "args": ["mcp-for-nwafactivity"],
      "env": {
        "PDQQ_COOKIES": "p_uin=xxx; uuid=xxx; EO-Bot-Js-Token=xxx",
        "PDQQ_GUILD_ID": "inwafu1934",
        "PDQQ_CHANNEL_ID": "670126629"
      }
    }
  }
}
```

创建步骤：

1. 打开 [创建 MCP 服务](https://modelscope.cn/mcp/servers/create)，保持
   「从 GitHub 仓库快速创建」。
2. GitHub 地址填 `https://github.com/unielevotor/nwafu-AgentPlatformMCP`，
   英文名称填 `nwafu-campus`，托管类型选「可托管部署」。
3. 平台自动解析本 README 的服务配置并执行部署检测
   （`uvx` 安装包 → 连接 → `list_tools`），通过后即可在工具页测试使用。

同一份配置也可直接用于 Claude Desktop / Cursor 等本地客户端。
`PDQQ_COOKIES` 过期后重新导出并在连接时更新；官网类工具无需 Cookie。

如需以远程 HTTP 方式部署（Docker / Serverless），用
`mcp-for-nwafactivity --transport streamable-http` 启动，详见代码内
`--help` 与仓库 Dockerfile。

## Cookie 自动化（无需手动填 PDQQ_COOKIES）

QQ 频道会话 Cookie 会过期，手动复制容易忘。项目提供两个自动化手段：

1. **本地 Cookie 守护程序 `nwafu-cookie-keeper`**：周期性用浏览器自动刷新
   Cookie 并写入 `cookies.json`，可附带启动 HTTP 端点供 MCP 拉取：

   ```powershell
   uv run nwafu-cookie-keeper --serve 127.0.0.1:8765 --token 换成随机长令牌 --out cookies.json
   ```

2. **MCP server 自动拉取**：在 MCP 环境里配置 `PDQQ_COOKIE_URL` 指向上面端点的
   `/cookie`，server 会按 TTL 自动拉取并缓存，无需手工填写：

   ```env
   PDQQ_COOKIE_URL=http://127.0.0.1:8765/cookie
   PDQQ_COOKIE_TOKEN=换成随机长令牌
   PDQQ_COOKIE_REFRESH_TTL=600
   ```

本地 / 局域网部署时 keeper 与 MCP 同机即可；若 MCP 部署在魔搭云端，需要把
keeper 端点通过内网穿透（如 Cloudflare Tunnel）暴露为公网 HTTPS 地址。

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `PDQQ_COOKIES` | QQ 频道会话 Cookie（频道类工具需要） |
| `NWAFU_COOKIE_FILE` | 指向 `nwafu-export-cookies` 导出的 JSON |
| `PDQQ_COOKIE_URL` / `PDQQ_COOKIE_TOKEN` | 远程 Cookie 提供者地址与 Bearer 令牌（自动化） |
| `PDQQ_COOKIE_REFRESH_TTL` | 远程 Cookie 缓存秒数，默认 600 |
| `PDQQ_GUILD_ID` / `PDQQ_CHANNEL_ID` | 频道与子版块标识，默认 `inwafu1934` / `670126629` |
| `NWAFU_TIMEOUT` | 单请求超时秒数，默认 30 |
| `NWAFU_MCP_TRANSPORT` | `stdio`（默认）或 `streamable-http` |

参考 [.env.example](.env.example)。

## 合规说明

仅抓取公开可见内容，不绕过登录 / 权限校验；内置随机 UA、限速与重试，请勿调低
延迟做高频抓取。重要信息请以官方原文为准。
