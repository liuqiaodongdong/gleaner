# Agent 使用约定（Gleaner Skill + CLI）

你正在使用 **gleaner** 学术文献采集能力。入口是 **Skill + `gleaner_cli.py`**。

## 装机（仓库 ↔ Skill，必须成对）

用户说「安装项目 / clone」或「安装 skill / 注册 skill / 安装这个 skill」时，**没有 `gleaner_cli.py` 就必须先 clone**。只拷 SKILL.md **不算装完**。

1. 本机没有 `gleaner_cli.py`（安装 skill 也走这一步）：  
   `git clone https://github.com/liuqiaodongdong/gleaner.git` → `pip install -r requirements.txt`
2. 在仓库根：`python gleaner_cli.py install-skill`  
   会拷到 `~/.grok/skills/gleaner`、`~/.cursor/skills/gleaner`、`~/.codex/skills/gleaner`，并写入 `.gleaner_root`。
3. 当前会话设 `GLEANER_ROOT` 为仓库绝对路径。
4. 再 `status`；知网无 cookie 则 Agent **自己**跑 `login.py`（脚本内超级鹰自动过滑块）。仅首次加 `ACQ_ALLOW_COLD_LOGIN=1`。不要只跑 `login-hint`，不要让用户手拖。

## 根目录与 Skill

| 项 | 说明 |
|----|------|
| 默认仓库根 | 见 `GLEANER_ROOT`；未设时用 `gleaner_cli.py` 所在仓库根或 CLI `--root` |
| 环境变量 | `GLEANER_ROOT` 指向本仓库根（含 `gleaner_cli.py`） |
| 用户 Skill | 仓库 `skill/gleaner/`；用 `install-skill` 注册到 `~/.grok` / `~/.cursor` / `~/.codex` |
| 凭据 | 优先进程环境 / `GLEANER_ROOT/.env`；Elsevier 也可 `acq/data/.elsevier_key` |

```powershell
$env:GLEANER_ROOT = "<本仓库绝对路径>"
python "$env:GLEANER_ROOT\gleaner_cli.py" status
# 或
pwsh "$env:USERPROFILE\.grok\skills\gleaner\scripts\gleaner.ps1" status
```

## 首次 / 采集前：必须做部署引导

1. **先跑** `python gleaner_cli.py status`（不要先假设用户已配好密钥）。
2. 阅读返回的 `lines.*.ready`、`blockers`、`next_steps_for_user`。
3. 若用户要用的线 `ready=false`：
   - **用清晰清单展示给用户**（申请网址、要填哪些环境变量、本地命令）。
   - **协助用户完成配置**（写 `GLEANER_ROOT/.env`、写 `acq/data/.elsevier_key`）。
   - **知网必须先有 `cookies.json`**：没有则 Agent **自己启动** `login.py`（有头 Edge，**脚本内超级鹰自动过滑块并写盘**）。禁止只打印 `login-hint`、禁止让用户手拖或复制 cookie。仅首次加 `ACQ_ALLOW_COLD_LOGIN=1`。**禁止**无 cookie 就跑 `cnki` / `cnki-list`（冷启动下不了全文，只会空烧超级鹰）。
   - **不要**在未就绪时强行跑 `cnki` / `els` / `intl`（CLI 会返回 `setup_incomplete`）。
4. 用户表示已配置后，**再跑一次** `status` 确认，再开始采集。

## 各线需要什么

| 线 | CLI 子命令 | 硬门槛 | 推荐 |
|---|---|---|---|
| CNKI 全文 | `cnki` | 机构代理 + 超级鹰 + **`cookies.json`** | 首次 `ACQ_ALLOW_COLD_LOGIN=1` 录 cookie；之后热启动 |
| CNKI 题录 | `cnki-list` | 机构代理 + **`cookies.json`** | 同上，无 cookie 不准开浏览器 |
| CNKI 分级建式 | `prepare` | 无（纯本地、不启浏览器） | Agent 先做关键词拓展 |
| Elsevier | `els` | **官方** `ELSEVIER_API_KEY` 或 `acq/data/.elsevier_key` | 见下方官方申请流程 |
| 国际 | `intl` | 公网（一般无需密钥） | CARSI cookie 可选 |
| 注册 Skill | `install-skill` | 仓库内有 `skill/gleaner/SKILL.md` | clone + pip 之后立刻跑 |
| 就绪检查 | `status` | — | 每次采集前 |
| 源摘要 | `sources` | — | 可选 |
| 超级鹰积分 | `score` | `CJY_*` | 排障 |
| 登录提示 | `login-hint` | — | **首次装机必做**；之后 cookie 过期再跑 |

## Elsevier 官方 API（必读·禁止误导）

`els` **只走 Elsevier 官方 Developer API**。引导用户时**必须**使用下列官方渠道，**禁止**推荐第三方 Key、破解、镜像站，或让用户爬 `sciencedirect.com` 网页代替 API。

### 官方链接

| 用途 | URL |
|------|-----|
| Developer Portal | https://dev.elsevier.com/ |
| 创建 / 管理 API Key | https://dev.elsevier.com/apikey/manage |
| 配额说明 | https://dev.elsevier.com/api_key_settings.html |
| 账号注册/登录 | https://account.elsevier.com/ |
| 本仓库详细步骤 | [`docs/ELSEVIER_API.md`](docs/ELSEVIER_API.md) |

### 正确申请步骤（照此告诉用户）

1. 用**学校/机构邮箱**在 https://account.elsevier.com/ 注册或登录（已有 ScienceDirect/Scopus 账号可通用）。
2. 打开 https://dev.elsevier.com/ ，登录。
3. 进入 https://dev.elsevier.com/apikey/manage → **Create API Key**。
4. Label 可填 `gleaner-local`；Website URL 本地可用 `http://localhost`（以页面校验为准）。
5. 复制 API Key → 写入 `GLEANER_ROOT/.env` 的 `ELSEVIER_API_KEY=...`，或单行写入 `acq/data/.elsevier_key`。
6. 再跑 `python gleaner_cli.py status`，确认 `lines.elsevier.ready=true`。

### 必须向用户澄清的事实

- Key 主要用于**官方 API 鉴权与配额**；**订阅全文**仍依赖机构订阅，未订的刊可能下不到全文。
- 学术机构用户对多数 Research Products API 有免费额度（Scival/Embase 等除外，本项目不用）。
- 完整说明、话术模板见 **`docs/ELSEVIER_API.md`**；`status` 的 `blockers[].apply_steps` 也会返回同样步骤。

### 超级鹰

- https://www.chaojiying.com/ （验证码类型 **9602**）

### 配置位置

- 推荐写在 `GLEANER_ROOT/.env`（模板：`.env.example`）
- Elsevier 也可：`acq/data/.elsevier_key`（已 gitignore）
- 系统/用户环境变量中的 `CJY_*` / `ACQ_*` / `ELSEVIER_*` 优先于 `.env`
- **禁止**把密钥、cookies 写进仓库或提交 git
- **禁止**在回复中回显完整 API key / 密码

## 采集流程（就绪后）

### CNKI 分级（推荐）

1. **Agent** 根据研究方向做同义发散与概念分组（CLI 不做 LLM 拓展）。
2. `python gleaner_cli.py prepare --topic ... --concept-groups '...'` → 写出 `keyword_workspace/<topic>/` 与 L1–L4 式子（含 `LY` 刊滤，白名单 `acq/data/cnki_journal_tiers.json`）。
3. **先** `cnki-list --level L1 --search-md ... --num N` 看 TOTAL；够用再全文。  
   **分批**：每批篇数在 40–60 **随机**（省略 `--num` 即可，禁止每批写死 50），**同一 `--out-name`** 续传；禁止一次拉满 TOTAL。批间热启动 `python login.py`，禁止并行开两个知网浏览器。后台跑 CLI，看 `corpus/*_run.log`，不要申请交互终端。
4. 产物在 `corpus/<批次>/`；过程日志见 `corpus/*_run.log`。结果少再升 L2→L3→L4（用户授权后）。

概念组 JSON 示例：
`[{"name":"数字经济","keywords":["数字经济","数字化","数据要素"]},{"name":"全要素生产率","keywords":["全要素生产率","TFP"]}]`

### 其它

- CNKI 兼容：`cnki --query ...` 或专业式（无分级、无 `LY`）。
- Elsevier：必须用**英文**布尔式或 `--concept-groups`（英文 keywords）。默认写入题名 `title`、按 `relevance` 排序；不要丢中文知网式或裸全文 `qs`。例：
  `python gleaner_cli.py els --query "\"supply chain\" AND \"green transition\"" --num 15`
  组式：`--concept-groups '[{"name":"sc","keywords":["supply chain"]},{"name":"gt","keywords":["green transition"]}]'`
  官方规则见 `docs/ELSEVIER_API.md`。高召回才 `--scope qs`。
- 国际：`intl`。
- 长任务用终端跑 CLI，**不要假设** 30 分钟内返回。

## 出错时

- `error: setup_incomplete` / `ready=false` → 继续部署引导，不要重试硬跑。
- Elsevier 缺 Key → **只**按 `docs/ELSEVIER_API.md` / 官方 Portal 引导。
- 验证码/下载失败 → 查 `score`、代理、cookies 是否过期；`login-hint` → 热启动 `python login.py`（不要冷启动续批次）。
- 细节见 `README.md` 与 Skill `references/`。
