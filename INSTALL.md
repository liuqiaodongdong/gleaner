# 安装

完整说明见 [README.md](README.md)。

```bash
git clone https://github.com/liuqiaodongdong/gleaner-mcp.git
cd gleaner-mcp
pip install -r requirements.txt
```

将 [`.mcp.json.example`](.mcp.json.example) 中的路径与 `env` 填入 MCP 客户端配置，重启后调用 `setup_status` 检查是否就绪。
