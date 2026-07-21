# Gleaner

多源学术文献采集 MCP（stdio）。把「检索 → 下载全文 → 归一化元数据」交给 Claude Code 等 Agent 一键完成。

| 来源 | 工具 | 说明 | 产物 |
|------|------|------|------|
| **中国知网 CNKI** | `cnki_collect` / `cnki_list` | 关键词或专业检索式；全文需机构权限 | PDF / CAJ |
| **Elsevier / ScienceDirect** | `els_collect` | 官方 API + 期刊白名单 | Markdown（+ XML） |
| **国际文献** | `intl_collect` | OpenAlex 发现 → OA / NBER / Sci-Hub / 可选 CARSI | PDF |

输出目录：`corpus/<批次>/metadata.csv` + `papers/`。

---

## 快速开始

### 1. 安装

```bash
git clone https://github.com/liuqiaodongdong/gleaner-mcp.git
cd gleaner-mcp

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
# 若不用系统 Edge 跑知网，再执行：
# playwright install chromium
```

需要 **Python 3.11+**。知网线建议 Windows + 系统 Edge。

### 2. 准备账号（按需）

| 用途 | 是否需要 | 申请 |
|------|----------|------|
| 知网全文 | 机构网络/代理 + [超级鹰](https://www.chaojiying.com/)（验证码 9602） | 代理可用校园网/VPN；超级鹰需积分 |
| Elsevier | **官方** API Key（免费学术额度） | 见下方；完整版 [docs/ELSEVIER_API.md](docs/ELSEVIER_API.md) |
| 国际 OA 线 | 通常不需要 | — |

首次使用可先调 MCP 工具 **`setup_status`**，它会检查缺什么并给出配置步骤。

#### Elsevier 官方 API Key（`els_collect` 必需）

本项目**只使用** [Elsevier Developer Portal](https://dev.elsevier.com/) 官方 API，**不要**使用第三方 Key、破解或网页爬取代替。

1. 用**学校/机构邮箱**注册/登录：https://account.elsevier.com/  
2. 打开 https://dev.elsevier.com/ → [Create / Manage API Key](https://dev.elsevier.com/apikey/manage)  
3. **Create API Key**（Label 如 `gleaner-local`；Website 本地可用 `http://localhost`）  
4. 将 Key 写入 MCP 的 `ELSEVIER_API_KEY`，或单行写入 `acq/data/.elsevier_key`  
5. 调 `setup_status` 确认 `elsevier.ready`

说明：Key 负责 API 鉴权与配额；**订阅全文**仍依赖你的机构权益。配额见 [api_key_settings](https://dev.elsevier.com/api_key_settings.html)。逐步图与 Agent 话术见 **[docs/ELSEVIER_API.md](docs/ELSEVIER_API.md)**。

### 3. 接入 Claude Code（或其他 MCP 客户端）

编辑 MCP 配置（Claude Code 常见路径：`~/.claude.json`），加入：

```json
{
  "mcpServers": {
    "gleaner": {
      "type": "stdio",
      "command": "C:/Path/To/python.exe",
      "args": ["C:/Path/To/gleaner-mcp/acq_mcp.py"],
      "env": {
        "ELSEVIER_API_KEY": "your_key",
        "CJY_USER": "chaojiying_user",
        "CJY_PASS": "chaojiying_pass",
        "CJY_SOFTID": "your_softid",
        "ACQ_PROXY": "http://127.0.0.1:PORT"
      }
    }
  }
}
```

- 将 `command` / `args` 改成你的本机绝对路径  
- **`ACQ_PROXY` 按你本机代理软件填写**（Clash / V2 等端口各不相同，常见如 `7890`、`7897`、`10808`……以你客户端「HTTP 代理」端口为准）。也可不写，程序会尝试读取 **Windows 系统代理**  
- 若电脑已在校园网 / 机构 VPN 内、浏览器能直接下知网，通常**不必**再设 `ACQ_PROXY`  
- 密钥放在 `env` 里即可；Elsevier 也可写成文件 `acq/data/.elsevier_key`（单行）  
- 模板见 [`.mcp.json.example`](.mcp.json.example)、[`.env.example`](.env.example)  
- 重启客户端后，`/mcp` 应能看到 `gleaner`

### 4. （可选）知网登录缓存

减少验证码频率：

```bash
set ACQ_BROWSER_CHANNEL=msedge
python login.py
```

---

## MCP 工具

| 工具 | 作用 |
|------|------|
| `setup_status` | 检查配置是否齐全，返回待办步骤（**建议先调**） |
| `cnki_collect` | 知网检索并下载全文 |
| `cnki_list` | 知网仅题录（不下 PDF） |
| `els_collect` | Elsevier 白名单刊检索 + 全文转 MD |
| `intl_collect` | 国际论文发现与下载 |
| `chaojiying_score` | 查询超级鹰积分 |
| `list_sources` | 各源状态与配额摘要 |

Agent 约定见 [`AGENTS.md`](AGENTS.md)：未配置完成时会引导你补齐，而不是盲目采集。

### 调用示例

```text
setup_status()

cnki_collect(query="数字经济", num=10, out_name="demo_cnki")
cnki_collect(query="SU %= '供应链' AND YR >= 2024", num=20, pro=True)
cnki_list(query="数字经济", num=100)

els_collect(
  query='("digital economy" OR digitalization) AND innovation',
  num=10, tier="1+2", year_from="2020"
)

intl_collect(query="minimum wage employment", num=15, year_from="2018")
```

---

## 工作原理（简）

```
MCP 客户端
  └── acq_mcp.py (gleaner)
        ├── CNKI  → Playwright + 代理 + 超级鹰
        ├── Elsevier → REST API + API Key
        └── 国际 → OpenAlex / OA / Sci-Hub / CARSI
              └── corpus/<批次>/
```

- 知网：无头浏览器（默认 Edge），验证码走超级鹰 9602  
- Elsevier：Search API + Article Retrieval，全文 XML 转结构化 Markdown  
- 国际/Elsevier 的 HTTP 请求默认绕过系统代理（`trust_env=False`），避免部分代理导致的 SSL 错误；知网取机构权限时则使用 `ACQ_PROXY` 或系统代理  

---

## 命令行（调试用）

```bash
python main.py 供应链 30
python run_batch.py params.json
python run_els_batch.py els_params.json
python run_intl_batch.py intl_params.json
```

参数字段见各脚本文件头注释。

---

## 项目结构

```
acq_mcp.py           # MCP 入口
acq/                 # 采集核心与各源 adapter
  setup_check.py     # setup_status 实现
  sources/           # cnki 相关外：oa / scihub / els / openalex …
run_*.py             # 各线批量入口
browser.py / captcha.py / login.py …
tests/
AGENTS.md            # 给 Agent 的使用约定
```

---

## 故障排查

| 现象 | 处理 |
|------|------|
| `setup_incomplete` / 缺密钥 | 调 `setup_status`，按返回步骤配置 |
| Elsevier Key 缺失 | **只**按 [docs/ELSEVIER_API.md](docs/ELSEVIER_API.md) 在 dev.elsevier.com 申请 |
| 知网无权限 / 打不开 | 检查是否在机构网/VPN，或 `ACQ_PROXY` 端口是否与本机代理软件一致 |
| 超级鹰相关报错 | 检查 `CJY_USER` / `CJY_PASS` / `CJY_SOFTID` 与积分 |
| MCP 里看不到 gleaner | 路径是否正确、是否重启客户端 |
| Elsevier 0 篇 | 检索式是否过窄；机构是否订阅该刊全文（Key  alone 不等于全库 PDF） |

---

## 许可证与声明

- 请遵守知网、Elsevier 等平台服务条款，仅在合法授权（机构订阅等）范围内使用。  
- 验证码打码、第三方镜像等能力由你自行承担合规风险。  
- 本项目按「现状」提供，作者不对滥用或账号封禁负责。

Issues / PR 欢迎。
