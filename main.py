import csv
import re
import sys
import time
import random
from datetime import datetime
from pathlib import Path
from config import DELAY_PAGE, DELAY_DETAIL, PAPERS_DIR
from browser import launch_browser, close_browser, save_cookies_after_captcha
from scraper import (
    search_keyword, search_professional, get_total_results, extract_list_items,
    go_next_page, extract_detail_metadata, _random_delay, wait_for_captcha,
)
from downloader import download_paper, is_already_downloaded


CSV_FIELDS = [
    "batch",
    "title", "authors", "abstract", "keywords",
    "journal", "pub_date", "doi", "institution", "fund",
    "cite_count", "download_count", "url",
]


def _save_csv(all_results, out_dir, batch_name, journal_code, verbose=False):
    """增量写 metadata.csv 到 --out 目录内。原子写（先 .tmp 再 rename）。

    每篇下完都调一次，中途 Ctrl+C/kill 也保住已抓的元数据。
    """
    if not all_results or not out_dir:
        return
    csv_dir = out_dir
    csv_dir.mkdir(parents=True, exist_ok=True)
    csv_path = csv_dir / "metadata.csv"
    # 给本批所有条目打 batch 标
    for r in all_results:
        r["batch"] = batch_name
    # 读已有
    existing_by_title = {}
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_by_title[row.get("title", "").strip()] = row
    # 老条目缺 batch 时按 pub_date 年份回填
    for row in existing_by_title.values():
        if not row.get("batch", "").strip():
            m = re.match(r"(\d{4})", row.get("pub_date", "").strip())
            if m and journal_code:
                row["batch"] = f"{journal_code}_{m.group(1)}"
    n_new, n_updated = 0, 0
    for r in all_results:
        title = r.get("title", "").strip()
        if title in existing_by_title:
            old = existing_by_title[title]
            for k in CSV_FIELDS:
                new_val = r.get(k, "")
                if new_val and (isinstance(new_val, str) and new_val.strip()) and not old.get(k, "").strip():
                    old[k] = new_val
                    n_updated += 1
        else:
            existing_by_title[title] = r
            n_new += 1
    merged = list(existing_by_title.values())
    # 原子写
    tmp_path = csv_path.with_name(csv_path.name + ".tmp")
    with open(tmp_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(merged)
    tmp_path.replace(csv_path)
    if verbose:
        print(f"[main] metadata saved to {csv_path} ({n_new} new, {n_updated} fields updated, {len(merged)} total)")


def _read_expression(source: str) -> str:
    """Read a professional search expression from a file or use it directly as a string."""
    from pathlib import Path
    p = Path(source)
    if p.exists() and p.is_file():
        text = p.read_text(encoding="utf-8")
        # Extract expression from code block if it's a markdown file
        import re
        code_blocks = re.findall(r'```\n(.*?)\n```', text, re.DOTALL)
        if code_blocks:
            # Use the first code block (keyword expression without journal filter)
            return code_blocks[0].strip()
        return text.strip()
    return source


def _parse_named_arg(argv, name):
    """Extract --name value from argv, return (value, remaining_argv)."""
    if name not in argv:
        return None, argv
    idx = argv.index(name)
    value = argv[idx + 1]
    remaining = [a for i, a in enumerate(argv) if i != idx and i != idx + 1]
    return value, remaining


def _parse_date(s):
    """Parse date string like '2026-02-01' or '20260201'."""
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s}. Use YYYY-MM-DD or YYYYMMDD format.")


def _check_date_in_range(pub_date_str, date_from, date_to):
    """Check if pub_date string falls within [date_from, date_to]. Returns True if in range or unparseable."""
    if not pub_date_str or not pub_date_str.strip():
        return True  # no date info, don't skip
    # CNKI pub_date is typically "YYYY-MM-DD" or "YYYY-MM"
    cleaned = pub_date_str.strip().replace("/", "-")
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            d = datetime.strptime(cleaned, fmt).date()
            if date_from and d < date_from:
                return False
            if date_to and d > date_to:
                return False
            return True
        except ValueError:
            continue
    return True  # unparseable, don't skip


def main():
    # Parse arguments
    argv = list(sys.argv[1:])
    pro_mode = "--pro" in argv

    out_dir_str, argv = _parse_named_arg(argv, "--out")
    out_dir = Path(out_dir_str) if out_dir_str else None

    date_from_str, argv = _parse_named_arg(argv, "--date-from")
    date_to_str, argv = _parse_named_arg(argv, "--date-to")
    date_from = _parse_date(date_from_str) if date_from_str else None
    date_to = _parse_date(date_to_str) if date_to_str else None

    args = [a for a in argv if a != "--pro"]

    if pro_mode:
        if len(args) != 2:
            print("Usage: python main.py --pro <expression_or_file> <num> [--out <dir>] [--date-from YYYY-MM-DD] [--date-to YYYY-MM-DD]")
            print('Example: python main.py --pro "SU %=\'供应链\'" 30 --date-from 2026-02-01 --date-to 2026-04-01')
            print("Example: python main.py --pro search.md 30 --out pdf --date-from 2026-02-01 --date-to 2026-04-01")
            sys.exit(1)
        expression = _read_expression(args[0])
        num = int(args[1])
        keyword = "professional_search"
        print(f"[main] professional search, target={num} papers")
        print(f"[main] expression: {expression[:100]}...")
    else:
        if len(args) != 2:
            print("Usage: python main.py <keyword> <num> [--out <dir>] [--date-from YYYY-MM-DD] [--date-to YYYY-MM-DD]")
            print("       python main.py --pro <expression_or_file> <num> [--out <dir>] [--date-from YYYY-MM-DD] [--date-to YYYY-MM-DD]")
            print("Example: python main.py 供应链 30")
            sys.exit(1)
        keyword = args[0]
        num = int(args[1])
        print(f"[main] keyword='{keyword}', target={num} papers")

    if out_dir:
        print(f"[main] output dir: {out_dir}")
    if date_from or date_to:
        print(f"[main] date filter: {date_from or '...'} ~ {date_to or '...'}")

    # 批次名 = <期刊代码>_<年份>，从 --out 路径推导
    journal_code = out_dir.parent.name if out_dir else ""
    batch_name = f"{journal_code}_{out_dir.name}" if out_dir else ""

    pw, browser, context, page = launch_browser()
    all_results = []

    try:
        if pro_mode:
            search_professional(page, expression)
        else:
            search_keyword(page, keyword)
        # Save cookies after passing any CAPTCHA
        save_cookies_after_captcha(context)
        total = get_total_results(page)
        print(f"[main] total results available: {total}")
        target = min(num, total) if total > 0 else num

        page_num = 1
        while len(all_results) < target:
            print(f"\n[main] --- page {page_num}, collected {len(all_results)}/{target} ---")

            items = extract_list_items(page)
            print(f"[main] found {len(items)} items on page {page_num}")

            if not items:
                print("[main] no items found, stopping")
                break

            for i, item in enumerate(items):
                if len(all_results) >= target:
                    break

                if not item["url"]:
                    continue

                # Date filter: skip papers outside the specified range
                if date_from or date_to:
                    if not _check_date_in_range(item.get("pub_date", ""), date_from, date_to):
                        print(f"  [skip] {item['title'][:40]}... (date: {item.get('pub_date', '?')})")
                        continue

                already_downloaded = is_already_downloaded(item["title"], out_dir)

                print(f"\n  [{len(all_results)+1}/{target}] {item['title'][:50]}...")

                # Open detail page in a NEW TAB to preserve search results
                detail_page = context.new_page()
                try:
                    detail = extract_detail_metadata(detail_page, item["url"])
                    item.update(detail)
                    _random_delay(DELAY_DETAIL)

                    # Download full text (skip if already downloaded)
                    if already_downloaded:
                        print(f"  [skip] already downloaded")
                    else:
                        file_path, file_type = download_paper(detail_page, item["title"], out_dir)
                        item["file_path"] = file_path
                        item["file_type"] = file_type
                finally:
                    detail_page.close()

                all_results.append(item)
                # 增量写 CSV — 每篇都落盘，中途中断也保住元数据
                _save_csv(all_results, out_dir, batch_name, journal_code)
                _random_delay(DELAY_PAGE)

            if len(all_results) >= target:
                break

            # Next page
            if not go_next_page(page):
                print("[main] no more pages")
                break
            page_num += 1
            _random_delay(DELAY_PAGE)

        print(f"\n[main] collected {len(all_results)} papers")

    except KeyboardInterrupt:
        print(f"\n[main] interrupted by user, collected {len(all_results)} papers")
    finally:
        close_browser(pw, browser)

    # 末尾再写一次（带 verbose 输出汇总，每篇下完已经增量写过）
    _save_csv(all_results, out_dir, batch_name, journal_code, verbose=True)

    print("[main] done")


if __name__ == "__main__":
    main()
