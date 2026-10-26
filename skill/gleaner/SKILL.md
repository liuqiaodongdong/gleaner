---
name: gleaner
description: >
  普通版学术文献采集（CNKI / Elsevier）。默认直连、代理可选。
  安装时先克隆仓库、安装依赖，再执行 gleaner_cli.py install-skill。
  知网首次验证运行 python login.py --first-run，超级鹰由项目脚本调用。
  校外学校机构入口登录请使用独立技能 gleanera。
---

# Gleaner 普通版

仓库：https://github.com/liuqiaodongdong/gleaner.git，分支 `main`。只提供 CNKI 与 Elsevier 两条线路。

## 安装与更新

新安装先克隆完整仓库，不能只复制 SKILL.md。已有仓库先检查 Git 状态，再更新 `main`。

```powershell
git clone https://github.com/liuqiaodongdong/gleaner.git <dest>
cd <dest>
python -m pip install -r requirements.txt
python gleaner_cli.py install-skill
python gleaner_cli.py status
```

需要 Python 3.11+；Windows 建议系统 Edge。技能注册到各客户端的 `skills/gleaner`，`.gleaner_root` 指向本仓库，与 `gleanera` 独立。根目录优先使用 CLI `--root`，其次 `GLEANER_ROOT`；包装脚本可读取技能指针。

## 网络与首次验证

- 默认直连，校园网或 VPN 的系统路由仍生效；无需代理软件或端口。`ACQ_PROXY` 仅在用户确实需要代理时配置，不自动读取系统代理。不能把 `PORT` 占位符填入有效配置。
- `status` 检查本地配置，不能据此宣称机构权限或远端账号已验证。
- 首次填写实际 `CJY_USER`、`CJY_PASS`、`CJY_SOFTID`，运行 `python gleaner_cli.py score` 验证账号和积分。占位值不算已配置；报错先修正，不能直接开始验证码调用。
- 无 `cookies.json` 时，由 Agent 运行 `python login.py --first-run`。以后运行 `python login.py` 复用已有会话。Windows 自动选择 Edge；其它平台须安装 Playwright 浏览器或指定 `ACQ_BROWSER_CHANNEL`。
- 登录脚本内部完成超级鹰调用与平稳拖动，Agent 不另调打码接口，也不重复操纵同一个验证页面。自动最多两次；失败返回非零退出码，报告实际原因，不把退出或创建文件视为成功。
- 默认不切换为人工等待。只有用户明确选择人工验证，才临时设置 `ACQ_MANUAL_CAPTCHA=1`，人工等待最多 90 秒。
- 确认登录输出 `ok=true` 并保存非空会话后，再运行 `status`。未就绪时不能启动采集；机构权限仍由实际访问结果验证。

## 采集

先 `status`，根据需要选择线路，不自动转用其它来源。

### CNKI 完整题录

```powershell
python gleaner_cli.py cnki-list --details --query "数字经济" --num 50 --out-name demo_metadata
```

输出标题、作者、摘要、关键词、期刊、日期、机构、基金、被引次数、下载次数、URL 共 11 列。仅访问列表和详情，不下载全文、不创建 papers；使用 `--num`，不用 `--until`。不要与全文批次复用输出目录。省略 `--details` 为列表页 7 列。

### CNKI 全文

由 Agent 拓展概念组，`prepare` 生成 L1–L4 检索式；先 `cnki-list` 看命中数，再 `cnki`。L1 不够可升 L2；L3/L4 经用户明确同意后使用。

目标篇数为用户指定或列表 TOTAL。使用同一 `--out-name` 和 `--until <目标>` 串行多批，每批 40–60 篇随机；不要一次拉满、不要并行浏览器。普通版批间可自动热启动登录脚本，失败即停止。只有 `until_reached` 和实际文件数满足目标才报告采够。

### Elsevier

只使用官方 Developer API，Key 来自 https://dev.elsevier.com/apikey/manage 。支持英文布尔式、概念组及期刊分级。默认保存完整 PDF＋XML；PDF 通过正文对象接口下载并验证身份及可用页数。PDF 失败时保留 XML 并报告原因，不能计为完整下载。

## 运行与汇报

长任务用终端 CLI，不擅自增加固定超时；查看 `corpus/*_run.log`。汇报 `local_dir`、`metadata_rows`、实际 PDF/CAJ 或 XML 数量、主要标题和日志。零下载和部分失败如实报告。

凭据仅存本机忽略文件或环境变量；不回显、不提交密钥或 Cookie。详见 [环境配置](references/env.md) 和 [工作流](references/workflows.md)。
