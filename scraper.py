import re
import time
import random
from playwright.sync_api import Page
from config import CNKI_SEARCH_URL, CNKI_ADVANCED_URL, DELAY_PAGE, DELAY_DETAIL, MAX_RETRIES


def _random_delay(delay_range: tuple) -> None:
    delay = random.uniform(*delay_range)
    print(f"  [delay] waiting {delay:.1f}s...")
    time.sleep(delay)


def _check_captcha(page: Page) -> bool:
    """Check if we hit a CAPTCHA page or overlay. Returns True if CAPTCHA detected."""
    # Check for overlay/modal CAPTCHA (appears on top of current page)
    overlay = page.query_selector(
        ".verify-img-panel, #verify-bar-box, .verifybox, "
        ".mask[style*='display: block'], .verify-mask"
    )
    if overlay:
        try:
            if overlay.is_visible():
                return True
        except Exception:
            pass
    # Check for full-page CAPTCHA redirect
    search_input = page.query_selector("input.search-input, input#txt_SearchText")
    if search_input:
        return False
    return "verify" in page.url or "captcha" in page.url.lower() or page.title() == "安全验证"


def wait_for_captcha(page: Page) -> None:
    """看得见拼图才打码；过了（检索框/无控件）立刻写 cookie。URL 带 /verify 不算失败。"""
    from captcha import (
        solve_slider_captcha,
        captcha_blocks_cookie_write,
        _has_pass_signal,
        _captcha_widget_visible,
        _captcha_url_hint,
    )
    from browser import save_cookies_after_captcha

    if _has_pass_signal(page):
        return
    if not _captcha_widget_visible(page) and _captcha_url_hint(page):
        for _ in range(8):
            if _captcha_widget_visible(page) or _has_pass_signal(page):
                break
            time.sleep(0.4)
    if _has_pass_signal(page) or not _captcha_widget_visible(page):
        return
    print("[captcha] 检测到验证码，超级鹰自动解...")
    for _round in range(3):
        if solve_slider_captcha(page):
            try:
                save_cookies_after_captcha(page.context)
            except Exception:
                pass
            time.sleep(1.0)
            if _has_pass_signal(page) or not captcha_blocks_cookie_write(page):
                print("[captcha] 已通过 ✓")
                return
        time.sleep(2)
    print("[captcha] 自动解多轮失败，跳过本次（不死等）")


def search_keyword(page: Page, keyword: str) -> None:
    """Navigate to CNKI and perform a keyword search."""
    page.goto(CNKI_SEARCH_URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    wait_for_captcha(page)

    # After CAPTCHA, URL may still be /verify/... even though page loaded
    # Re-navigate to search page if needed
    if "verify" in page.url:
        print("[search] re-navigating to search page after CAPTCHA...")
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
    wait_for_captcha(page)
    print(f"[search] searched for '{keyword}'")


def search_professional(page: Page, expression: str) -> None:
    """Navigate directly to CNKI professional search page and execute the expression."""
    try:
        page.goto(CNKI_ADVANCED_URL, wait_until="domcontentloaded", timeout=30000)
    except Exception:
        if _check_captcha(page):
            wait_for_captcha(page)
        else:
            raise
    time.sleep(5)
    wait_for_captcha(page)

    if "verify" in page.url:
        print("[search] re-navigating after CAPTCHA...")
        page.goto(CNKI_ADVANCED_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)

    # Fill the professional search textarea
    textarea = page.query_selector("textarea")
    if not textarea or not textarea.is_visible():
        page.screenshot(path="debug_pro_search.png")
        raise RuntimeError("Cannot find professional search textarea. Screenshot saved to debug_pro_search.png")
    textarea.click()
    textarea.fill(expression)
    print(f"[search] expression filled ({len(expression)} chars)")
    _random_delay((1, 2))

    # Click search button
    search_btn = page.query_selector("input.btn-search")
    if not search_btn:
        search_btn = page.query_selector("input[type='button'][value='检索'], button:has-text('检索')")
    if search_btn:
        search_btn.click()
    else:
        textarea.press("Enter")

    # CNKI loads results via AJAX (SPA), so wait for result table or error message
    time.sleep(8)
    wait_for_captcha(page)
    expr_preview = expression[:80] + "..." if len(expression) > 80 else expression
    print(f"[search] professional search executed: {expr_preview}")


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
    # Try multiple selectors — professional search uses different DOM
    selectors = [
        "#PageNext",
        "a#PageNext",
        "a.PageNext",
        "#page-next",
        "a[id*='PageNext']",
        "a.next",                       # common pagination class
    ]
    next_btn = None
    for sel in selectors:
        el = page.query_selector(sel)
        if el:
            try:
                if el.is_visible():
                    next_btn = el
                    break
            except Exception:
                continue

    # Fallback: find "下一页" or ">" link in pagination area
    if not next_btn:
        for candidate in page.query_selector_all("a"):
            text = (candidate.inner_text() or "").strip()
            if text in (">", "›", "下一页", "»"):
                try:
                    if candidate.is_visible():
                        next_btn = candidate
                        break
                except Exception:
                    continue

    if not next_btn:
        # Debug: screenshot and log pagination HTML
        page_area = page.query_selector(".pager, .page, #page, [class*='pager'], [class*='pagin']")
        if page_area:
            print(f"[pagination] found pager area, HTML: {page_area.inner_html()[:500]}")
        else:
            print("[pagination] no pager element found on page")
        page.screenshot(path="debug_pagination.png")
        print("[pagination] screenshot saved to debug_pagination.png")
        return False

    # Check if disabled or not visible
    cls = next_btn.get_attribute("class") or ""
    if "disabled" in cls or "noclick" in cls:
        return False
    try:
        if not next_btn.is_visible():
            print("[pagination] next button found but not visible")
            page.screenshot(path="debug_pagination.png")
            print("[pagination] screenshot saved to debug_pagination.png")
            return False
    except Exception:
        pass

    next_btn.click()
    page.wait_for_load_state("domcontentloaded")
    time.sleep(5)
    wait_for_captcha(page)
    return True


def extract_detail_metadata(page: Page, url: str) -> dict:
    """Navigate to detail page and extract full metadata.

    Returns dict with keys: abstract, keywords, doi, fund, institution.
    """
    for attempt in range(MAX_RETRIES):
        try:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as nav_err:
                # Navigation may timeout due to CAPTCHA redirect — check and solve
                print(f"  [warn] navigation issue: {nav_err}")
                if _check_captcha(page):
                    print("  [captcha] CAPTCHA detected during navigation, solving...")
                    wait_for_captcha(page)
                    # After CAPTCHA, retry navigation
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    except Exception:
                        pass
                else:
                    raise
            time.sleep(3)
            wait_for_captcha(page)

            # Verify we actually landed on a detail page, not a block page
            detail_marker = page.query_selector(
                "#ChDivSummary, .abstract-text, .doc-top, .wx-tit, h1"
            )
            if not detail_marker:
                current_url = page.url
                title = page.title()
                print(f"  [debug] detail page not loaded. URL={current_url[:80]}, title={title}")
                page.screenshot(path="debug_detail_page.png")
                print("  [debug] screenshot saved to debug_detail_page.png")
                # Might be an undetected CAPTCHA or block page
                if _check_captcha(page) or "verify" in current_url or title == "安全验证":
                    wait_for_captcha(page)
                    # retry navigation after solving
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
            doi_el = page.query_selector("[id*='DOI'] a, .doi a")
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
