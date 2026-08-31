---
name: gleaner
description: >
  学术文献采集（知网 CNKI / Elsevier / 国际 OA·SciHub）。
  用仓库 gleaner_cli.py 跑 install-skill、status、prepare、cnki-list、cnki、els、intl。
  Use when: /gleaner、下知网、采文献、cnki、elsevier、国际论文、gleaner 采集、
  安装 gleaner、安装 skill、注册 skill、clone gleaner。
---

# Gleaner（Skill + CLI）

用本机仓库统一 CLI 做三线学术文献采集。

**仓库和 Skill 必须成对存在**：只拷 SKILL.md 采不了文献；只 clone 仓库、不注册 Skill，Agent 也找不到约定。下面两条路最后都要跑 `install-skill` 再 `status`。

## 安装（仓库 ↔ Skill）

官方仓库：https://github.com/liuqiaodongdong/gleaner.git  
需要 **Python 3.11+**。知网线建议 Windows + 系统 Edge。

### A. 用户说「安装项目 / clone gleaner / 装这个仓库」

1. `git clone https://github.com/liuqiaodongdong/gleaner.git` 到用户指定目录；未指定则当前工作区旁的 `gleaner/`。
2. `python -m venv .venv` 后激活，再 `pip install -r requirements.txt`。
3. **立刻** `python gleaner_cli.py install-skill`（把 `skill/gleaner` 注册到 `~/.grok/skills/gleaner`、`~/.cursor/skills/gleaner`、`~/.codex/skills/gleaner`，并写入 `.gleaner_root`）。
4. 当前会话设 `GLEANER_ROOT` 为仓库绝对路径。
5. `python gleaner_cli.py status`。线未 ready → 配 `.env`；知网无 `cookies.json` → 仅首次 `ACQ_ALLOW_COLD_LOGIN=1` 后 `python login.py`。
6. **不要**在未就绪时硬跑 `cnki` / `els` / `intl`。

### B. 用户说「安装 skill / 注册 skill / 装 gleaner skill」

1. 若本机没有含 `gleaner_cli.py` 的仓库：先走上面 A（clone + pip），**不要只拷 SKILL.md**。
2. 仓库已在：在仓库根执行 `python gleaner_cli.py install-skill`。
3. 设 `GLEANER_ROOT`，再 `status`，缺什么补什么。
4. 包装脚本会读 Skill 目录里的 `.gleaner_root`；当前会话仍建议设环境变量。

```powershell
$env:GLEANER_ROOT = "<本仓库绝对路径>"
python "$env:GLEANER_ROOT\gleaner_cli.py" install-skill
python "$env:GLEANER_ROOT\gleaner_cli.py" status
# 或
pwsh "$env:USERPROFILE\.grok\skills\gleaner\scripts\gleaner.ps1" status
```

子命令：`install-skill` | `status` | `sources` | `score` | `login-hint` | `prepare` | `cnki-list` | `cnki` | `els` | `intl`

## 默认根目录

优先级：`GLEANER_ROOT` → CLI `--root` → Skill 目录 `.gleaner_root`（包装脚本）→ 仓库内 `gleaner_cli.py` 所在目录。详见 [references/env.md](references/env.md)。

## 铁律

1. **先 status**：任何采集前必须先跑  
   `python "$env:GLEANER_ROOT\gleaner_cli.py" status`  
   看 `lines.*.ready` / `blockers` / `next_steps_for_user`。线未 ready → 引导配置，**禁止硬采**。

2. **知网先录 cookie**：`status` 里 `cookies.ok=false` 时 **禁止** 跑 `cnki` / `cnki-list`。Agent **只跑** `python login.py`（超级鹰过滑块后立刻写盘并退出）。**不要**用浏览器工具自己抠 cookie。仅第一次没有文件才加 `ACQ_ALLOW_COLD_LOGIN=1`。冷启动采集下不了全文，只会空烧超级鹰。

3. **长任务走 shell CLI**：`cnki-list` / `cnki` / `els` / `intl` 可能超过 30 分钟。用终端执行 CLI，**不要假设**会在固定超时内返回。过程与结果看 `corpus/*_run.log` 与结束时的摘要 JSON。

4. **Cookie 失效**：CNKI 下载/列表报登录、验证码反复失败、或疑似会话过期时：  
   - `python gleaner_cli.py login-hint`  
   - 已有 `cookies.json`：在 `GLEANER_ROOT` 下 `set ACQ_BROWSER_CHANNEL=msedge` 后 `python login.py`（热启动，禁止冷启动）  
   - 仅第一次没有 cookie：再加 `set ACQ_ALLOW_COLD_LOGIN=1`  
   完成后重跑 `status` 再采。无需个人知网账号。

5. **完成后汇报**：`local_dir` 路径、`metadata_rows` / `downloaded_files` 篇数、主要标题、`log_path`。0 篇也要报，并建议是否升 level / 放宽 query。

6. **细节文档**：环境与密钥见 [references/env.md](references/env.md)；标准流程见 [references/workflows.md](references/workflows.md)。

7. **禁止回显密钥**：不要打印 `CJY_*`、`ELSEVIER_API_KEY`、完整 cookies 或 `.elsevier_key` 内容。

## CNKI 推荐流程（分级）

1. Agent 按研究方向做同义发散，产出 concept groups JSON。  
2. `prepare --topic ... --concept-groups '...'`（或 `@path`）→ `keyword_workspace/<topic>/` 与 L1–L4 式。  
3. **先** `cnki-list --level L1 --search-md ...` 看 TOTAL。  
4. TOTAL 够用再 `cnki --level L1 ...` 全文。  
5. L1 太少且用户要更多 → 升 **L2**（用户明确同意后再 L3/L4）。

概念组示例：

```json
[
  {"name": "数字经济", "keywords": ["数字经济", "数字化", "数据要素"]},
  {"name": "全要素生产率", "keywords": ["全要素生产率", "TFP"]}
]
```

Elsevier / 国际见 [references/workflows.md](references/workflows.md)。

## 错误速查

| 现象 | 处理 |
|------|------|
| 找不到 gleaner_cli.py / Skill 未注册 | clone 仓库 → `pip install -r requirements.txt` → `install-skill` → 设 `GLEANER_ROOT` |
| setup / ready=false | 按 status 的 next_steps 配代理、CJY、**cookies**、Elsevier Key；无 cookie 勿开 cnki |
| cookie / 登录相关失败 | `login-hint` → 热启动 `python login.py`（仅首次 `ACQ_ALLOW_COLD_LOGIN=1`） |
| 子进程非 0 | 读 `corpus/*_run.log` 尾部，汇报 log 路径 |
| 0 命中 | 升 level、放宽年份或改 query；先 list 再 collect |
