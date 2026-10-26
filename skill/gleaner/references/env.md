# Gleaner 环境配置

根目录：CLI `--root` 优先，其次 `GLEANER_ROOT`，默认是脚本所在仓库。包装脚本另可读取技能目录中的 `.gleaner_root`。

在普通版仓库执行 `python gleaner_cli.py install-skill`，注册到 Grok/Cursor/Codex 的 `skills/gleaner`，不覆盖 `gleanera`。

| 配置 | 用途 |
|---|---|
| `CJY_USER` / `CJY_PASS` / `CJY_SOFTID` | 普通版知网自动验证码；填写真实值并用 `score` 验证 |
| `cookies.json` | 知网登录会话；首次 `python login.py --first-run` 建立 |
| `ELSEVIER_API_KEY` 或 `acq/data/.elsevier_key` | Elsevier 官方 API |
| `ACQ_PROXY` | 可选，知网代理；未设或为空默认直连 |
| `ACQ_BROWSER_CHANNEL` | 浏览器通道，Windows 登录默认 msedge |
| `ACQ_MANUAL_CAPTCHA=1` | 用户选择人工处理验证码时临时启用 |

默认直连，不读取 Windows 系统代理；VPN 系统路由仍然生效。需要代理时填写实际 `http://host:数字端口`、`https://host:数字端口` 或 `socks5://host:数字端口`。PORT 是占位符；代理并不提供订阅权益。状态检查只验证格式，不探测网络连通性。

CLI 从进程环境、仓库 `.env` 以及旧 `.mcp.json` 的对应配置加载凭据，优先保留进程已有值。模板占位值不是有效凭据。旧代理不再需要时，应清除 `.env` 和环境变量中的旧值。

凭据不回显、不提交 Git。超级鹰：https://www.chaojiying.com/ 。Elsevier：https://dev.elsevier.com/apikey/manage 。
