# Gleanera 机构版工作规则

本分支是 `feature/cnki-institution-session`，产品及技能名 `gleanera`。适用于校外且学校支持 CNKI 机构认证的用户。只提供知网，不提供国际线或 Elsevier。

## 安装与目录隔离

新安装克隆本分支到独立目录，安装 requirements.txt 后执行 `python gleanera_cli.py install-skill`。技能注册到 `skills/gleanera`，不覆盖普通版 `skills/gleaner`。使用 `GLEANERA_ROOT`、`GLEANERA_PYTHON` 和 `.gleanera_root`；不依赖普通版环境变量。

## 网络和登录

默认直连，系统 VPN 路由仍生效。ACQ_PROXY 是可选代理，仅在用户明确需要时配置；PORT 必须换成真实数字端口，不自动读取系统代理。

先 `status`。机构会话缺失或失效时运行 `python login.py`，用户在可见浏览器完成学校认证。确认知网的机构名称后才保存 Cookie 和本地校验标记；失败保留原会话。

首次机构认证不依赖超级鹰。采集中的超级鹰服务为可选配置，可用 `python gleanera_cli.py score` 验证。模板占位值不是有效凭据。

## 采集

机构会话只在用户主动登录时更新；采集期间和批间不覆盖或自动重录 Cookie。身份未确认、会话失效、无新增结果时停止并给出原因。不能以 Cookie 文件存在代替实际机构身份确认。

题录用 `cnki-list`，完整题录加 `--details`，输出 11 列，不下载全文，不用 `--until`。全文先列表再用同一 `--out-name` 和 `--until <目标>` 串行多批；不并行浏览器。分级 L1 不够可升 L2，L3/L4 需用户同意。

长任务用 CLI，读取运行日志，不擅自设置固定超时。完成时核对实际文件，报告题录数、下载数、输出目录和失败原因。

## 数据与发布

凭据、Cookie、会话标记、历史文献保留在本目录，不回显、不提交。代码测试用 `python -m pytest -q`。推送遵循用户授权，只更新当前机构分支。
