# Gleanera · 知网校外机构版

Gleanera 用于**不在校园网范围内，且学校支持通过 CNKI 机构登录入口完成身份认证**的情况。用户在可见浏览器中选择学校并完成认证，程序确认知网显示机构身份后保存会话，后续复用该会话检索和采集文献。

本分支只提供 CNKI，国际线和 Elsevier 线的代码、命令及专属依赖已移除。普通版 `gleaner` 位于 `main`；机构版 `gleanera` 位于 `feature/cnki-institution-session`。两套技能、CLI 和根目录环境变量分别管理。

## 安装

需要 Python 3.11+、Git；Windows 建议安装系统 Edge。使用独立目录：

```powershell
git clone --branch feature/cnki-institution-session --single-branch https://github.com/liuqiaodongdong/gleaner.git gleanera
cd gleanera
python -m pip install -r requirements.txt
python gleanera_cli.py install-skill
python gleanera_cli.py status
```

技能安装到 Grok、Cursor、Codex 各自的 `skills/gleanera`，指针文件为 `.gleanera_root`。不会覆盖 `skills/gleaner`。可选环境变量为 `GLEANERA_ROOT`、`GLEANERA_PYTHON`；普通版的 `GLEANER_ROOT` 不参与机构版目录定位。

已有旧机构版目录更新后改用 `gleanera_cli.py`，重新执行 `install-skill` 注册新名称；现有本机 Cookie、会话标记、配置和文献文件保留。

## 网络与登录

默认直连，不自动读取 Windows 系统代理。VPN 的系统路由仍然生效。只有确实需要代理时才设置 `ACQ_PROXY`；模板中的 `PORT` 是占位符，必须换成代理程序的真实数字端口。状态检查仅校验配置格式，网络可用性在实际访问时确认。

```powershell
python login.py
python gleanera_cli.py status
```

`login.py` 默认打开 https://fsso.cnki.net/ ，等待用户完成学校统一认证。账号密码只在学校页面输入。首次认证不要求超级鹰，也不需要冷启动开关；`--institution` 作为旧用法仍兼容。

机构身份、知网 Cookie、无正在显示的验证码同时确认后才保存，更新失败会恢复原会话。关闭登录窗口或等待超时会返回失败，不覆盖已有会话。

采集过程中不自动重录或覆盖机构 Cookie。每次访问会检查机构身份；失效、身份未确认或批次无进展时停止并提示重新登录。本地 `status` 只检查会话文件与标记一致，实际有效性以访问结果为准。

采集中若出现验证码，可选填写 `CJY_USER`、`CJY_PASS`、`CJY_SOFTID` 并运行 `python gleanera_cli.py score` 检查服务。未配置时不把整个机构版标为不可用；需要验证码处理而无法完成时报告失败，保留会话。

## 检索与下载

```powershell
# 仅列表题录
python gleanera_cli.py cnki-list --query "数字经济" --num 30 --out-name demo_list
# 包含摘要、关键词、机构、基金的 11 列题录；不下载全文
python gleanera_cli.py cnki-list --details --query "数字经济" --num 30 --out-name demo_metadata
# 全文：串行多批直到达到目标，批间不重新登录
python gleanera_cli.py cnki --query "数字经济" --out-name demo_fulltext --until 30
```

支持 `prepare` 概念组、L1–L4 分级与 `--pro` 专业检索。先列表确认范围，再下载。L3/L4 扩展需用户同意。题录使用 `--num`；全文目标使用 `--until`，不要并行启动多套知网浏览器。

输出在本目录 `corpus/<批次>`。全文附带 `papers/`；仅题录不创建全文目录。失败时读取 `corpus/*_run.log`，以实际文件数和 `until_reached` 判断完成情况。

## 更新

```powershell
git pull --ff-only origin feature/cnki-institution-session
python -m pip install -r requirements.txt
python gleanera_cli.py install-skill
python gleanera_cli.py status
```

`institution.ps1 login/status/list/download/test` 继续可用，有 `.venv` 时优先使用其中的 Python。普通版更新 `main`，机构版更新自己的分支；不直接把普通版命令当作机构版执行。

## 本地数据

`.env`、`cookies.json`、`acq/cookies/`、日志、文献输出均留在本机并被 Git 忽略。删除采集线路不删除历史文献和凭据。不要把账号密码、Cookie 或学校认证页面内容提交到仓库。

开发测试：`python -m pytest -q`，仅收集 `tests/`，避免把旧迁移包中的测试当作当前测试。
