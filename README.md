# nwafu-mcp · 西北农林科技大学校园信息 MCP 工具集

为部署在任意智能体平台上的 Agent 提供一套符合 [MCP 协议](https://modelcontextprotocol.io)
的工具，覆盖三个核心能力：

1. **校园频道热门总结**：抓取西北农林科技大学官方 QQ 频道
   （[pd.qq.com/g/inwafu1934](https://pd.qq.com/g/inwafu1934)）近期热门帖子，
   按互动量排序并自动归类为「活动 / 竞赛 / 通知 / 推荐 / 贴士 / 求助」等类别，
   每条重要信息均附来源帖子标题与链接，保证可溯源。
2. **官网快速查询**：通过学校官网（[www.nwafu.edu.cn](https://www.nwafu.edu.cn/)）
   与新闻网的全文索引，快速查询最近的活动、竞赛、通知、招聘信息；
   支持传入「植保学院」「教务处」等关键词缩小检索范围。
3. **跨站自定义检索**：把用户问题自动拆成检索词，同时在官网全文索引与
   校园频道近期帖子中检索并合并输出，所有结果排版为易读的 Markdown，
   并附带原文链接。

---

## 功能特性

- **MCP 标准实现**：基于官方 `mcp` Python SDK（FastMCP），stdio 传输，
  可直接接入 Claude Desktop、Cursor、Windsurf 以及各类支持 MCP 的智能体平台。
- **信息可溯源**：所有结论性条目都带来源标题 + 原文链接，重要信息单独
  「重点提示 / 时效性提示」区块。
- **分类智能**：规则引擎自动把频道帖子归类到「推荐 / 贴士 / 活动 / 竞赛 /
  通知 / 求助」等类别，组内按热度（点赞 + 评论加权）排序。
- **关键词精检索**：官网查询支持任意关键词缩小范围（如学院名、部门名、事项名）。
- **健壮容错**：请求超时、重试、限速随机延迟、Cookie 过期提示，单工具失败
  不影响其他工具。
- **隐私合规**：只抓取公开可见内容，不绕过登录/权限校验；Cookie 通过环境变量
  注入，不写入代码仓库。

---

## 工具列表

| 工具 | 用途 | 关键参数 |
| --- | --- | --- |
| `campus_channel_summary` | 校园 QQ 频道近期热门帖子智能总结（热度榜 + 分类 + 重点信息） | `window_hours` 时间窗口、`max_posts` 抓取量、`top_n` 热度榜条数、`include_comments` 是否抓热评 |
| `official_site_recent` | 官网最近通知/活动/竞赛/招聘快速查询与总结 | `category` 分类、`keyword` 缩小范围（如学院名）、`days` 时间范围、`max_results` |
| `official_site_search` | 官网全文检索（自定义关键词） | `query` 核心词、`keyword` 附加限定词、`days`、`max_results` |
| `campus_question_search` | 跨「官网 + 校园频道」自定义问题检索 | `question` 问题原文、`keywords` 可选显式检索词、`days`、`include_channel` |

所有工具输出均为 Markdown 文本，结构包含：数据来源、抓取时间、查询条件、
结果列表（标题 / 日期 / 来源 / 摘要 / 链接）与重点提示。

---

## 工作原理

### 校园 QQ 频道

腾讯频道 Web 端为纯前端渲染，公开数据来自 protobuf-over-JSON 网关：

```text
POST https://pd.qq.com/qunng/guild/gotrpc/noauth/trpc.qchannel.commreader.ComReader/<Method>
x-oidb: {"uint32_service_type": 11 时间线 | 5 评论}
```

匿名可读公开内容，但网关要求浏览器级会话 Cookie
（`p_uin` + `uuid` + `EO-Bot-Js-Token`）。本工具：

- 默认拉取「帖子广场」子版块（`670126629`）最近 N 条帖子（按发布时间）；
- 用 `点赞数 + 2 × 评论数` 估算热度，取窗口内最热帖子；
- 规则引擎自动分类，重要信息（通知/公告/报名/截止/考试等）单独提示；
- 可选为热度榜帖子抓取热评（`GetFeedComments`）。

> 说明：`GetGuildFeeds` 的「热门排序」接口经实测返回空数据，故热度榜采用
> 「近期帖子 × 互动量」方案，更符合「近期热门」语义。

### 学校官网

学校主站与新闻网使用通元 CMS 全文检索：

```text
GET https://www.nwsuaf.edu.cn/cms/web/search/index.jsp
    ?query=<关键词>&siteID=<站点ID>&searchScope=0&channelID=&matchType=0
    &sortField=publishDate&order=1&date=<3|6|12>&page=<页码>
```

- `siteID=32e6d9be...` 为主站索引（覆盖全校各学院/部门）；
- 按分类生成检索词（通知/公告、活动/讲座/论坛、竞赛/大赛、招聘等），
  合并用户关键词后分页拉取，解析标题、日期、来源、摘要与原文链接；
- 时间范围默认近 90 天（映射到索引的 3/6/12 个月过滤）。

---

## 快速开始（本地运行）

```powershell
cd nwafu-mcp
uv sync --extra dev
```

### 1. 配置频道 Cookie（可选，仅频道类工具需要）

```powershell
uv run nwafu-export-cookies --out cookies.json
```

脚本会用本机 Edge/Chrome 打开频道页建立会话并导出 Cookie。然后把
`cookies.json` 中的 `cookie_header` 写入环境变量：

```powershell
$env:PDQQ_COOKIES = "p_uin=xxx; uuid=xxx; EO-Bot-Js-Token=xxx"
# 或
$env:NWAFU_COOKIE_FILE = "F:\path\to\cookies.json"
```

> Cookie 会过期（反爬 token 与浏览器实例绑定），云端部署建议定期刷新。

### 2. 直接测试工具函数（不经过 MCP 客户端）

```powershell
uv run python -c "
import os
os.environ['NWAFU_COOKIE_FILE'] = 'cookies.json'
from nwafu_mcp.server import official_site_recent
print(official_site_recent(category='通知', keyword='植保学院'))
"
```

### 3. 以 MCP Server 方式运行

```powershell
uv run nwafu-mcp
```

---

## 接入 MCP 客户端

### Claude Desktop（`claude_desktop_config.json`）

```json
{
  "mcpServers": {
    "nwafu-campus": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/unielevotor/nwafu-AgentPlatformMCP",
        "nwafu-mcp"
      ],
      "env": {
        "PDQQ_COOKIES": "p_uin=xxx; uuid=xxx; EO-Bot-Js-Token=xxx"
      }
    }
  }
}
```

### Cursor / Windsurf / 通用平台（JSON 形式）

```json
{
  "mcpServers": {
    "nwafu-campus": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/unielevotor/nwafu-AgentPlatformMCP", "nwafu-mcp"],
      "env": {
        "PDQQ_COOKIES": "p_uin=xxx; uuid=xxx; EO-Bot-Js-Token=xxx",
        "PDQQ_GUILD_ID": "inwafu1934",
        "PDQQ_CHANNEL_ID": "670126629"
      }
    }
  }
}
```

也可用 `pip install git+https://github.com/unielevotor/nwafu-AgentPlatformMCP` 安装后，
以 `nwafu-mcp` 命令直接启动。

### 托管模式（远程 HTTP URL，供云端智能体平台使用）

如果你的智能体平台支持**远程 MCP 服务器**（通过 URL 连接），不需要 `command`，改为：

```json
{
  "mcpServers": {
    "nwafu-campus": {
      "url": "https://your-host.example.com/mcp",
      "headers": {
        "Authorization": "Bearer <你的 NWAFU_MCP_AUTH_TOKEN>"
      }
    }
  }
}
```

如何把服务器跑起来并暴露到公网，见下面的「托管部署」章节。

---

## 托管部署（远程 HTTP）

项目默认是 stdio 本地模式；要托管，用 `streamable-http` 传输把 MCP server
跑成常驻 HTTP 服务，再让智能体平台通过 URL 连接。

### 1. 本地直接启动（调试）

```powershell
$env:NWAFU_MCP_AUTH_TOKEN = "换成随机长令牌"
uv run nwafu-mcp --transport streamable-http --host 0.0.0.0 --port 8000 --mount-path /mcp
```

也可以全用环境变量（适合容器/平台注入）：

```powershell
$env:NWAFU_MCP_TRANSPORT = "streamable-http"
$env:NWAFU_MCP_HOST = "0.0.0.0"
$env:NWAFU_MCP_PORT = "8000"
$env:NWAFU_MCP_MOUNT_PATH = "/mcp"
$env:NWAFU_MCP_AUTH_TOKEN = "换成随机长令牌"
uv run nwafu-mcp
```

启动后：

- 健康检查：`GET /healthz` → `{"status":"ok", ...}`
- MCP 端点：`POST /mcp`（协议为 [Streamable HTTP](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)）

### 2. Docker 部署

```bash
docker build -t nwafu-mcp .
docker run -d --name nwafu-mcp -p 8000:8000 \
  -e NWAFU_MCP_AUTH_TOKEN="换成随机长令牌" \
  -e PDQQ_COOKIES="p_uin=xxx; uuid=xxx; EO-Bot-Js-Token=xxx" \
  nwafu-mcp
```

镜像内默认以 `streamable-http` 模式监听 `0.0.0.0:8000`。

### 3. 部署到云平台

把代码推到 GitHub 后，任意支持容器的平台（Railway、Render、Fly.io、阿里云
容器服务等）都可以直接构建；Serverless 场景建议加 `--stateless`（或环境变量
`NWAFU_MCP_STATELESS=true`）。

### 4. 托管注意事项

- **必须开鉴权**：`NWAFU_MCP_AUTH_TOKEN` 设置后，所有 MCP 请求需带
  `Authorization: Bearer <token>`，否则返回 401；令牌请用
  `python -c "import secrets; print(secrets.token_urlsafe(32))"` 生成。
- **必须走 HTTPS**：公网部署请在前面挂 Nginx/Caddy 或平台自带的 TLS，
  避免令牌明文传输。
- **频道工具需要 Cookie**：`PDQQ_COOKIES` 在服务器上配好后会过期，
  需要定期刷新（见「快速开始」）。
- **出口网络**：服务器需能访问 `pd.qq.com` 与 `nwafu.edu.cn`。
- 健康检查 `/healthz` 不要求鉴权，方便负载均衡探测。

---

## GitHub 部署步骤

1. 推送到 GitHub 仓库（`unielevotor/nwafu-AgentPlatformMCP`）：

```bash
git remote add origin https://github.com/unielevotor/nwafu-AgentPlatformMCP.git
git push -u origin main
```

2. 确认仓库为 **Public**（私有仓库时，目标智能体平台需能访问 GitHub 凭据）。
3. 在智能体平台的 MCP 配置中填入上面的 `uvx --from git+...` 启动命令，
   并注入 `PDQQ_COOKIES` 等环境变量。

---

## 环境变量

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `PDQQ_COOKIES` | 频道工具需要 | QQ 频道浏览器会话 Cookie |
| `NWAFU_COOKIE_FILE` | 频道工具需要 | 指向 `nwafu-export-cookies` 导出的 JSON |
| `PDQQ_GUILD_ID` | 否 | 频道标识，默认 `inwafu1934` |
| `PDQQ_CHANNEL_ID` | 否 | 子版块 ID，默认 `670126629`（帖子广场） |
| `PDQQ_MIN_DELAY` / `PDQQ_MAX_DELAY` | 否 | 频道请求间隔（秒），默认 0.3–0.8 |
| `NWAFU_TIMEOUT` | 否 | 单请求超时（秒），默认 30 |
| `NWAFU_MCP_TRANSPORT` | 否 | `stdio`（本地）或 `streamable-http`（托管），默认 `stdio` |
| `NWAFU_MCP_HOST` / `NWAFU_MCP_PORT` | 否 | HTTP 监听地址/端口，默认 `0.0.0.0:8000` |
| `NWAFU_MCP_MOUNT_PATH` | 否 | MCP 端点路径，默认 `/mcp` |
| `NWAFU_MCP_AUTH_TOKEN` | 托管建议 | Bearer 鉴权令牌；留空则不鉴权 |
| `NWAFU_MCP_STATELESS` | 否 | Serverless 场景开启无状态模式 |

参考 [.env.example](.env.example)。

---

## 输出示例（节选）

```markdown
# 🎓 西农校园频道 · 近期热门总结

> 数据来源：西北农林科技大学官方 QQ 频道 ｜ 时间窗口：近 72 小时 ｜ 帖子数：48

## 🔥 热度榜
1. **中元节鬼是真的多啊…**（👍7 · 💬1 · 08-27）
   来源：[中元节鬼是真的多啊](https://pd.qq.com/g/inwafu1934/post/...)

## 🏆 竞赛（2）
- **关于举办2026年创新创业大赛的通知**（👍5 · 💬2 · 08-26）
  来源：[…](https://pd.qq.com/g/inwafu1934/post/...)

## ⚠️ 重点信息（建议优先查看）
- [关于选课时间安排的通知](https://pd.qq.com/g/inwafu1934/post/...)
```

```markdown
# 📢 西北农林科技大学官网 · 近期信息查询

> 查询条件：分类=通知 ｜ 关键词=植保学院 ｜ 时间范围：近 90 天 ｜ 结果数：12

1. **关于举办2026年植保论坛系列学术报告会（十七）的通知**（2026-08-26 · 植物保护学院）
   [查看原文](https://ppc.nwafu.edu.cn/xzbg/...)
```

---

## 合规与使用建议

- 只抓取**公开可见**内容，不绕过登录、付费或权限校验。
- 已内置随机 UA、随机延迟与失败重试，部署时请勿调小延迟做高频抓取，
  遵守目标平台服务条款与《个人信息保护法》等适用法规。
- 重要信息（报名截止、考试安排等）请以官方原文为准，工具输出仅供速览。
- 频道 Cookie 含会话标识，切勿提交到公开仓库，务必通过环境变量注入。

---

## 常见问题

| 现象 | 处理 |
| --- | --- |
| 频道工具提示「未配置 Cookie」 | 本地执行 `nwafu-export-cookies --out cookies.json` 后配置环境变量 |
| 频道工具报 `retcode=150/4000` | Cookie 失效或缺失反爬 token，重新导出 |
| 官网查询结果为空 | 放宽 `days`、去掉关键词或更换分类后重试 |
| 云端无 Edge/Chrome | 安装 `playwright` 并 `python -m playwright install chromium`，或定期在本地导出 Cookie 后注入 |

## 目录结构

```text
src/nwafu_mcp/
  server.py          MCP 服务器与四个工具定义
  qq_channel.py      QQ 频道数据层（时间线/热评）
  official_site.py   官网全文检索数据层
  classify.py        帖子分类与热度评分
  format.py          Markdown 报告排版
  config.py          环境变量与默认配置
  export_cookies.py  本地导出频道 Cookie 的 CLI
tests/               单元测试
scripts/mcp_smoke.py 端到端 MCP 冒烟测试（连接 stdio server 并调用全部工具）
Dockerfile           托管模式容器镜像
```
