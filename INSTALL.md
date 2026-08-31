# 安装

完整说明见 [README.md](README.md)。

```bash
git clone https://github.com/liuqiaodongdong/gleaner.git
cd gleaner
pip install -r requirements.txt
```

需要 **Python 3.11+**。生产采集只用 `gleaner_cli.py`，**不需要、也不安装 `mcp` 包**。`acq_mcp.py` 仅仓库内对照，勿用于生产。

## 配置

1. 复制 [`.env.example`](.env.example) 为 `.env`，按需填写 `CJY_*`、`ELSEVIER_API_KEY`、`ACQ_PROXY` 等（**不要**提交 git）。
2. Elsevier 也可把 Key 单行写入 `acq/data/.elsevier_key`。
3. 可选：设置环境变量 `GLEANER_ROOT` 指向本仓库根。
4. 知网登录见 `python gleaner_cli.py login-hint`：已有 cookie 热启动 `python login.py`；仅首次无 cookie 才 `ACQ_ALLOW_COLD_LOGIN=1`。

## 使用（Skill + CLI）

Gleaner **不再通过 MCP 暴露**。请用统一 CLI：

```bash
# 就绪检查（务必先跑）
python gleaner_cli.py status

# 子命令
python gleaner_cli.py prepare|cnki-list|cnki|els|intl|login-hint|sources|score
```

在 Grok 中安装用户 Skill：把仓库 `skill/gleaner/` 复制到 `~/.grok/skills/gleaner/`，并设置 `GLEANER_ROOT`。

历史 MCP 模板 [`.mcp.json.example`](.mcp.json.example) 仅保留 **env 键名** 供迁移到 `.env`；`acq_mcp.py` 为 legacy，勿用于生产。
