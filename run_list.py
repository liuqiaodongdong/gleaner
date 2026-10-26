"""题录采集入口：默认只取列表页；details=true 补充详情字段，始终不下载全文。

供下游 find-leading-scholars 技能排"本土大佬"用 —— 排名只吃聚合的题录，不需要正文。
复用浏览器/登录/检索/翻页流程；默认跳过详情，details 模式只补充元数据。

params.json 字段（与 run_batch 同形）：
  keyword / topic   : 关键词模式
  pro=true + expression : 专业检索式模式（吃 cnki-advanced-search 技能的输出）
  num               : 目标篇数（=配额，CNKI 不封 IP）
  out               : 输出目录（产出 out/metadata.csv，无 papers/）
  details           : 补充摘要、关键词、机构和基金，输出 11 列

用法：python run_list.py params.json
"""
import os, sys, json, csv
from pathlib import Path

# 题录列只保留列表页能拿到的字段，顺序按下游约定
FIELDS = ["title", "authors", "journal", "pub_date", "cite_count", "download_count", "url"]
DETAIL_FIELDS = ["title", "authors", "abstract", "keywords", "journal", "pub_date",
                 "institution", "fund", "cite_count", "download_count", "url"]


def load_params(pf) -> dict:
    """读 UTF-8 JSON 参数，归一成 dict（避免命令行中文乱码）。"""
    p = json.loads(Path(pf).read_text(encoding="utf-8"))
    keyword = p.get("keyword") or p.get("topic") or ""
    pro = bool(p.get("pro"))
    return {
        "keyword": keyword,
        "pro": pro,
        "expression": p.get("expression", keyword),
        "num": int(p.get("num", 100)),
        "out": p.get("out", "out"),
        "details": bool(p.get("details", False)),
    }


def check_output_schema(out_dir, fields):
    """禁止缩减已有题录列，避免与全文批次共用目录时丢失下载信息。"""
    path = Path(out_dir) / "metadata.csv"
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as f:
            existing = csv.DictReader(f).fieldnames or []
        if set(existing) - set(fields):
            raise ValueError("已有 metadata.csv 包含本模式以外的列，请换一个 --out-name")


def save_csv(rows, out_dir, fields=None) -> Path:
    """写 metadata.csv（utf-8-sig，按 title 合并去重，原子替换）—— 同 run_batch 约定，仅列不同。"""
    fields = FIELDS if fields is None else fields
    out_dir = Path(out_dir)
    check_output_schema(out_dir, fields)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "metadata.csv"
    merged = {}
    if path.exists():
        with open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                merged[r.get("title", "")] = r
    for r in rows:
        merged[r.get("title", "")] = r
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(merged.values())
    tmp.replace(path)
    return path


def sort_by_citations(page, log=print) -> bool:
    """尽力把结果按"被引"降序排，方便大佬靠前；失败不报错（排名聚合全量，顺序不影响正确性）。

    # TODO 被引排序：CNKI 排序控件 DOM 未在本机联网核实，此处为尽力点击"被引"链接，
    # 若线上选择器不符会被 except 静默吞掉，仍按默认顺序采集，不影响最终排名。
    """
    try:
        for sel in ("li[data-order] a:has-text('被引')", "a:has-text('被引')",
                    ".sort-default a:has-text('被引')", "#orderCitedTime"):
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                page.wait_for_load_state("domcontentloaded")
                import time as _t
                _t.sleep(3)
                log("[list] 已切到被引降序排序")
                return True
        log("[list] 未找到被引排序控件，按默认顺序采集")
    except Exception as e:
        log(f"[list] 被引排序失败（忽略，按默认顺序）：{e}")
    return False


def harvest(page, num, extract_fn=None, next_fn=None, log=print,
            detail_fn=None, save_fn=None) -> list:
    """循环 extract_list_items + go_next_page，累积题录直到达 num 或没有下一页。

    extract_fn/next_fn 可注入（便于离线单测）；默认用 scraper 里的真实实现。
    按 title 去重，避免翻页重复项把配额吃空。
    """
    if extract_fn is None or next_fn is None:
        from scraper import extract_list_items, go_next_page  # 延迟导入，单测无需 playwright
        extract_fn = extract_fn or extract_list_items
        next_fn = next_fn or go_next_page

    records, seen = [], set()
    page_num = 1
    while len(records) < num:
        items = extract_fn(page)
        if not items:
            log("[list] 本页无结果，停止")
            break
        for it in items:
            title = it.get("title", "")
            if not title or title in seen:
                continue
            record = dict(it)
            if detail_fn is not None:
                # 详情失败时向上传播；已完成的记录由 save_fn 逐篇保存。
                detail = detail_fn(it)
                for key in ("abstract", "keywords", "institution", "fund"):
                    record[key] = detail.get(key, "")
            seen.add(title)
            fields = DETAIL_FIELDS if detail_fn is not None else FIELDS
            records.append({k: record.get(k, "") for k in fields})
            if save_fn is not None:
                save_fn(records)
            log(f"[list] {len(records)}/{num}  {title[:30]}")
            if len(records) >= num:
                break
        if len(records) >= num:
            break
        if not next_fn(page):
            log("[list] 无下一页")
            break
        page_num += 1
    return records


def collect_detail(context, item):
    """在独立页读取详情，始终关闭页面；此路径不导入或调用下载器。"""
    if not item.get("url"):
        raise ValueError(f"题录缺少详情 URL：{item.get('title', '')}")
    from scraper import extract_detail_metadata, _random_delay
    from config import DELAY_DETAIL

    dp = context.new_page()
    try:
        metadata = extract_detail_metadata(dp, item["url"], strict=True)
        _random_delay(DELAY_DETAIL)
        return metadata
    finally:
        dp.close()


def main():
    os.environ.setdefault("ACQ_HEADLESS", "1")
    os.environ.setdefault("ACQ_BROWSER_CHANNEL", "msedge")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pf = sys.argv[1] if len(sys.argv) > 1 else "list_params.json"
    p = load_params(pf)
    out_dir = Path(p["out"])
    if p["num"] <= 0:
        raise ValueError("num 必须大于 0")
    fields = DETAIL_FIELDS if p["details"] else FIELDS
    check_output_schema(out_dir, fields)
    q = p["expression"] if p["pro"] else p["keyword"]
    print(f"[list] mode={'pro' if p['pro'] else 'keyword'} q={q[:60]!r} num={p['num']} out={out_dir}")

    from browser import launch_browser, close_browser, save_cookies_after_captcha
    from scraper import search_keyword, search_professional, get_total_results

    pw, browser, context, page = launch_browser()
    records = []
    try:
        if p["pro"]:
            search_professional(page, p["expression"])
        else:
            search_keyword(page, p["keyword"])
        from acq.cnki_session import wait_for_institution_identity
        if not wait_for_institution_identity(page):
            raise RuntimeError("未确认学校机构身份；停止采集并保留会话，请运行 python login.py 登录。")
        save_cookies_after_captcha(context)
        total = get_total_results(page)
        print("[list] TOTAL=", total)
        target = min(p["num"], total) if total > 0 else p["num"]
        sort_by_citations(page)
        records = harvest(
            page, target,
            detail_fn=(lambda item: collect_detail(context, item)) if p["details"] else None,
            save_fn=lambda rows: save_csv(rows, out_dir, fields),
        )
        save_csv(records, out_dir, fields)
    finally:
        close_browser(pw, browser)
    print(f"[list] DONE collected={len(records)} out={out_dir}")


if __name__ == "__main__":
    main()
