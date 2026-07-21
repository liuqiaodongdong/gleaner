# CNKI Search Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Playwright-based CNKI scraper that searches by keyword, extracts paper metadata from detail pages, and downloads full-text files (PDF preferred, CAJ fallback).

**Architecture:** Sequential scraper — command-line driven (`python main.py <keyword> <num>`). Browser with stealth.min.js anti-detection. Search → list page → detail page → download, one paper at a time. Metadata saved as CSV, papers saved as files.

**Tech Stack:** Python, Playwright (sync API), stealth.min.js

---

## File Structure

| File | Responsibility |
|------|---------------|
| `config.py` | Configuration constants (delays, paths, URLs) |
| `browser.py` | Playwright browser launch with stealth |
| `scraper.py` | Search, paginate, extract list items, extract detail page metadata |
| `downloader.py` | Download full-text PDF/CAJ from detail page |
| `main.py` | Entry point — parse args, orchestrate scrape + download, write CSV |
| `libs/stealth.min.js` | Anti-detection script (copied from zhihu project) |

---

### Task 1: config.py + project skeleton

**Files:**
- Create: `config.py`
- Create: `libs/stealth.min.js` (copy)

- [ ] **Step 1: Create config.py**

```python
from pathlib import Path

# Project paths
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
METADATA_DIR = OUTPUT_DIR / "metadata"
PAPERS_DIR = OUTPUT_DIR / "papers"

# Scraping parameters
DELAY_PAGE = (2, 5)       # seconds, random range between page actions
DELAY_DETAIL = (3, 8)     # seconds, random range after detail page
MAX_RETRIES = 3           # network retry count

# CNKI URLs
CNKI_SEARCH_URL = "https://kns.cnki.net/kns8s/defaultresult/index"
```

- [ ] **Step 2: Copy stealth.min.js from zhihu project**

```bash
mkdir -p libs
cp "C:/Users/laidh/Desktop/01#项目/0127#zhihu_scraper/libs/stealth.min.js" libs/stealth.min.js
```

- [ ] **Step 3: Create output directories**

```bash
mkdir -p output/metadata output/papers
touch output/.gitkeep output/metadata/.gitkeep output/papers/.gitkeep
```

- [ ] **Step 4: Commit**

```bash
git add config.py libs/stealth.min.js output/.gitkeep output/metadata/.gitkeep output/papers/.gitkeep
git commit -m "feat: add config and project skeleton"
```

---

### Task 2: browser.py — Browser with stealth

**Files:**
- Create: `browser.py`

- [ ] **Step 1: Create browser.py**

```python
import time
from playwright.sync_api import sync_playwright


def launch_browser():
    """Launch Playwright browser with stealth and return (pw, browser, page)."""
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--exclude-switches=enable-automation",
            "--disable-infobars",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-maximized",
        ],
    )
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        accept_downloads=True,
    )
    context.add_init_script(path="libs/stealth.min.js")
    page = context.new_page()
    return pw, browser, page


def close_browser(pw, browser) -> None:
    browser.close()
    pw.stop()
```

- [ ] **Step 2: Verify import**

```bash
cd "C:/Users/laidh/Desktop/01#项目/0128#cnki_scraper"
python -c "from browser import launch_browser; print('import ok')"
```

Expected: `import ok`

- [ ] **Step 3: Commit**

```bash
git add browser.py
git commit -m "feat: add browser management with stealth"
```

---

### Task 3: scraper.py — Search, paginate, extract metadata

**Files:**
- Create: `scraper.py`

- [ ] **Step 1: Create scraper.py**

```python
import re
import time
import random
from playwright.sync_api import Page
from config import CNKI_SEARCH_URL, DELAY_PAGE, DELAY_DETAIL, MAX_RETRIES


def _random_delay(delay_range: tuple) -> None:
    delay = random.uniform(*delay_range)
    print(f"  [delay] waiting {delay:.1f}s...")
    time.sleep(delay)


def search_keyword(page: Page, keyword: str) -> None:
    """Navigate to CNKI and perform a keyword search."""
    page.goto(CNKI_SEARCH_URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)

    # Find search input and type keyword
    search_input = page.query_selector("input.search-input, input#txt_SearchText")
    if not search_input:
        raise RuntimeError("Cannot find CNKI search input")
    search_input.click()
    search_input.fill(keyword)
    _random_delay((1, 2))

    # Click search button
    search_btn = page.query_selector("input.search-btn, button.search-btn, .btn-search")
    if search_btn:
        search_btn.click()
    else:
        search_input.press("Enter")

    page.wait_for_load_state("domcontentloaded")
    time.sleep(3)
    print(f"[search] searched for '{keyword}'")


def get_total_results(page: Page) -> int:
    """Get total number of search results from the result page."""
    count_el = page.query_selector(".pagerTitleCell em, .result-count")
    if count_el:
        text = count_el.inner_text().strip().replace(",", "")
        match = re.search(r'\d+', text)
        if match:
            return int(match.group())
    return 0


def extract_list_items(page: Page) -> list[dict]:
    """Extract basic info from search result list page.

    Returns list of dicts with keys: title, url, authors, journal, pub_date,
    cite_count, download_count.
    """
    results = []
    rows = page.query_selector_all("table.result-table-list tbody tr, .result-table-list tr")

    for row in rows:
        try:
            # Title and URL
            title_el = row.query_selector("td.name a.fz14, a.fz14")
            if not title_el:
                continue
            title = title_el.inner_text().strip()
            url = title_el.get_attribute("href") or ""
            if url and url.startswith("/"):
                url = "https://kns.cnki.net" + url

            # Authors
            author_el = row.query_selector("td.author, .author")
            authors = author_el.inner_text().strip() if author_el else ""

            # Journal/Source
            source_el = row.query_selector("td.source a, .source a")
            journal = source_el.inner_text().strip() if source_el else ""

            # Date
            date_el = row.query_selector("td.date, .date")
            pub_date = date_el.inner_text().strip() if date_el else ""

            # Cite count
            cite_el = row.query_selector("td.quote, .quote")
            cite_count = cite_el.inner_text().strip() if cite_el else "0"

            # Download count
            dl_el = row.query_selector("td.download, .download")
            download_count = dl_el.inner_text().strip() if dl_el else "0"

            results.append({
                "title": title,
                "url": url,
                "authors": authors,
                "journal": journal,
                "pub_date": pub_date,
                "cite_count": cite_count,
                "download_count": download_count,
            })
        except Exception as e:
            print(f"  [warn] failed to extract row: {e}")
            continue

    return results


def go_next_page(page: Page) -> bool:
    """Click next page button. Returns True if successful, False if no more pages."""
    next_btn = page.query_selector("#PageNext, a#PageNext")
    if not next_btn:
        return False
    # Check if disabled
    cls = next_btn.get_attribute("class") or ""
    if "disabled" in cls or "noclick" in cls:
        return False
    next_btn.click()
    page.wait_for_load_state("domcontentloaded")
    time.sleep(3)
    return True


def extract_detail_metadata(page: Page, url: str) -> dict:
    """Navigate to detail page and extract full metadata.

    Returns dict with keys: abstract, keywords, doi, fund, institution.
    """
    for attempt in range(MAX_RETRIES):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            # Abstract
            abstract_el = page.query_selector("#ChDivSummary, .abstract-text, [id*='ChDivSummary']")
            abstract = abstract_el.inner_text().strip() if abstract_el else ""

            # Keywords
            kw_els = page.query_selector_all("p.keywords a, .keywords a")
            keywords = ";".join(el.inner_text().strip().rstrip(";；") for el in kw_els if el.inner_text().strip())

            # DOI
            doi = ""
            doi_el = page.query_selector("[id*='DOI'] a, .doi a, .top-tip span:-soup-contains('DOI') + span")
            if doi_el:
                doi = doi_el.inner_text().strip()
            else:
                # Try finding DOI in the metadata section
                all_labels = page.query_selector_all(".top-tip span, .doc-info span")
                for i, label in enumerate(all_labels):
                    if "DOI" in (label.inner_text() or ""):
                        # Next sibling or next element might have the value
                        doi_val = page.query_selector(f".top-tip a, .doc-info a")
                        if doi_val:
                            doi = doi_val.inner_text().strip()
                        break

            # Fund / 基金
            fund_els = page.query_selector_all("p.funds a, .funds a, [class*='fund'] a")
            fund = ";".join(el.inner_text().strip().rstrip(";；") for el in fund_els if el.inner_text().strip())

            # Institution / 机构
            inst_els = page.query_selector_all("a[href*='organ'], .orgn a, h3.author + div a, .author-info .orgn span")
            institution = ";".join(el.inner_text().strip().rstrip(";；") for el in inst_els if el.inner_text().strip())

            return {
                "abstract": abstract,
                "keywords": keywords,
                "doi": doi,
                "fund": fund,
                "institution": institution,
            }
        except Exception as e:
            print(f"  [warn] detail page attempt {attempt + 1} failed: {e}")
            _random_delay((2, 3))

    print(f"  [error] giving up on {url}")
    return {"abstract": "", "keywords": "", "doi": "", "fund": "", "institution": ""}
```

- [ ] **Step 2: Verify import**

```bash
python -c "from scraper import search_keyword, extract_list_items, extract_detail_metadata, go_next_page; print('import ok')"
```

Expected: `import ok`

- [ ] **Step 3: Commit**

```bash
git add scraper.py
git commit -m "feat: add search, pagination, and metadata extraction"
```

---

### Task 4: downloader.py — Full-text download

**Files:**
- Create: `downloader.py`

- [ ] **Step 1: Create downloader.py**

```python
import re
import time
from pathlib import Path
from playwright.sync_api import Page
from config import PAPERS_DIR


def _sanitize_filename(name: str) -> str:
    """Replace illegal filename characters with underscore."""
    return re.sub(r'[\\/*?:"<>|\n\r\t]', '_', name).strip()[:100]


def download_paper(page: Page, keyword: str, title: str) -> tuple[str, str]:
    """Download full-text from the current detail page.

    Tries PDF first, falls back to CAJ.
    Returns (file_path, file_type) or ("", "") if download fails.
    """
    save_dir = PAPERS_DIR / _sanitize_filename(keyword)
    save_dir.mkdir(parents=True, exist_ok=True)
    safe_title = _sanitize_filename(title)

    # Try PDF download first
    pdf_btn = page.query_selector(
        "a#pdfDown, a.btn-dlpdf, a[id*='pdfDown'], "
        ".btn-dlpdf a, a[href*='pdfdown'], a[onclick*='pdf']"
    )
    if pdf_btn:
        result = _do_download(page, pdf_btn, save_dir, safe_title, "pdf")
        if result:
            return result

    # Fallback to CAJ
    caj_btn = page.query_selector(
        "a#cajDown, a.btn-dlcaj, a[id*='cajDown'], "
        ".btn-dlcaj a, a[href*='cajdown']"
    )
    if caj_btn:
        result = _do_download(page, caj_btn, save_dir, safe_title, "caj")
        if result:
            return result

    print(f"  [download] no download button found for: {title[:40]}")
    return ("", "")


def _do_download(page: Page, btn, save_dir: Path, safe_title: str, ext: str) -> tuple[str, str] | None:
    """Click download button and save the file."""
    try:
        with page.expect_download(timeout=60000) as download_info:
            btn.click()
        download = download_info.value
        file_path = save_dir / f"{safe_title}.{ext}"
        download.save_as(str(file_path))
        rel_path = str(file_path.relative_to(file_path.parents[3]))  # relative to project root
        print(f"  [download] saved {ext.upper()}: {file_path.name}")
        return (rel_path, ext.upper())
    except Exception as e:
        print(f"  [download] {ext.upper()} download failed: {e}")
        return None
```

- [ ] **Step 2: Verify import**

```bash
python -c "from downloader import download_paper; print('import ok')"
```

Expected: `import ok`

- [ ] **Step 3: Commit**

```bash
git add downloader.py
git commit -m "feat: add full-text PDF/CAJ downloader"
```

---

### Task 5: main.py — Entry point and CSV output

**Files:**
- Create: `main.py`

- [ ] **Step 1: Create main.py**

```python
import csv
import sys
import time
import random
from datetime import datetime
from config import METADATA_DIR, DELAY_PAGE, DELAY_DETAIL
from browser import launch_browser, close_browser
from scraper import (
    search_keyword, get_total_results, extract_list_items,
    go_next_page, extract_detail_metadata, _random_delay,
)
from downloader import download_paper


CSV_FIELDS = [
    "keyword", "title", "authors", "institution", "abstract", "keywords",
    "journal", "pub_date", "doi", "fund", "cite_count", "download_count",
    "url", "file_path", "file_type", "scraped_at",
]


def save_results(keyword: str, results: list[dict]) -> None:
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = keyword.replace("/", "_").replace("\\", "_").replace(" ", "_")
    filepath = METADATA_DIR / f"{safe_name}.csv"

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        now = datetime.now().isoformat()
        for item in results:
            item["keyword"] = keyword
            item["scraped_at"] = now
            writer.writerow(item)

    print(f"\n[save] {len(results)} results saved to {filepath}")


def main():
    if len(sys.argv) != 3:
        print("Usage: python main.py <keyword> <num>")
        print("Example: python main.py 供应链 30")
        sys.exit(1)

    keyword = sys.argv[1]
    num = int(sys.argv[2])
    print(f"[main] keyword='{keyword}', target={num} papers")

    pw, browser, page = launch_browser()
    all_results = []

    try:
        search_keyword(page, keyword)
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

                print(f"\n  [{len(all_results)+1}/{target}] {item['title'][:50]}...")
                search_page_url = page.url

                # Extract detail metadata
                detail = extract_detail_metadata(page, item["url"])
                item.update(detail)
                _random_delay(DELAY_DETAIL)

                # Download full text
                file_path, file_type = download_paper(page, keyword, item["title"])
                item["file_path"] = file_path
                item["file_type"] = file_type

                all_results.append(item)

                # Go back to search results
                page.goto(search_page_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(3)
                _random_delay(DELAY_PAGE)

            if len(all_results) >= target:
                break

            # Next page
            if not go_next_page(page):
                print("[main] no more pages")
                break
            page_num += 1
            _random_delay(DELAY_PAGE)

        save_results(keyword, all_results)

    except KeyboardInterrupt:
        print("\n[main] interrupted by user")
        if all_results:
            save_results(keyword, all_results)
    finally:
        close_browser(pw, browser)
        print("[main] done")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import**

```bash
python -c "from main import main; print('import ok')"
```

Expected: `import ok`

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add main entry point with CLI args and CSV output"
```

---

### Task 6: Debug & end-to-end test

- [ ] **Step 1: Create debug script to verify selectors**

Create `debug.py`:

```python
"""Debug: open CNKI search, check selectors."""
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from browser import launch_browser, close_browser
from scraper import search_keyword, extract_list_items, get_total_results

pw, browser, page = launch_browser()

search_keyword(page, "供应链")
total = get_total_results(page)
print(f"Total results: {total}")

items = extract_list_items(page)
print(f"Items on page 1: {len(items)}")

for i, item in enumerate(items[:3]):
    print(f"\n=== Item {i} ===")
    for k, v in item.items():
        print(f"  {k}: {str(v)[:80]}")

# Take screenshot
page.screenshot(path="debug_cnki.png", full_page=True)
print("\nScreenshot saved to debug_cnki.png")

# Save HTML
html = page.content()
with open("debug_cnki.html", "w", encoding="utf-8") as f:
    f.write(html)
print("HTML saved to debug_cnki.html")

close_browser(pw, browser)
```

- [ ] **Step 2: Install dependencies (if not already)**

```bash
pip install playwright && python -m playwright install chromium
```

- [ ] **Step 3: Run debug script**

Run in a terminal (needs campus network / VPN):

```bash
cd "C:\Users\laidh\Desktop\01#项目\0128#cnki_scraper"
python debug.py
```

Check output: verify items are extracted, inspect screenshot. If selectors don't match, update `scraper.py` based on the saved HTML.

- [ ] **Step 4: Run full scraper with 3 papers**

```bash
python main.py 供应链 3
```

Expected:
1. Searches CNKI for "供应链"
2. Extracts metadata for 3 papers
3. Downloads PDF/CAJ for each
4. Saves CSV to `output/metadata/供应链.csv`
5. Papers saved in `output/papers/供应链/`

- [ ] **Step 5: Verify output**

```bash
python -c "
import csv
from pathlib import Path
f = Path('output/metadata/供应链.csv')
reader = csv.DictReader(open(f, encoding='utf-8-sig'))
rows = list(reader)
print(f'rows: {len(rows)}')
if rows:
    print(f'fields: {list(rows[0].keys())}')
    for r in rows:
        print(f'  {r[\"title\"][:40]} | file={r[\"file_type\"]} | doi={r[\"doi\"]}')"
```

- [ ] **Step 6: Fix any selector issues and commit**

```bash
git add -A
git commit -m "feat: complete CNKI scraper v1.0"
```
