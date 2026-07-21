# Gleaner（物尽其用）—— 机构学术资源采集 MCP

把「主题 → 检索 → 下载全文 → 归一化语料」封装成 **stdio MCP**（`gleaner`），在本机运行，可被 Claude Code / 其他 MCP 客户端调用。

三条采集线**全部在本机执行**（无需备用机 SSH）：

| 线 | MCP 工具 | 鉴权 / 网络 | 产物 |
|---|---|---|---|
| **CNKI 中文** | `cnki_collect` / `cnki_list` | 机构代理 + 超级鹰过验证码 | PDF / CAJ |
| **国际 #13** | `intl_collect` | 公网（绕系统代理直连）+ 可选 CARSI cookie | PDF |
| **Elsevier** | `els_collect` | 官方 API + **API key** | MD（+ XML 留底） |

产物统一落在 `corpus/<批次名>/`，跨源合并表为 `corpus/merged_metadata.csv`。

---

## 使用指南（分发安装）

### 0. 你需要准备什么

| 能力 | 是否必需 | 怎么拿 |
|---|---|---|
| Python 3.11+ | 必需 | 本机 Python / conda |
| 机构网络或代理 | CNKI 全文需要 | 校园网 / VPN / 可访问知网机构库的代理 |
| 超级鹰账号 | CNKI 下载验证码需要 | [chaojiying.com](https://www.chaojiying.com/) |
| Elsevier API key | Elsevier 线需要 | [dev.elsevier.com](https://dev.elsevier.com/) → Create API Key（建议学校邮箱） |
| 系统 Edge 或 Chromium | CNKI 浏览器自动化 | Windows 推荐 Edge；或 `playwright install chromium` |

**不会随仓库分发（也切勿上传）的内容：**

- `cookies.json`、`acq/cookies/**`（本机会话）
- `acq/data/.elsevier_key`、`.env`（密钥）
- `corpus/`、`output/`（下载产物）
- 个人路径的 `.mcp.json`

### 1. 获取代码并安装依赖

```bash
cd <你的目录>
# git clone <本仓库>   # 或解压分发包
cd 0128#cnki_scraper   # 以实际目录名为准

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
# CNKI 若不用系统 Edge，再装浏览器内核：
# playwright install chromium
```

### 2. 配置密钥（必做，且只放本机）

任选一种方式（**推荐写在 MCP 的 `env` 里**，不落盘到仓库）。

#### 方式 A：Claude Code / MCP 配置（推荐）

1. 复制模板：

```bash
# Windows 示例：把配置合并进 Claude 的 mcpServers
# 模板见仓库内 .mcp.json.example
```

2. 编辑 Claude 配置（Windows 常见路径：`C:\Users\<你>\.claude.json`），加入：

```json
{
  "mcpServers": {
    "gleaner": {
      "type": "stdio",
      "command": "C:/Path/To/python.exe",
      "args": ["C:/Path/To/0128#cnki_scraper/acq_mcp.py"],
      "env": {
        "ELSEVIER_API_KEY": "你的ElsevierKey",
        "CJY_USER": "超级鹰用户名",
        "CJY_PASS": "超级鹰密码",
        "CJY_SOFTID": "超级鹰softid",
        "ACQ_PROXY": "http://127.0.0.1:10808"
      }
    }
  }
}
```

说明：

- `command` / `args` 必须改成**你机器上的绝对路径**
- `ACQ_PROXY`：CNKI 拿机构权限用的 HTTP 代理；若已开系统代理且与浏览器一致，也可不写（程序会读 Windows 系统代理）
- 字段清单见 [`.env.example`](.env.example)、[`.mcp.json.example`](.mcp.json.example)

#### 方式 B：密钥文件（仅 Elsevier）

```text
acq/data/.elsevier_key   # 单行 API key，无换行杂讯
```

该路径已在 `.gitignore` 中，**不要** `git add`。

#### 方式 C：系统环境变量

```text
ELSEVIER_API_KEY / CJY_USER / CJY_PASS / CJY_SOFTID / ACQ_PROXY
```

### 3. （可选）CNKI 首次登录存 cookie

机构 session 可减少验证码频率：

```bash
set ACQ_BROWSER_CHANNEL=msedge
python login.py
# 浏览器打开后完成访问；cookies 写入 cookies.json（已 gitignore）
```

### 4. 验证 MCP 已连接

1. 重启 Claude Code（或你的 MCP 客户端）
2. `/mcp` 应看到 `gleaner`
3. 可用工具：

| 工具 | 作用 |
|---|---|
| **`setup_status`** | **部署引导（优先）**：检查超级鹰 / Elsevier key / cookies / 代理，返回申请步骤 |
| `cnki_collect` | 知网检索 + 全文下载 |
| `cnki_list` | 知网仅题录（不下 PDF） |
| `intl_collect` | 国际：OpenAlex 发现 → OA / NBER / Sci-Hub / CARSI |
| `els_collect` | Elsevier 白名单刊 + 全文 XML→MD |
| `chaojiying_score` | 查超级鹰积分 |
| `list_sources` | 列各源状态 / 配额 / 就绪摘要 |

### 4.1 Agent 部署引导（自动）

仓库含 [`AGENTS.md`](AGENTS.md)：约定 **agent 首次使用或采集前必须先调 `setup_status`**，把 `next_steps_for_user` 展示给你，协助申请：

- 超级鹰 → https://www.chaojiying.com/
- Elsevier API → https://dev.elsevier.com/
- CNKI cookies → 本机 `python login.py`

未配齐时调用 `cnki_collect` / `els_collect` 会返回 `setup_incomplete`（不会傻跑），agent 应继续引导配置。

人也可以直接让 agent：「先检查 gleaner 部署状态」。

### 5. 典型调用

```text
# 知网关键词
cnki_collect(query="数字经济", num=10, out_name="demo_cnki")

# 知网专业检索式
cnki_collect(query="SU %= '供应链' AND YR >= 2024", num=20, pro=True)

# 仅题录（给学者统计等）
cnki_list(query="数字经济", num=100)

# Elsevier：ScienceDirect qs 布尔式 + 白名单 tier
els_collect(
  query='("digital economy" OR digitalization) AND innovation',
  num=10, tier="1+2", year_from="2020", out_name="demo_els"
)

# 国际 OA / Sci-Hub 等
intl_collect(query="minimum wage employment", num=15, year_from="2018")
```

批次目录：

```text
corpus/<out_name 或自动名>/
  metadata.csv
  papers/          # PDF / MD / XML
```

---

## 架构（本机）

```
Claude Code / MCP 客户端
   │  gleaner (stdio → acq_mcp.py)
   ├── cnki_*  → run_batch.py / run_list.py   # 浏览器 + 代理 + 超级鹰
   ├── intl_*  → run_intl_batch.py            # 直连外网
   └── els_*   → run_els_batch.py             # API key
                 产物 → corpus/<批次>/
```

- **CNKI**：Playwright（默认无头 + 系统 Edge）经代理访问机构库；验证码用超级鹰 type **9602**。
- **Elsevier**：`X-ELS-APIKey`；检索 + Article Retrieval 全文 XML → 结构化 MD；白名单见 `acq/data/intl_journal_tiers.json`。
- **国际 / Elsevier HTTP**：`trust_env=False` 绕 Clash，避免 `SSL: UNEXPECTED_EOF`；CNKI 浏览器则**需要**代理时用 `ACQ_PROXY`。

---

## CLI 调试（不经 MCP）

```bash
# CNKI
python main.py 供应链 30
python run_batch.py path/to/params.json

# Elsevier（params 里 out 用绝对路径更稳）
python run_els_batch.py path/to/els_params.json

# 国际
python run_intl_batch.py path/to/intl_params.json
```

JSON 参数字段见各 `run_*.py` 文件头注释。

---

## 安全与分发清单

上传 / 打包 / 开源前请确认：

| 路径 | 是否应出现在仓库 |
|---|---|
| `cookies.json` | ❌ 否 |
| `acq/cookies/` | ❌ 否 |
| `acq/data/.elsevier_key` | ❌ 否 |
| `.env` / 含真实密钥的 `.mcp.json` | ❌ 否 |
| `corpus/`、`output/` | ❌ 否（体量大且含文献） |
| `config.py` 中的账号默认值 | ❌ 否（已改为仅读环境变量） |
| `.env.example` / `.mcp.json.example` | ✅ 可以（占位符） |
| `acq/data/intl_journal_tiers.json` | ✅ 可以（刊名白名单，非密钥） |

本地自检：

```bash
git status
git check-ignore -v cookies.json acq/data/.elsevier_key .mcp.json
# 应显示被 ignore

git ls-files | findstr /i "cookie elsevier_key .env"
# 应无输出
```

> **说明**：若历史 commit 里曾写入过超级鹰密码等，公开推送前请**改密**，并考虑用 `git filter-repo` 等清理历史。当前工作区已去掉 `config.py` 默认账号。

---

## 代码结构

```
acq/                     # 多源采集核心
  sources/               # openalex / oa / scihub / nber / carsi / els*
  els_config.py          # API key 读取
  data/intl_journal_tiers.json
acq_mcp.py               # MCP 入口（gleaner）
acq/setup_check.py       # 部署就绪检查（setup_status）
AGENTS.md                # Agent 行为约定（首次 setup_status）
run_batch.py / run_list.py / run_els_batch.py / run_intl_batch.py
browser.py scraper.py downloader.py captcha.py login.py config.py
tests/
.mcp.json.example
.env.example
```

---

## 依赖

见 [`requirements.txt`](requirements.txt)：`playwright`、`requests`、`mcp`、`lxml`、`pandas`、`ddddocr`、`pytest` 等。

---

## 故障排查（简）

| 现象 | 可能原因 |
|---|---|
| `Elsevier API key 缺失` | 未设 `ELSEVIER_API_KEY` 且无 `.elsevier_key` |
| `超级鹰账号未配置` | 未设 `CJY_*` |
| CNKI 打不开 / 无机构权限 | 代理未通；设 `ACQ_PROXY` 或系统代理 |
| 国际线 `SSL: UNEXPECTED_EOF` | 请求误走 Clash；应保持 `trust_env=False`（代码已处理） |
| MCP 工具列表没有 gleaner | `command`/`args` 路径错误，或未重启客户端 |
| `els_collect` 0 篇 | 检索式过窄 / tier 无刊 / key 无订阅权限 |

---

## 设计历史

`docs/superpowers/` 为早期 spec/plan，其中「备用机 SSH」等拓扑**已过时**，以本文与 `acq_mcp.py` 为准。
