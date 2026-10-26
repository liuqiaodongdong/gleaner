# Gleanera 环境配置

CLI `--root` 优先，其次 `GLEANERA_ROOT`；默认是 gleanera_cli.py 所在仓库。包装脚本读取 `.gleanera_root`；可用 `GLEANERA_PYTHON` 指定 Python。

默认直连，ACQ_PROXY 完全可选，不自动使用系统代理。校园 VPN 的系统路由仍有效。配置代理时必须使用实际 host 和数字端口；未配置无需安装代理软件。

机构会话通过 `python login.py` 建立，存入本目录 cookies.json 和 acq/cookies/cnki/session.json，不能移用普通版文件冒充已确认机构身份。

CJY_USER / CJY_PASS / CJY_SOFTID 为采集验证码的可选配置；不要求外部论文 API Key。机密只存本地 .env、忽略文件或进程环境，不回显或提交。

旧安装迁移：保留本机配置与会话，改用 gleanera_cli.py 并重新 install-skill。若不再需要旧代理，从 .env 和环境变量中清除 ACQ_PROXY。无需更改普通版的技能或路径。
