---
name: gleaner
description: >
  学术文献采集（知网 CNKI / Elsevier / 国际 OA·SciHub）。
  用户说「安装 skill / 注册 skill / 装 gleaner」时：必须先 git clone
  https://github.com/liuqiaodongdong/gleaner.git ，再 pip 与
  python gleaner_cli.py install-skill。只把 SKILL.md 拷到 ~/.cursor/skills 不算安装。
  无 cookies.json 时 Agent 必须自己跑 python login.py（脚本内超级鹰自动过滑块）。
  Use when: /gleaner、下知网、采文献、cnki、elsevier、国际论文、gleaner 采集、
  安装 gleaner、安装 skill、安装这个 skill、注册 skill、clone gleaner、
  录 cookie、登录知网、login.py、超级鹰、cookies.json。
---

# Gleaner（Skill + CLI）

用本机仓库统一 CLI 做三线学术文献采集。

## 安装 skill = 先下载项目（禁止只拷 SKILL.md）

用户说「安装 skill / 注册 skill / 装 gleaner」时，**第一条命令必须是 clone 仓库**。
没有 `gleaner_cli.py` 就还没装完。只拷本文件到 `~/.cursor/skills/gleaner` **无效**。

```powershell
# 用户指定了目录就用那个；否则当前工作区下的 gleaner\
git clone https://github.com/liuqiaodongdong/gleaner.git <dest>
cd <dest>
python -m pip install -r requirements.txt
python gleaner_cli.py install-skill
$env:GLEANER_ROOT = (Resolve-Path .).Path
python gleaner_cli.py status
```

本机已有仓库：在仓库根跑 `python gleaner_cli.py install-skill`。  
Skill 目录里已有脚本时：`python scripts/bootstrap.py`（没有仓库会自己 clone）。

然后才能录 cookie、再采集。

## 录 cookie（Agent 自己做，不要问用户拖滑块）

`status` 里 `cookies.ok=false` 或用户说「登录 / 录 cookie」时：

1. 先确认 `.env` 有 `CJY_USER` / `CJY_PASS` / `CJY_SOFTID`（没有则协助写好，再 `status`）。
2. **Agent 自己启动**（不要只跑 `login-hint`，不要让用户手拖或从 DevTools 复制）：
   - 首次无文件：`$env:ACQ_BROWSER_CHANNEL='msedge'; $env:ACQ_ALLOW_COLD_LOGIN='1'; python login.py`
   - 已有文件（批间重录）：只设 `ACQ_BROWSER_CHANNEL=msedge`，再 `python login.py`
3. `login.py` **内部**用超级鹰 9602 过滑块并立刻写 `cookies.json`。Agent **不要**另调超级鹰 API、不要用浏览器工具抠 cookie。
4. 终端出现 `已更新会话` 后重跑 `status`，再采。无个人知网账号。

官方仓库：https://github.com/liuqiaodongdong/gleaner.git  
需要 **Python 3.11+**。知网线建议 Windows + 系统 Edge。

clone + `install-skill` 之后设 `GLEANER_ROOT`，再 `status`。线未 ready → 配 `.env`；无 cookie → Agent 自己跑 `login.py`。**不要**未就绪就硬采。

```powershell
$env:GLEANER_ROOT = "<本仓库绝对路径>"
python "$env:GLEANER_ROOT\gleaner_cli.py" status
pwsh "$env:USERPROFILE\.grok\skills\gleaner\scripts\gleaner.ps1" status
```

子命令：`install-skill` | `status` | `sources` | `score` | `login-hint` | `prepare` | `cnki-list` | `cnki` | `els` | `intl`

## 默认根目录

优先级：`GLEANER_ROOT` → CLI `--root` → Skill 目录 `.gleaner_root`（包装脚本）→ 仓库内 `gleaner_cli.py` 所在目录。详见 [references/env.md](references/env.md)。

## 铁律

1. **先 status**：任何采集前必须先跑  
   `python "$env:GLEANER_ROOT\gleaner_cli.py" status`  
   看 `lines.*.ready` / `blockers` / `next_steps_for_user`。线未 ready → 引导配置，**禁止硬采**。

2. **知网先录 cookie**：`status` 里 `cookies.ok=false` 时 **禁止** 跑 `cnki` / `cnki-list`。Agent **必须自己启动** `python login.py`（超级鹰在脚本里自动过滑块并写盘）。**禁止**：只打印 `login-hint` 就停、让用户手拖滑块、让用户从浏览器复制 cookie、用浏览器工具抠 cookie、另外调用超级鹰接口。仅第一次没有文件才加 `ACQ_ALLOW_COLD_LOGIN=1`。冷启动采集下不了全文，只会空烧超级鹰。

3. **知网全文必须分批**：`cnki-list` 看到 TOTAL 后，**禁止**一次 `--num` 拉满（如 200+）。每批篇数在 **40–60 随机**（省略 `--num` 由 CLI 抽；**禁止每批都写 50**）。**同一 `--out-name`** 续传（已下的会跳过）。批与批之间热启动 `python login.py` 换新 cookie，**禁止**同时开两个知网浏览器。不要申请「交互终端」；后台跑 CLI，进度看 `corpus/*_run.log`。

4. **长任务走 shell CLI**：`cnki-list` / `cnki` / `els` / `intl` 可能超过 30 分钟。用终端执行 CLI，**不要假设**会在固定超时内返回。过程与结果看 `corpus/*_run.log` 与结束时的摘要 JSON。

5. **Cookie 失效**：CNKI 下载/列表报登录、验证码反复失败、或疑似会话过期时：  
   - `python gleaner_cli.py login-hint`  
   - 已有 `cookies.json`：在 `GLEANER_ROOT` 下 `set ACQ_BROWSER_CHANNEL=msedge` 后 `python login.py`（热启动，禁止冷启动）  
   - 仅第一次没有 cookie：再加 `set ACQ_ALLOW_COLD_LOGIN=1`  
   完成后重跑 `status` 再采。无需个人知网账号。

6. **完成后汇报**：`local_dir` 路径、`metadata_rows` / `downloaded_files` 篇数、主要标题、`log_path`。0 篇也要报，并建议是否升 level / 放宽 query。

7. **细节文档**：环境与密钥见 [references/env.md](references/env.md)；标准流程见 [references/workflows.md](references/workflows.md)。

8. **禁止回显密钥**：不要打印 `CJY_*`、`ELSEVIER_API_KEY`、完整 cookies 或 `.elsevier_key` 内容。

## CNKI 推荐流程（分级）

1. Agent 按研究方向做同义发散，产出 concept groups JSON。  
2. `prepare --topic ... --concept-groups '...'`（或 `@path`）→ `keyword_workspace/<topic>/` 与 L1–L4 式。  
3. **先** `cnki-list --level L1 --search-md ...` 看 TOTAL。  
4. TOTAL 够用再 `cnki --level L1 --out-name <固定名>` 全文（不要带死 `--num 50`）；剩余下一批评同一 `out-name`，批间热启动 `login.py`。  
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
| 找不到 gleaner_cli.py / 用户说安装 skill | **先 clone 仓库**，再 pip + `install-skill`；禁止只拷 SKILL.md |
| setup / ready=false | 按 status 的 next_steps 配代理、CJY、**cookies**、Elsevier Key；无 cookie 勿开 cnki |
| cookie / 登录相关失败 | Agent 自己热启动 `python login.py`（仅首次 `ACQ_ALLOW_COLD_LOGIN=1`）；不要只跑 login-hint |
| 子进程非 0 | 读 `corpus/*_run.log` 尾部，汇报 log 路径 |
| 0 命中 | 升 level、放宽年份或改 query；先 list 再 collect |
