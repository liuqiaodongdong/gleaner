# CNKI Search Scraper Design Spec

## Overview

基于 Playwright 的知网（CNKI）论文搜索爬虫，按关键词搜索论文，提取完整元数据并下载全文（优先 PDF，fallback CAJ）。通过校园网/VPN 使用机构下载权限。

## 需求

- 命令行指定关键词和数量：`python main.py <关键词> <数量>`
- 提取详情页完整元数据（标题、作者、摘要、关键词、DOI、基金、机构、引用/下载次数等）
- 下载全文：优先 PDF，无 PDF 则下载 CAJ
- 元数据保存为 CSV，全文保存为文件
- 不需要登录（校园网环境下直接可用）
- 为后续扩展预留接口（关键词拓展 skill、高级检索 skill）

## 技术选型

- **Playwright (Python, sync API)** — 模拟真实浏览器
- **stealth.min.js** — 反自动化检测（复用知乎项目）
- **同步顺序爬取** — 简单可靠

## 项目结构

```
0128#cnki_scraper/
├── main.py              # 入口，解析命令行参数，调度爬取和下载
├── config.py            # 配置（延时参数、输出路径等）
├── browser.py           # Playwright 浏览器管理（stealth）
├── scraper.py           # 搜索、翻页、详情页元数据提取
├── downloader.py        # 全文下载（优先 PDF，fallback CAJ）
├── libs/
│   └── stealth.min.js   # 反检测脚本（从知乎项目复用）
└── output/
    ├── metadata/        # 每个关键词一个 CSV
    └── papers/          # 按关键词分子目录存放全文
```

## 工作流程

### 1. 启动

```bash
python main.py 供应链 30
```

解析参数：关键词 = "供应链"，数量 = 30

### 2. 搜索与爬取

1. 打开知网搜索页 `https://kns.cnki.net/kns8s/search`
2. 在搜索框输入关键词，点击搜索
3. 遍历搜索结果页，逐条处理：
   - 从列表页提取基本信息（标题、作者、期刊、发表时间、引用/下载次数）
   - 点进详情页，提取完整元数据（摘要、关键词、DOI、基金项目、机构）
   - 调用 downloader 下载全文
   - 返回搜索结果页继续下一条
4. 达到指定数量后停止
5. 如果搜索结果不足指定数量，爬取所有可用结果

### 3. 全文下载

- 在详情页查找"PDF 下载"按钮，有则下载 PDF
- 无 PDF 按钮时查找"CAJ 下载"按钮，下载 CAJ
- 文件保存到 `output/papers/<关键词>/` 目录，文件名为 `<标题>.pdf` 或 `<标题>.caj`
- 文件名中的非法字符替换为下划线

### 4. 反爬策略

- 每次页面操作后随机延时 2-5 秒
- 详情页爬取后随机延时 3-8 秒
- 使用 stealth.min.js 隐藏自动化特征
- 模拟真实浏览器 viewport 和 User-Agent

### 5. 数据保存

元数据保存为 `output/metadata/<关键词>.csv`，字段如下：

| 字段 | 类型 | 说明 |
|------|------|------|
| keyword | str | 搜索关键词 |
| title | str | 论文标题 |
| authors | str | 作者（多个用分号分隔） |
| institution | str | 作者机构 |
| abstract | str | 摘要 |
| keywords | str | 关键词（多个用分号分隔） |
| journal | str | 期刊名 |
| pub_date | str | 发表时间 |
| doi | str | DOI |
| fund | str | 基金项目 |
| cite_count | str | 引用次数 |
| download_count | str | 下载次数 |
| url | str | 知网详情页链接 |
| file_path | str | 下载的全文文件相对路径 |
| file_type | str | PDF 或 CAJ |
| scraped_at | str | 爬取时间（ISO 格式） |

## 错误处理

- 详情页加载失败：重试 3 次，仍失败则跳过，元数据标记为不完整
- 全文下载失败：跳过，file_path 留空
- 搜索无结果：打印提示并退出
- 进度通过控制台打印，方便监控

## 依赖

- `playwright`
- Python 标准库：`csv`, `sys`, `time`, `random`, `datetime`, `pathlib`, `re`

## 扩展预留

命令行接口 `python main.py <关键词> <数量>` 作为基础入口，后续可通过 skill 扩展：
- 关键词拓展 skill：生成关键词列表，逐个调用此爬虫
- 高级检索 skill：构造高级检索条件，替换简单搜索部分
