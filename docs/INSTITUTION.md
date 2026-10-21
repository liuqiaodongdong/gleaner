# 官方校外机构登录旁路

代码分支为 `feature/cnki-institution-session`，使用独立 Git worktree。
主目录的 `main`、配置、cookies、文献和全局 Skill 指向不因运行本旁路而改变。
本目录使用自己的 `.env`、`.venv`、`cookies.json`、`acq/cookies/cnki/session.json` 及 `corpus/`。
不要将 Cookie、配置密钥或下载文献提交到 Git。

## 命令

在本 worktree 内运行：

```powershell
# 由用户选择学校并认证；程序成功后保存机构 cookies 及对应的会话标记
.\institution.ps1 login

# 查看本目录状态
.\institution.ps1 status

# 使用现有机构 cookies 下载一篇，不会在批次间重新录入
.\institution.ps1 download --pro --query "LY='中国工业经济'" --out-name institution_smoke --until 1

# 多批次示例：每批 1 篇，共 3 篇，仍然不自动重录
.\institution.ps1 download --pro --query "LY='中国工业经济'" --out-name institution_three --num 1 --until 3
```

显式调用 Python 时可使用 `gleaner_cli.py cnki --session-mode institution ...`。
默认 `--session-mode auto` 根据当前目录 `session.json` 的机构标记选择；只有缺少机构标记时才沿用 legacy 模式。
`login.py --institution` 自动生成标记并绑定 cookies 的 SHA-256；标记与文件不匹配时停止，不能悄悄改跑旧登录。
用户明确选择 `--session-mode legacy` 时保留旧的批间热启动行为。

## 机构模式下载规则

1. 不调用批间 `login.py`，仍按同一个 `--out-name` 和 `--until` 串行续传。
2. 下载子进程以机构模式运行，禁止把浏览器中的临时会话反写到 cookies.json；普通响应中的会话变化只保留在该浏览器内存中。
3. 检索后确认可见的机构身份；身份无法确认则停止，不自动录入。
4. 无新增全文、下载失败或标记失效时保留 cookies，报告未达目标；由用户主动运行 `institution.ps1 login`。
5. 验证码处理不等于重新登录，原有下载验证码逻辑保留。

`institution.ps1` 仅在执行期间设置进程环境，退出后还原。无需执行 `install-skill`，也不修改用户级环境变量。
本机首次建立 worktree 时复制了已成功验证的机构会话；此复制不改动主目录原文件。其他电脑应重新完成机构认证。
