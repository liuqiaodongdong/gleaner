# 安装普通版 Gleaner

需要 Python 3.11+、Git；Windows 知网采集建议安装系统 Edge。已有仓库可直接更新，无需重复克隆。

```powershell
git clone https://github.com/liuqiaodongdong/gleaner.git
cd gleaner
python -m pip install -r requirements.txt
python gleaner_cli.py install-skill
python gleaner_cli.py status
```

普通版提供 CNKI 和 Elsevier，技能名为 `gleaner`。校外机构登录版 `gleanera` 位于独立分支，使用独立技能目录。

## 网络与凭据

默认直连，安装不要求代理。校园网/VPN 的系统路由正常生效。确实需要本地代理时才在 `.env` 中填写 `ACQ_PROXY`；模板中的 `PORT` 必须换为真实数字端口。程序不会自动采用 Windows 系统代理。旧安装若遗留无效代理，应从 `.env` 和当前环境中移除该配置。

按需填写 `.env` 中的超级鹰凭据 `CJY_USER`、`CJY_PASS`、`CJY_SOFTID`；Elsevier 单独配置官方 Key，亦可保存在 `acq/data/.elsevier_key`。模板占位值不算已配置。凭据、会话及文献数据不提交 Git。

## 首次知网验证

```powershell
python gleaner_cli.py score
python login.py --first-run
python gleaner_cli.py status
```

先通过 `score` 确认账号和积分，再由 Agent 执行项目内登录脚本。看到成功保存会话且命令退出码为 0 后继续；失败先读取错误说明，修正配置或网络，不连续盲目重试。后续刷新运行 `python login.py`。

知网使用前仍需有有效的机构访问权限及 `cookies.json`。默认自动验证；仅用户选择人工验证时设置 `ACQ_MANUAL_CAPTCHA=1`。全文批量采集使用同一 `--out-name` 和 `--until <目标>`。

## 更新

```powershell
git pull --ff-only origin main
python -m pip install -r requirements.txt
python gleaner_cli.py install-skill
python gleaner_cli.py status
```

`install-skill` 更新 `gleaner` 技能并记录当前仓库位置，不覆盖既有 `.env`。完整命令见 [README.md](README.md)。
