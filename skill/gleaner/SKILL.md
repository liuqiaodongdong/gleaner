---
name: gleaner
description: >
  学术文献采集（知网 CNKI / Elsevier / 国际 OA·SciHub）。
  用仓库 gleaner_cli.py 跑 status、prepare、cnki-list、cnki、els、intl。
  Use when: /gleaner、下知网、采文献、cnki、elsevier、国际论文、gleaner 采集。
---

# Gleaner（Skill + CLI）

用本机仓库统一 CLI 做三线学术文献采集。

## 默认根目录

优先级：`GLEANER_ROOT` 环境变量 → CLI `--root` → 仓库内 `gleaner_cli.py` 所在目录。详见 [references/env.md](references/env.md)。

把本目录复制到用户 Skill 后，请先设置 `GLEANER_ROOT` 指向克隆下来的仓库根。

```powershell
$env:GLEANER_ROOT = "<本仓库绝对路径>"
python "$env:GLEANER_ROOT\gleaner_cli.py" status
# 或
pwsh "$env:USERPROFILE\.grok\skills\gleaner\scripts\gleaner.ps1" status
```

子命令：`status` | `sources` | `score` | `login-hint` | `prepare` | `cnki-list` | `cnki` | `els` | `intl`

## 铁律

1. **先 status**：任何采集前必须先跑  
   `python "$env:GLEANER_ROOT\gleaner_cli.py" status`  
   看 `lines.*.ready` / `blockers` / `next_steps_for_user`。线未 ready → 引导配置，**禁止硬采**。

2. **长任务走 shell CLI**：`cnki-list` / `cnki` / `els` / `intl` 可能超过 30 分钟。用终端执行 CLI，**不要假设**会在固定超时内返回。过程与结果看 `corpus/*_run.log` 与结束时的摘要 JSON。

3. **Cookie 失效**：CNKI 下载/列表报登录、验证码反复失败、或疑似会话过期时：  
   - `python gleaner_cli.py login-hint`  
   - 已有 `cookies.json`：在 `GLEANER_ROOT` 下 `set ACQ_BROWSER_CHANNEL=msedge` 后 `python login.py`（热启动，禁止冷启动）  
   - 仅第一次没有 cookie：再加 `set ACQ_ALLOW_COLD_LOGIN=1`  
   完成后重跑 `status` 再采。无需个人知网账号。

4. **完成后汇报**：`local_dir` 路径、`metadata_rows` / `downloaded_files` 篇数、主要标题、`log_path`。0 篇也要报，并建议是否升 level / 放宽 query。

5. **细节文档**：环境与密钥见 [references/env.md](references/env.md)；标准流程见 [references/workflows.md](references/workflows.md)。

6. **禁止回显密钥**：不要打印 `CJY_*`、`ELSEVIER_API_KEY`、完整 cookies 或 `.elsevier_key` 内容。

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
| setup / ready=false | 按 status 的 next_steps 配代理、CJY、Elsevier Key；勿重试硬采 |
| cookie / 登录相关失败 | `login-hint` → 热启动 `python login.py`（仅首次 `ACQ_ALLOW_COLD_LOGIN=1`） |
| 子进程非 0 | 读 `corpus/*_run.log` 尾部，汇报 log 路径 |
| 0 命中 | 升 level、放宽年份或改 query；先 list 再 collect |
