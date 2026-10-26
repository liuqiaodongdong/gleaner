---
name: gleanera
description: >
  Gleanera 知网校外机构版。用于不在校园网且学校支持 CNKI 机构登录的情况。
  首次 python login.py 打开学校机构认证，由用户在浏览器完成登录。
  默认直连、代理可选，复用有效机构会话；仅采集 CNKI。
---

# Gleanera

适用于校外且学校支持 https://fsso.cnki.net/ 机构认证的情况。只提供知网题录、摘要和有权限的全文下载，与普通版 `gleaner` 分别安装。

## 安装

先克隆完整机构分支，安装依赖，再注册技能：

```powershell
git clone --branch feature/cnki-institution-session --single-branch https://github.com/liuqiaodongdong/gleaner.git gleanera
cd gleanera
python -m pip install -r requirements.txt
python gleanera_cli.py install-skill
python gleanera_cli.py status
```

入口 `gleanera_cli.py`；独立环境变量 `GLEANERA_ROOT` / `GLEANERA_PYTHON`，技能指针 `.gleanera_root`。CLI `--root` 优先。普通版的根目录配置不参与机构版定位。注册到 `skills/gleanera`，不会覆盖 `skills/gleaner`。

## 登录与网络

默认直连，不读取系统代理；校园 VPN 的系统路由仍生效。ACQ_PROXY 可选，仅用户确实需要代理时设置实际地址和数字端口。PORT 是占位符，不能照抄为有效配置。

机构会话未就绪时运行 `python login.py`，让用户在可见浏览器选择学校并完成身份认证。脚本确认机构身份后保存会话。无需冷启动开关；首次学校认证不依赖超级鹰，采集验证码可选配置 CJY_*。

采集期间及批间不自动重新登录，不覆盖 Cookie。会话失效、机构身份未确认或无进展时停止，提示用户主动运行登录脚本。`status` 只检查本地会话与标记一致；实际可用性通过页面访问确认。

## 采集与汇报

先 `status`，再 `cnki-list` 看命中数。仅需题录或摘要时使用 `cnki-list --details --num N --out-name <题录批次>`，输出 11 列，不下载全文。省略 --details 时只采列表字段。

全文使用 `cnki --out-name <固定名> --until <目标>` 串行多批；不要一次拉满或并行浏览器。支持 `prepare` 概念组与 L1–L4；升 L3/L4 需用户明确同意。

长任务用 CLI，不擅自设固定超时；看 `corpus/*_run.log`。核对实际文件、`until_reached` 和下载数再报告完成。凭据和 Cookie 不回显、不提交。

详见 [环境配置](references/env.md) 与 [工作流](references/workflows.md)。
