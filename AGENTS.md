# Agent 使用约定（Gleaner MCP）

你正在使用 **gleaner** 学术文献采集 MCP。本文件约束你的行为。

## 首次 / 采集前：必须做部署引导

1. **先调用** `setup_status`（不要先假设用户已配好密钥）。
2. 阅读返回的 `lines.*.ready`、`blockers`、`next_steps_for_user`。
3. 若用户要用的线 `ready=false`：
   - **用清晰清单展示给用户**（申请网址、要填哪些环境变量、本地命令）。
   - **协助用户完成配置**（改 MCP `env`、写 `acq/data/.elsevier_key`、跑 `python login.py` 等）。
   - **不要**在未就绪时强行调用 `cnki_collect` / `els_collect`（工具会返回 `setup_incomplete`）。
4. 用户表示已配置后，**再调一次** `setup_status` 确认，再开始采集。

## 各线需要什么

| 线 | 工具 | 硬门槛 | 推荐 |
|---|---|---|---|
| CNKI 全文 | `cnki_collect` | 机构代理 `ACQ_PROXY`/系统代理 + 超级鹰 `CJY_USER/PASS/SOFTID` | `python login.py` → `cookies.json` |
| CNKI 题录 | `cnki_list` | 机构代理 | cookies |
| CNKI 分级建式 | `cnki_prepare` | 无（纯本地、不启浏览器） | Agent 先做关键词拓展 |
| Elsevier | `els_collect` | **官方** `ELSEVIER_API_KEY` 或 `acq/data/.elsevier_key` | 见下方官方申请流程 |
| 国际 | `intl_collect` | 公网（一般无需密钥） | CARSI cookie 可选 |

## Elsevier 官方 API（必读·禁止误导）

`els_collect` **只走 Elsevier 官方 Developer API**。引导用户时**必须**使用下列官方渠道，**禁止**推荐第三方 Key、破解、镜像站，或让用户爬 `sciencedirect.com` 网页代替 API。

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
5. 复制 API Key → 写入 MCP `env` 的 `ELSEVIER_API_KEY`，或单行写入 `acq/data/.elsevier_key`。
6. 再调 `setup_status`，确认 `lines.elsevier.ready=true`。

### 必须向用户澄清的事实

- Key 主要用于**官方 API 鉴权与配额**；**订阅全文**仍依赖机构订阅，未订的刊可能下不到全文。
- 学术机构用户对多数 Research Products API 有免费额度（Scival/Embase 等除外，本项目不用）。
- 完整说明、话术模板见 **`docs/ELSEVIER_API.md`**；`setup_status` 的 `blockers[].apply_steps` 也会返回同样步骤。

### 超级鹰

- https://www.chaojiying.com/ （验证码类型 **9602**）

### 配置位置

- 推荐写在 MCP 配置的 `env` 字段（模板：`.mcp.json.example`）
- Elsevier 也可：`acq/data/.elsevier_key`（已 gitignore）
- **禁止**把密钥、cookies 写进仓库或提交 git
- **禁止**在回复中回显完整 API key / 密码

## 采集流程（就绪后）

### CNKI 分级（推荐）

1. **Agent** 根据研究方向做同义发散与概念分组（MCP 不做 LLM 拓展）。
2. `cnki_prepare(topic, concept_groups_json)` → 写出 `keyword_workspace/<topic>/` 与 L1–L4 式子（含 `LY` 刊滤，白名单 `acq/data/cnki_journal_tiers.json`）。
3. `cnki_collect(level="L1", search_md=..., num=N)` 或 `cnki_list(...)`；结果少再升 L2→L3→L4。
4. 产物在 `corpus/<批次>/`。

概念组 JSON 示例：
`[{"name":"数字经济","keywords":["数字经济","数字化","数据要素"]},{"name":"全要素生产率","keywords":["全要素生产率","TFP"]}]`

### 其它

- CNKI 兼容：`cnki_collect(query=..., pro=False/True)`（无分级、无 `LY`）。
- Elsevier / 国际：`els_collect` / `intl_collect`。

## 出错时

- `error: setup_incomplete` → 继续部署引导，不要重试硬跑。
- Elsevier 缺 Key → **只**按 `docs/ELSEVIER_API.md` / 官方 Portal 引导。
- 验证码/下载失败 → 查 `chaojiying_score`、代理、cookies 是否过期。
- 细节见 `README.md`。
