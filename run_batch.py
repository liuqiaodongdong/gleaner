"""批量采集入口：从 UTF-8 JSON 读参数（避免命令行中文乱码，供 gleaner_cli 调用）。

params.json 字段：
  keyword / topic   : 关键词模式
  pro=true + expression : 专业检索式模式（吃 cnki-advanced-search 技能的输出）
  num               : 目标篇数（=配额，高低由调用方定，CNKI 不封 IP）
  out               : 输出目录（产出 out/metadata.csv + out/papers/*.pdf）

用法：python run_batch.py params.json
"""
import os, sys, json, csv
os.environ.setdefault("ACQ_HEADLESS", "1")
os.environ.setdefault("ACQ_BROWSER_CHANNEL", "msedge")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
from browser import launch_browser, close_browser, save_cookies_after_captcha
from scraper import (search_keyword, search_professional, get_total_results,
                     extract_list_items, go_next_page, extract_detail_metadata, _random_delay)
from downloader import download_paper, is_already_downloaded
from config import DELAY_PAGE, DELAY_DETAIL

FIELDS = ["title", "authors", "abstract", "keywords", "journal", "pub_date", "doi",
          "institution", "fund", "cite_count", "download_count", "url", "file_path", "file_type"]

import os as _os
# 连续失败熔断：撞墙(拼图校验)即快速退出本轮，交给外层重启轮转续跑；可用环境变量覆盖
MAX_CONSEC_FAIL = int(_os.environ.get("ACQ_MAX_CONSEC_FAIL", "5"))


def save_csv(rows, out_dir: Path):
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
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(merged.values())
    tmp.replace(path)


def main():
    pf = sys.argv[1] if len(sys.argv) > 1 else "batch_params.json"
    p = json.loads(Path(pf).read_text(encoding="utf-8"))
    keyword = p.get("keyword") or p.get("topic") or ""
    num = int(p.get("num", 20))
    out_dir = Path(p.get("out", "out"))
    pro = bool(p.get("pro"))
    expression = p.get("expression", keyword)
    papers_dir = out_dir / "papers"
    print(f"[batch] mode={'pro' if pro else 'keyword'} q={(expression if pro else keyword)[:60]!r} num={num} out={out_dir}")

    pw, browser, context, page = launch_browser()
    results = []
    consec_fail = 0
    try:
        if pro:
            search_professional(page, expression)
        else:
            search_keyword(page, keyword)
        save_cookies_after_captcha(context)
        total = get_total_results(page)
        print("[batch] TOTAL=", total)
        target = min(num, total) if total > 0 else num
        page_num = 1
        while len(results) < target and consec_fail < MAX_CONSEC_FAIL:
            items = extract_list_items(page)
            if not items:
                print("[batch] 无结果，停止")
                break
            for it in items:
                if len(results) >= target or consec_fail >= MAX_CONSEC_FAIL:
                    break
                if not it.get("url"):
                    continue
                # 续传：已下载的直接跳过，避免重复进详情页、减少无谓验证码
                if is_already_downloaded(it["title"], papers_dir):
                    print(f"[batch] skip 已下: {it['title'][:30]}")
                    continue
                dp = context.new_page()
                try:
                    it.update(extract_detail_metadata(dp, it["url"]))
                    _random_delay(DELAY_DETAIL)
                    fp, ft = download_paper(dp, it["title"], papers_dir)
                    it["file_path"], it["file_type"] = fp, ft
                    consec_fail = 0 if fp else consec_fail + 1
                    results.append(it)
                    save_csv(results, out_dir)
                    print(f"[batch] {len(results)}/{target}  {it['title'][:30]}  -> {ft or 'FAIL'}")
                except Exception as e:
                    consec_fail += 1
                    print(f"[batch] item err ({consec_fail}): {e}")
                finally:
                    dp.close()
                _random_delay(DELAY_PAGE)
            if len(results) >= target or consec_fail >= MAX_CONSEC_FAIL:
                break
            if not go_next_page(page):
                print("[batch] 无下一页")
                break
            page_num += 1
        save_csv(results, out_dir)
        if consec_fail >= MAX_CONSEC_FAIL:
            print("[batch] 连续失败熔断")
    finally:
        close_browser(pw, browser)
    print(f"[batch] DONE collected={len(results)} out={out_dir}")


main()
