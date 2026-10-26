# 安装 Gleanera 机构版

适用情况：位于校外，学校支持通过 CNKI 机构入口登录。先克隆机构分支到独立目录：

```powershell
git clone --branch feature/cnki-institution-session --single-branch https://github.com/liuqiaodongdong/gleaner.git gleanera
cd gleanera
python -m pip install -r requirements.txt
python gleanera_cli.py install-skill
python login.py
python gleanera_cli.py status
```

Python 3.11+；Windows 使用系统 Edge。首次学校机构认证由用户在浏览器完成，脚本确认机构身份后自动保存知网会话。

默认直连，`ACQ_PROXY` 可选，PORT 占位符必须替换为真实端口。无需 Elsevier Key，首次机构登录无需超级鹰；采集验证码的超级鹰配置为可选。

机构版使用 `gleanera_cli.py`、`GLEANERA_ROOT`、`skills/gleanera` 和 `.gleanera_root`。普通版使用原来的 `gleaner` 名称，两者可以同时安装。

旧机构版更新后执行 `python gleanera_cli.py install-skill` 注册新名称；本机 `.env`、Cookie、机构会话标记和文献输出保留。详见 [README](README.md)。
