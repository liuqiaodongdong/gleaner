# 安装速查

完整说明见 **[README.md](README.md)**。此处只列最短路径。

## 1. 依赖

```bash
pip install -r requirements.txt
# 可选：playwright install chromium   # 不用系统 Edge 时
```

## 2. 密钥（本机，勿提交）

| 变量 / 文件 | 用途 |
|---|---|
| `ELSEVIER_API_KEY` 或 `acq/data/.elsevier_key` | Elsevier |
| `CJY_USER` / `CJY_PASS` / `CJY_SOFTID` | CNKI 验证码（超级鹰） |
| `ACQ_PROXY`（可选） | CNKI 机构代理 |

模板：`.env.example`、`.mcp.json.example`。

## 3. 注册 MCP

把 `.mcp.json.example` 中的路径与 `env` 填好，合并进 Claude 的 `mcpServers`（如 `~/.claude.json`），重启客户端。入口文件：`acq_mcp.py`，server 名：`gleaner`。

## 4. 自检

```bash
git check-ignore -v cookies.json acq/data/.elsevier_key .mcp.json
python -c "from acq.setup_check import check_setup; import json; print(json.dumps(check_setup(), ensure_ascii=False, indent=2))"
# 或在 MCP 客户端调用工具 setup_status
```

Agent 约定见 [`AGENTS.md`](AGENTS.md)：首次使用先 `setup_status`，再按清单引导用户配置。
