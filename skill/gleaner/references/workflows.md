# Gleaner 工作流

## 新电脑首次使用

1. 安装完整仓库和依赖，执行 `python gleaner_cli.py install-skill`。
2. `python gleaner_cli.py status` 检查本地配置。网络默认直连，不需要代理配置。
3. 普通版知网：填写真实的超级鹰账号、密码、软件 ID，运行 `python gleaner_cli.py score` 检查账号与积分。
4. 首次运行 `python login.py --first-run`；后续会话刷新运行 `python login.py`。两者均由脚本内部调用超级鹰。
5. 登录退出码为 0 且 `ok=true` 后，再 `status` 并开始采集。失败先读取实际错误，不循环重新创建会话。

## 知网

仅题录：`python gleaner_cli.py cnki-list --details --query "数字经济" --num 50 --out-name demo_metadata`。输出 11 列题录，不下载 PDF/CAJ，不使用 `--until`。

全文：先用 `prepare` 建式，再 `cnki-list --level L1 --search-md <path>` 查看命中数；用 `cnki --level L1 --search-md <path> --out-name <name> --until <目标>` 串行多批。普通版批间热启动登录失败就停止。L3/L4 需要用户明确同意。

校园网可直连。校外需要学校机构登录入口的用户，使用独立的 `gleanera` 机构版及其登录流程。

## Elsevier

先 `status` 确认 Key 配置，再运行 `python gleaner_cli.py els --query "digital innovation" --tier "1+2" --year-from 2015 --num 25`。

PDF 与 XML 分别保存；`downloaded_files` 为完整 PDF 篇数，`downloaded_xml` 单独统计。PDF 不可用时保留 XML，报告 `download_error`。空结果或部分失败返回 `ok=false`。

## 汇报

核对实际文件和摘要结果，报告输出目录、题录数、实际下载数、标题及日志。默认不增加长任务超时。密钥和登录 Cookie 仅保存在本机。
