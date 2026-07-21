# Agent 使用约定（Gleaner MCP）

你正在使用 **gleaner** 学术文献采集 MCP。本文件约束你的行为。

## 首次 / 采集前：必须做部署引导

1. **先调用** `setup_status`（不要先假设用户已配好密钥）。
2. 阅读返回的 `lines.*.ready`、`blockers`、`next_steps_for_user`。
3. 若用户要用的线 `ready=false`：
   - **用清晰清单展示给用户**（申请网址、要填哪些环境变量、本地命令）。
   - **协助用户完成配置**（告诉他改 MCP `env`、写 `acq/data/.elsevier_key`、跑 `python login.py` 等）。
   - **不要**在未就绪时强行调用 `cnki_collect` / `els_collect`（工具会返回 `setup_incomplete`，应据此继续引导）。
4. 用户表示已配置后，**再调一次** `setup_status` 确认，再开始采集。

## 各线需要什么

| 线 | 工具 | 硬门槛 | 推荐 |
|---|---|---|---|
| CNKI 全文 | `cnki_collect` | 机构代理 `ACQ_PROXY`/系统代理 + 超级鹰 `CJY_USER/PASS/SOFTID` | `python login.py` → `cookies.json` |
| CNKI 题录 | `cnki_list` | 机构代理 | cookies |
| Elsevier | `els_collect` | `ELSEVIER_API_KEY` 或 `acq/data/.elsevier_key` | — |
| 国际 | `intl_collect` | 公网（一般无需密钥） | CARSI cookie 可选 |

### 申请链接（引导用户时给出）

- 超级鹰：https://www.chaojiying.com/ （验证码类型 **9602**）
- Elsevier API：https://dev.elsevier.com/ → Create API Key（建议学校邮箱）

### 配置位置

- 推荐写在 MCP 配置的 `env` 字段（模板：`.mcp.json.example`）
- Elsevier 也可单行文件：`acq/data/.elsevier_key`（已 gitignore）
- **禁止**把密钥、cookies 写进仓库或提交 git
- **禁止**在回复中回显完整 API key / 密码

## 采集流程（就绪后）

主题 → 检索式（可用 keyword-expander / 高级检索技能）→  
`cnki_collect(pro=True)` / `els_collect` / `intl_collect` →  
产物在 `corpus/<批次>/`（`metadata.csv` + `papers/`）。

## 出错时

- `error: setup_incomplete` → 继续部署引导，不要重试硬跑。
- 验证码/下载失败 → 查 `chaojiying_score`、代理、cookies 是否过期。
- 细节见 `README.md`。
