# Elsevier 官方 API Key 申请指南

本项目的 `els_collect` **只使用 Elsevier 官方 Developer API**（ScienceDirect Search + Article Retrieval），**不需要**爬 ScienceDirect 网页、不需要账号密码登录浏览器、也不要用第三方「Elsevier 破解 / 镜像」之类说法。

官方入口（请以官网为准）：

- Developer Portal：https://dev.elsevier.com/
- 管理 / 创建 API Key：https://dev.elsevier.com/apikey/manage
- 默认配额说明：https://dev.elsevier.com/api_key_settings.html

---

## 申请步骤（给用户 / Agent 照做）

### 1. 注册 Elsevier 账号

1. 打开 https://account.elsevier.com/ （或从 dev.elsevier.com 点登录/注册）。
2. **建议使用学校/机构邮箱**注册（学术机构用户对多数 Research Products API 有免费额度；Scival / Embase 等例外，本项目不用它们）。
3. 若你已有 ScienceDirect / Scopus 账号，可直接用同一账号登录 Developer Portal。

### 2. 登录 Developer Portal 并创建 Key

1. 打开 https://dev.elsevier.com/
2. 登录后进入 **My API Key** / [I want an API Key](https://dev.elsevier.com/apikey/manage)
3. 点击 **Create API Key**
4. 填写：
   - **Label**：任意备注名，如 `gleaner-local`
   - **Website URL**：个人本地使用可填 `http://localhost` 或按页面要求填写（部分说明允许用占位；以页面校验为准）
5. 创建成功后复制 **API Key**（一长串字符）

### 3. 配置到本项目（二选一，勿提交到 git）

**方式 A（推荐）—— MCP 环境变量**

在 Claude Code 等客户端的 `mcpServers.gleaner.env` 中：

```json
"ELSEVIER_API_KEY": "粘贴你的API_Key"
```

**方式 B——本机文件**

在项目目录创建文件（单行、无多余空格/换行杂讯）：

```text
acq/data/.elsevier_key
```

内容仅为 key 本身一行。该路径已在 `.gitignore` 中。

配置后请用户（或 Agent）再调一次 MCP 工具 **`setup_status`**，确认 `lines.elsevier.ready == true`。

---

## 本项目实际用到哪些 API

| 用途 | 接口 | 说明 |
|------|------|------|
| 检索 | ScienceDirect Search API V2 | `PUT https://api.elsevier.com/content/search/sciencedirect` |
| 全文 | Article Retrieval | `GET .../content/article/doi/{doi}?view=FULL`，取 XML 再转 Markdown |

请求头使用官方方式：`X-ELS-APIKey: <your_key>`（见 `acq/sources/els.py`）。

---

## 权限与预期（避免误导用户）

1. **API Key ≠ 自动拥有全库 PDF**  
   - Key 主要用于调用官方 API、遵守配额。  
   - **订阅全文**通常还依赖机构订阅权益；学校未订的刊/五大顶刊等可能只有题录或拿不到全文 XML。  
   - 本项目对订阅文章走 **全文 XML → MD**（实测部分 PDF 端点仅封面预览）。

2. **不要让用户去**  
   - 购买来路不明的「Elsevier API」  
   - 用浏览器自动化硬爬 `sciencedirect.com` 当官方 API 用  
   - 把 Key 写进公开仓库或发给陌生人  

3. **配额**  
   - 免费学术 Key 有周请求上限与 QPS 限制，详见  
     https://dev.elsevier.com/api_key_settings.html  
   - 大批次请控制 `num` / `per_journal`，避免打满配额。

4. **合规**  
   - 遵守 Elsevier API 使用条款与机构订阅协议，仅限合法科研/学习用途。

---

## Agent 话术模板（缺 Key 时）

请直接引导用户，勿编造其他申请渠道：

> 要用 Elsevier 线，请申请**官方** API Key：  
> 1. 用学校邮箱在 https://dev.elsevier.com/ 登录/注册  
> 2. 打开 https://dev.elsevier.com/apikey/manage → Create API Key  
> 3. 把 Key 填进 MCP 的 `ELSEVIER_API_KEY`，或写入 `acq/data/.elsevier_key`  
> 4. 再运行 `setup_status` 确认就绪  
> 详细步骤见项目 `docs/ELSEVIER_API.md`。
