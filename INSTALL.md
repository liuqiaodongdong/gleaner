# 安装

完整说明见 [README.md](README.md)。

```bash
git clone https://github.com/liuqiaodongdong/gleaner.git
cd gleaner
pip install -r requirements.txt
```

需要 **Python 3.11+**。采集入口是 `gleaner_cli.py`。

## 配置

1. 复制 [`.env.example`](.env.example) 为 `.env`，按需填写 `CJY_*`、`ELSEVIER_API_KEY`、`ACQ_PROXY` 等（**不要**提交 git）。
2. Elsevier 也可把 Key 单行写入 `acq/data/.elsevier_key`。
3. 可选：设置环境变量 `GLEANER_ROOT` 指向本仓库根。
4. 知网**必须先有 cookies.json** 再采。Agent 跑 `login.py`：超级鹰自动过滑块并写入文件，用户不用手填 cookie。仅首次无文件才 `ACQ_ALLOW_COLD_LOGIN=1`。无 cookie 禁止 `cnki` / `cnki-list`（会空烧超级鹰）。

## 使用（Skill + CLI）

用统一 CLI：

```bash
# 就绪检查（务必先跑）
python gleaner_cli.py status

# 子命令
python gleaner_cli.py prepare|cnki-list|cnki|els|intl|login-hint|sources|score
```

在 Grok 中安装用户 Skill：把仓库 `skill/gleaner/` 复制到 `~/.grok/skills/gleaner/`，并设置 `GLEANER_ROOT`。
