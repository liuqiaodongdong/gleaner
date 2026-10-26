# Gleanera 工作流

1. 在机构版仓库执行 `python gleanera_cli.py status`。
2. 未建立或已失效的机构会话：`python login.py`，用户在学校页面认证，脚本确认知网机构身份后保存。
3. `cnki-list --query <关键词> --num N` 查看列表。完整题录加 `--details`，不用 --until，也不继续下载全文。
4. 需要全文时，`cnki --query <关键词> --out-name <固定名> --until N` 串行采集。批间不自动登录；失败停止并保留会话。
5. 核对实际输出，报告题录、PDF/CAJ 数量与日志。默认直连、代理可选；文件存在仅表示本地会话已保存，不代替实际访问确认。

概念组和分级检索使用 prepare 与 --level / --search-md。L3/L4 扩展需要用户同意。所有输出和登录状态属于本机构版目录。
