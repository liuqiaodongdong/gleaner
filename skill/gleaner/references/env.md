# Gleaner 环境与凭据

## 根目录 `GLEANER_ROOT`

CLI 解析优先级：

1. 环境变量 `GLEANER_ROOT`
2. CLI 参数 `--root PATH`
3. 默认：`gleaner_cli.py` 所在仓库根（随克隆目录变化，不写死本机路径）

```powershell
$env:GLEANER_ROOT = "<本仓库绝对路径>"
python "$env:GLEANER_ROOT\gleaner_cli.py" status
# 或
python gleaner_cli.py --root "<本仓库绝对路径>" status
```

包装脚本 `scripts/gleaner.ps1` / `scripts/gleaner.sh` 找仓库的顺序：

1. 环境变量 `GLEANER_ROOT`
2. Skill 目录里的 `.gleaner_root`（`python gleaner_cli.py install-skill` 写入，指向本机仓库）
3. 若 Skill 仍在仓库的 `skill/gleaner/` 内，向上查找 `gleaner_cli.py`

复制到 `~/.grok/skills/gleaner/` 等用户目录后，没有 `.gleaner_root` 时必须设 `GLEANER_ROOT`。Python 解释器可用 `GLEANER_PYTHON` 指定。

在仓库根执行一次即可同时注册到 Grok / Cursor / Codex：

```powershell
python gleaner_cli.py install-skill
```

## 凭据键（硬门槛）

| 键 / 文件 | 用途 | 线 |
|-----------|------|-----|
| `CJY_USER` / `CJY_PASS` / `CJY_SOFTID` | 超级鹰打码（类型 9602） | CNKI 全文 |
| `ACQ_PROXY` 或系统代理 | 机构网访问知网 | CNKI |
| `ACQ_HEADLESS` / `ACQ_BROWSER_CHANNEL` | 浏览器（CLI 全文默认 headless + msedge） | CNKI |
| `ELSEVIER_API_KEY` 或 `acq/data/.elsevier_key` | Elsevier 官方 Developer API | Elsevier |
| `cookies.json`（`python login.py`） | CNKI 机构会话，**硬门槛**；无文件禁止 `cnki`/`cnki-list`。仅首次 `ACQ_ALLOW_COLD_LOGIN=1` | CNKI 必需 |

超级鹰：https://www.chaojiying.com/  
Elsevier Key：https://dev.elsevier.com/apikey/manage （仅官方，禁止第三方/破解）

## CLI 如何加载凭据

`gleaner_cli.py` 启动时经 `acq.cli_support.load_credentials`：

1. **进程已有环境变量**（最高，不覆盖已设值）
2. **`GLEANER_ROOT/.env`**（键=值，UTF-8；已 gitignore，勿提交）
3. Elsevier 另可读 **`acq/data/.elsevier_key`**（单行 Key，已 gitignore）
   （本机若还留着旧 `.mcp.json` 的 env 段，也会当补缺读入，不必新写）

白名单前缀：`CJY_*`、`ACQ_*`、`ELSEVIER_*` 及上表显式键。

## 安全

- **禁止**在对话、日志、commit、截图里回显完整 API key、密码、cookies。
- 配置就绪后只复述「已配置 / 未配置」，不打印值。
- 密钥文件与 `.env` 不得写入 git。

## 自检

```powershell
python "$env:GLEANER_ROOT\gleaner_cli.py" status
python "$env:GLEANER_ROOT\gleaner_cli.py" score    # 超级鹰积分（需 CJY_*）
python "$env:GLEANER_ROOT\gleaner_cli.py" login-hint
```
