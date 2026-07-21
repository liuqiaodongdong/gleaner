"""
CNKI MCP Server - 知网学术搜索 MCP 服务
提供 search_cnki tool，供 Claude Code 在写作时检索真实文献。

Tool:
    search_cnki(query, limit=5) → 返回文献元数据列表（含摘要）
"""
import sys
import os
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

# 确保能导入同目录下的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cnki-search")

# 同步代码专用线程池（Playwright sync API 不能在 asyncio 线程跑）
_executor = ThreadPoolExecutor(max_workers=1)

# 全局浏览器实例（懒启动，只在 worker 线程中访问）
_browser_state = {
    "pw": None,
    "browser": None,
    "context": None,
    "page": None,
}


def _ensure_browser():
    """懒启动浏览器，后续调用复用同一实例。只在 worker 线程中调用。"""
    if _browser_state["page"] is not None:
        try:
            _browser_state["page"].title()
            return _browser_state["page"], _browser_state["context"]
        except Exception:
            _cleanup_browser()

    from browser import launch_browser
    pw, browser, context, page = launch_browser()
    _browser_state.update(pw=pw, browser=browser, context=context, page=page)
    return page, context


def _cleanup_browser():
    try:
        if _browser_state["browser"]:
            _browser_state["browser"].close()
        if _browser_state["pw"]:
            _browser_state["pw"].stop()
    except Exception:
        pass
    _browser_state.update(pw=None, browser=None, context=None, page=None)


def _sync_search(query: str, limit: int) -> str:
    """同步搜索逻辑，在 worker 线程中执行。"""
    from scraper import (
        search_keyword, extract_list_items, extract_detail_metadata,
        _random_delay,
    )
    from browser import save_cookies_after_captcha
    from config import DELAY_DETAIL

    page, context = _ensure_browser()

    # 搜索
    search_keyword(page, query)
    save_cookies_after_captcha(context)

    # 提取列表页结果
    items = extract_list_items(page)
    if not items:
        return json.dumps({"results": [], "message": f"未找到'{query}'相关文献"}, ensure_ascii=False)

    items = items[:limit]

    # 逐条打开详情页提取摘要
    results = []
    for i, item in enumerate(items):
        if not item.get("url"):
            continue

        detail_page = context.new_page()
        try:
            detail = extract_detail_metadata(detail_page, item["url"])
            item.update(detail)
            if i < len(items) - 1:
                _random_delay(DELAY_DETAIL)
        except Exception as e:
            logging.warning(f"详情页提取失败: {item.get('title', '?')}: {e}")
        finally:
            detail_page.close()

        results.append({
            "title": item.get("title", ""),
            "authors": item.get("authors", ""),
            "journal": item.get("journal", ""),
            "pub_date": item.get("pub_date", ""),
            "abstract": item.get("abstract", ""),
            "keywords": item.get("keywords", ""),
            "doi": item.get("doi", ""),
            "cite_count": item.get("cite_count", "0"),
            "url": item.get("url", ""),
        })

    return json.dumps({
        "query": query,
        "total": len(results),
        "results": results,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def search_cnki(query: str, limit: int = 5) -> str:
    """搜索知网(CNKI)学术文献，返回含摘要的元数据列表。

    用于论文写作时检索真实文献，确保引用的文献真实存在。
    返回 JSON 格式的文献列表，每条包含：title, authors, journal, pub_date,
    abstract, keywords, doi, cite_count, url。

    Args:
        query: 搜索关键词，如"沉浸式体验设计"、"供应链数字化"
        limit: 返回文献数量上限，默认5条
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _sync_search, query, limit)


if __name__ == "__main__":
    import atexit
    atexit.register(_cleanup_browser)
    mcp.run(transport="stdio")
