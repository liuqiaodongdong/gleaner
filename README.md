# Gleaner

多源学术文献采集（**Skill + CLI**）。把「检索 → 下载全文 → 归一化元数据」交给 Agent / 本机命令一键完成。

> **已弃用 MCP**：`acq_mcp.py` 仅 legacy 对照，硬超时 `timeout=1800` 为已知缺陷，**勿用于生产**。请用 `gleaner_cli.py` 与 `~/.grok/skills/gleaner/`。

**Authors:** [liuqiaodongdong](https://github.com/liuqiaodongdong) and [Grok](https://x.ai)  
仓库：https://github.com/liuqiaodongdong/gleaner

| 来源 | CLI | 说明 | 产物 |
|------|------|------|------|
| **中国知网 CNKI** | `prepare` → `cnki-list` / `cnki` | 关键词 / 专业式 / **期刊分级 L1–L4**（`cnki_journal_tiers.json`） | PDF / CAJ / 题录 |
| **Elsevier / ScienceDirect** | `els` | 官方 API + 期刊白名单 | Markdown（+ XML） |
| **国际文献** | `intl` | OpenAlex 发现 → OA / NBER / Sci-Hub / 可选 CARSI | PDF |

输出目录：`corpus/<批次>/metadata.csv` + `papers/`。

---

## 快速开始

### 1. 安装

```bash
git clone https://github.com/liuqiaodongdong/gleaner.git
cd gleaner

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

首次使用请先跑：

```bash
python gleaner_cli.py status
```

它会检查缺什么并给出配置步骤。

#### Elsevier 官方 API Key（`els` 必需）

本项目**只使用** [Elsevier Developer Portal](https://dev.elsevier.com/) 官方 API，**不要**使用第三方 Key、破解或网页爬取代替。

1. 用**学校/机构邮箱**注册/登录：https://account.elsevier.com/  
2. 打开 https://dev.elsevier.com/ → [Create / Manage API Key](https://dev.elsevier.com/apikey/manage)  
3. **Create API Key**（Label 如 `gleaner-local`；Website 本地可用 `http://localhost`）  
4. 将 Key 写入 `.env` 的 `ELSEVIER_API_KEY`，或单行写入 `acq/data/.elsevier_key`  
5. 再跑 `python gleaner_cli.py status` 确认 `elsevier.ready`

说明：Key 负责 API 鉴权与配额；**订阅全文**仍依赖你的机构权益。配额见 [api_key_settings](https://dev.elsevier.com/api_key_settings.html)。逐步图与 Agent 话术见 **[docs/ELSEVIER_API.md](docs/ELSEVIER_API.md)**。

### 3. 配置环境（`.env` / Skill）

复制 [`.env.example`](.env.example) 为 `.env`，填写：

```env
ELSEVIER_API_KEY=your_key
CJY_USER=chaojiying_user
CJY_PASS=chaojiying_pass
CJY_SOFTID=your_softid
ACQ_PROXY=http://127.0.0.1:PORT
```

- **`ACQ_PROXY` 按本机机构/校园网代理填写**（端口以客户端显示为准）。也可不写，程序会尝试读取 **Windows 系统代理**  
- 若电脑已在校园网 / 机构 VPN 内、浏览器能直接下知网，通常**不必**再设 `ACQ_PROXY`  
- 推荐设置 `GLEANER_ROOT` 指向本仓库根  
- 历史 MCP 模板 [`.mcp.json.example`](.mcp.json.example) **仅作 env 键名参考**（DEPRECATED）  
- Grok 用户 Skill：把仓库内 `skill/gleaner/` 复制到 `~/.grok/skills/gleaner/`（包装脚本会解析 ROOT 并调用 CLI）

### 4. （可选）知网登录缓存

机构会话写在 `cookies.json`（已 gitignore）。**批次间必须热启动**：加载现有 cookie，不要裸开浏览器。仅第一次没有 cookie 才允许冷启动。滑块用超级鹰 9602；过验证后才写入。无需个人知网账号。

```bash
set ACQ_BROWSER_CHANNEL=msedge
# 已有 cookies.json（续批次，推荐）
python login.py
# 仅首次没有 cookie：
set ACQ_ALLOW_COLD_LOGIN=1
python login.py
# 完整步骤
python gleaner_cli.py login-hint
```

---

## CLI 命令

| 命令 | 作用 |
|------|------|
| `status` | 检查配置是否齐全，返回待办步骤（**建议先跑**） |
| `prepare` | Agent 提供概念组 → 生成 L1–L4 专业检索式（`LY` 刊滤，不启浏览器） |
| `cnki` | 知网全文；支持 `--level L1..L4` + `--search-md` 分级采集 |
| `cnki-list` | 知网仅题录；同样支持分级 |
| `els` | Elsevier 白名单刊检索 + 全文转 MD |
| `intl` | 国际论文发现与下载 |
| `score` | 查询超级鹰积分 |
| `sources` | 各源状态与配额摘要 |
| `login-hint` | 知网登录 / cookie 提示 |

Agent 约定见 [`AGENTS.md`](AGENTS.md)：未配置完成时会引导你补齐，而不是盲目采集。

**CNKI 分级**：同义发散由 Agent 完成；`prepare` 只做确定性拼式。刊表：`acq/data/cnki_journal_tiers.json`（tier1/2/3）。

### 调用示例

```bash
python gleaner_cli.py status

# 1) Agent 拓展概念组后建式（不启浏览器）
python gleaner_cli.py prepare \
  --topic "数字经济" \
  --concept-groups '[{"name":"数字经济","keywords":["数字经济","数字化","数据要素"]}]' \
  --year-from 2015

# 2) 先题录看 TOTAL，再全文
python gleaner_cli.py cnki-list --level L1 --search-md "<prepare 返回的 search_md>" --num 100
python gleaner_cli.py cnki --level L1 --search-md "<search_md>" --num 30

# 兼容：无分级
python gleaner_cli.py cnki --query "数字经济" --num 10 --out-name demo_cnki

python gleaner_cli.py els \
  --query '("digital economy" OR digitalization) AND innovation' \
  --num 10 --tier 1+2 --year-from 2020

python gleaner_cli.py intl --query "minimum wage employment" --num 15 --year-from 2018
```

也可用 Skill 包装（先安装，见下方）：

```powershell
pwsh "$env:USERPROFILE\.grok\skills\gleaner\scripts\gleaner.ps1" status
```

### 安装用户 Skill

```powershell
$dest = "$env:USERPROFILE\.grok\skills\gleaner"
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.grok\skills" | Out-Null
Copy-Item -Recurse -Force skill\gleaner $dest
$env:GLEANER_ROOT = (Resolve-Path .).Path
```

复制到用户目录后必须设置 `GLEANER_ROOT`。也可用 `GLEANER_PYTHON` 指定解释器。

---

## 工作原理（简）

```
Agent / 终端
  └── gleaner_cli.py
        ├── CNKI  → Playwright + 代理 + 超级鹰
        ├── Elsevier → REST API + API Key
        └── 国际 → OpenAlex / OA / Sci-Hub / CARSI
              └── corpus/<批次>/
```

- 知网：无头浏览器（默认 Edge），验证码走超级鹰 9602  
- Elsevier：Search API + Article Retrieval，全文 XML 转结构化 Markdown  
- 国际/Elsevier 的 HTTP 请求默认绕过系统代理（`trust_env=False`），避免部分代理导致的 SSL 错误；知网取机构权限时则使用 `ACQ_PROXY` 或系统代理  
- 长任务由 CLI 子进程执行，**默认无 MCP 式 30 分钟硬杀**；日志见 `corpus/*_run.log`

---

## 底层脚本（调试用）

```bash
python run_batch.py params.json
python run_els_batch.py els_params.json
python run_intl_batch.py intl_params.json
```

参数字段见各脚本文件头注释。统一入口仍推荐 `gleaner_cli.py`。

---

## 项目结构

```
gleaner_cli.py       # 统一 CLI（推荐）
skill/gleaner/       # 用户 Skill（复制到 ~/.grok/skills/gleaner/）
acq_mcp.py           # LEGACY MCP 入口（勿生产）
acq/                 # 采集核心与各源 adapter
  cli_support.py     # ROOT / env / 子进程 / 摘要
  setup_check.py     # status 实现
  sources/           # cnki 相关外：oa / scihub / els / openalex …
run_*.py             # 各线批量入口
browser.py / captcha.py / login.py …
tests/
AGENTS.md            # 给 Agent 的使用约定（Skill+CLI）
```

---

## 故障排查

| 现象 | 处理 |
|------|------|
| `setup_incomplete` / 缺密钥 | 跑 `status`，按返回步骤配置 `.env` |
| Elsevier Key 缺失 | **只**按 [docs/ELSEVIER_API.md](docs/ELSEVIER_API.md) 在 dev.elsevier.com 申请 |
| 知网无权限 / 打不开 | 检查是否在机构网/VPN，或 `ACQ_PROXY` 端口是否与本机代理软件一致 |
| 超级鹰相关报错 | 检查 `CJY_USER` / `CJY_PASS` / `CJY_SOFTID` 与积分（`score`） |
| cookie / 登录失败 | `login-hint` → 热启动 `python login.py`（仅首次无 cookie 才 `ACQ_ALLOW_COLD_LOGIN=1`） |
| Elsevier 0 篇 | 检索式是否过窄；机构是否订阅该刊全文（Key alone 不等于全库 PDF） |
| 仍在用 MCP | 删除客户端里的 `gleaner` server；改用 CLI / Skill |

---

## License

[MIT](LICENSE) © [liuqiaodongdong](https://github.com/liuqiaodongdong)

本仓库代码按 MIT 许可开源：可自由使用、修改、分发（含闭源商用），保留版权与许可声明即可。

### 使用声明（与许可证独立）

- 请遵守知网、Elsevier 等平台服务条款，仅在合法授权（机构订阅等）范围内使用。  
- 验证码打码、第三方镜像等能力由你自行承担合规风险；**MIT 许可代码 ≠ 授权你违反第三方 ToS 或版权法**。  
- 本软件按「现状」提供，作者不对滥用、封禁或数据合规问题负责。

Issues / PR 欢迎：https://github.com/liuqiaodongdong/gleaner
