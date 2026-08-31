# Gleaner 标准工作流

默认在 `GLEANER_ROOT` 下执行。本机还没注册 Skill 时先 `python gleaner_cli.py install-skill`。先 `status`，线 ready 再采。长任务读 `corpus/*_run.log`。

```powershell
$env:GLEANER_ROOT = "<本仓库绝对路径>"
$cli = "python `"$env:GLEANER_ROOT\gleaner_cli.py`""
# 或: pwsh ~/.grok/skills/gleaner/scripts/gleaner.ps1 <args>
```

---

## 1. CNKI（推荐分级）

**原则：先 list 看 TOTAL，再 collect 全文。L1 少则升 L2。**

### 步骤

1. **status**  
   `python gleaner_cli.py status`  
   确认代理 + 超级鹰（全文）+ **已有 cookies.json**。没有 cookie 先 `login-hint`，不要开 list/全文。

2. **概念组（Agent 完成，CLI 不做 LLM 拓展）**  
   按研究方向同义发散，分组 JSON：

   ```json
   [
     {"name": "供应链", "keywords": ["供应链", "供应链管理"]},
     {"name": "绿色转型", "keywords": ["绿色转型", "绿色供应链", "低碳"]}
   ]
   ```

3. **prepare** → 写出 `keyword_workspace/<topic>/` 与 L1–L4（含 `LY` 刊滤）

   ```powershell
   python gleaner_cli.py prepare `
     --topic "上市公司供应链绿色转型" `
     --concept-groups '[{"name":"供应链","keywords":["供应链"]},{"name":"绿色转型","keywords":["绿色转型","绿色供应链"]}]' `
     --year-from 2020 --year-to 2026
   ```

   或 `--concept-groups @C:\path\groups.json`。

4. **cnki-list（先看 TOTAL）**

   ```powershell
   python gleaner_cli.py cnki-list `
     --level L1 `
     --search-md "keyword_workspace/上市公司供应链绿色转型/2020_2026/search.md" `
     --num 100
   ```

5. **按 TOTAL 决策**  
   - 命中够用 → `cnki --level L1 ...`  
   - L1 很少且用户要更多 → **L2**（再 list，再 collect）  
   - L3/L4 仅在用户明确同意后使用（更宽、噪声更大）

6. **cnki 全文**

   ```powershell
   python gleaner_cli.py cnki `
     --level L1 `
     --search-md "keyword_workspace/上市公司供应链绿色转型/2020_2026/search.md" `
     --num 10
   ```

7. **汇报**  
   `corpus/<batch>/`、metadata 行数、PDF 数、标题、对应 `*_run.log`。

### 兼容（无分级）

```powershell
python gleaner_cli.py cnki-list --query "数字经济" --num 50
python gleaner_cli.py cnki --query "数字经济" --num 10
# 专业检索式: --pro --query 'SU%=数字经济 AND ...'
```

### Cookie

**首次装机必须先录 cookie**，再 `cnki-list` / `cnki`。无 `cookies.json` 冷启动下不了全文，只会空烧超级鹰。

仅第一次：`set ACQ_ALLOW_COLD_LOGIN=1` 后 `python login.py`。之后热启动，不要冷启动。失败时先 `python gleaner_cli.py login-hint`。无需个人知网账号。

---

## 2. Elsevier

**仅官方 Developer API**（禁止爬 sciencedirect 网页、禁止第三方 Key）。

1. **status** → `lines.elsevier.ready`  
   缺 Key：官方 https://dev.elsevier.com/apikey/manage ；写入 `ELSEVIER_API_KEY` 或 `acq/data/.elsevier_key`。  
   全文仍依赖机构订阅。

2. **els**

   ```powershell
   python gleaner_cli.py els `
     --query "supply chain green transition" `
     --tier "1+2" `
     --year-from 2015 `
     --num 25
   ```

3. **汇报**  
   `corpus/<batch>/` 下 md/xml 数量与路径；日志 `corpus/*_run.log`。

---

## 3. 国际（OA / NBER / SciHub / 可选 CARSI）

1. **status** → intl 一般公网即可；CARSI cookie 可选。  
2. **intl**

   ```powershell
   python gleaner_cli.py intl `
     --query "minimum wage employment" `
     --num 25 `
     --sources "oa,scihub"
   # 可加 year-from、issn、carsi 等
   ```

3. **汇报**  
   PDF 目录、篇数、标题、log。

---

## 通用约定

| 项 | 说明 |
|----|------|
| 超时 | 默认**无** 30 分钟硬杀；勿给 skill 默认加 `--timeout` |
| 日志 | `corpus/<name>_run.log` 行级 tee |
| 摘要 | 结束 JSON：`ok`、`local_dir`、`metadata_rows`、`downloaded_files`、`titles`、`log_path` |
| 0 篇 | `ok` 仍可为 true；用篇数判断是否放宽条件 |
| 密钥 | 永不回显（见 env.md） |
