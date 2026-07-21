import re
import time
from pathlib import Path
from playwright.sync_api import Page
from config import PAPERS_DIR


def _sanitize_filename(name: str) -> str:
    """Replace illegal filename characters with underscore."""
    return re.sub(r'[\\/*?:"<>|\n\r\t]', '_', name).strip()[:100]


def is_already_downloaded(title: str, output_dir: Path | None = None) -> bool:
    """Check if a paper with the given title has already been downloaded."""
    save_dir = output_dir if output_dir else PAPERS_DIR
    safe_title = _sanitize_filename(title)
    for ext in ("pdf", "caj"):
        existing = save_dir / f"{safe_title}.{ext}"
        if existing.exists() and existing.stat().st_size > 0:
            return True
    return False


def download_paper(page: Page, title: str, output_dir: Path | None = None) -> tuple[str, str]:
    """Download full-text from the current detail page.

    Tries PDF first, falls back to CAJ.
    Returns (file_path, file_type) or ("", "") if download fails.
    """
    save_dir = output_dir if output_dir else PAPERS_DIR
    save_dir.mkdir(parents=True, exist_ok=True)
    safe_title = _sanitize_filename(title)

    # Skip if already downloaded
    for ext in ("pdf", "caj"):
        existing = save_dir / f"{safe_title}.{ext}"
        if existing.exists() and existing.stat().st_size > 0:
            print(f"  [download] already exists, skipped: {existing.name}")
            rel_path = str(existing)
            return (rel_path, ext.upper())

    # Try PDF download first (multiple selector strategies)
    pdf_btn = page.query_selector(
        "a#pdfDown, a.btn-dlpdf, a[id*='pdfDown'], "
        ".btn-dlpdf a, a[href*='pdfdown'], a[onclick*='pdf']"
    )
    if not pdf_btn:
        # New CNKI UI: match by text
        pdf_btn = page.query_selector("a:has-text('PDF下载'), a:has-text('PDF 下载')")
    if pdf_btn:
        result = _do_download(page, pdf_btn, save_dir, safe_title, "pdf")
        if result:
            return result

    # Fallback to CAJ
    caj_btn = page.query_selector(
        "a#cajDown, a.btn-dlcaj, a[id*='cajDown'], "
        ".btn-dlcaj a, a[href*='cajdown']"
    )
    if not caj_btn:
        caj_btn = page.query_selector("a:has-text('CAJ下载'), a:has-text('CAJ 下载')")
    if caj_btn:
        result = _do_download(page, caj_btn, save_dir, safe_title, "caj")
        if result:
            return result

    print(f"  [download] no download button found for: {title[:40]}")
    page.screenshot(path="debug_download_fail.png")
    print(f"  [debug] screenshot saved to debug_download_fail.png, URL={page.url[:80]}")
    return ("", "")


def _do_download(page: Page, btn, save_dir: Path, safe_title: str, ext: str) -> tuple[str, str] | None:
    """Click download button and save the file. Handles both direct download and new-tab download."""
    file_path = save_dir / f"{safe_title}.{ext}"

    # Strategy 1: expect_download (direct download)
    try:
        with page.expect_download(timeout=15000) as download_info:
            btn.click()
        download = download_info.value
        download.save_as(str(file_path))
        print(f"  [download] saved {ext.upper()}: {file_path.name}")
        rel_path = str(file_path)
        return (rel_path, ext.upper())
    except Exception:
        pass

    # Strategy 2: button click opened a new tab (CNKI sometimes does this)
    try:
        context = page.context
        pages_before = context.pages[:]
        # Check if a new page was opened
        new_pages = [p for p in context.pages if p not in pages_before and p != page]
        if not new_pages:
            # Try clicking again, this time expecting a new page
            with context.expect_page(timeout=15000) as new_page_info:
                btn.click()
            new_page = new_page_info.value
            new_page.wait_for_load_state("domcontentloaded", timeout=15000)
        else:
            new_page = new_pages[0]

        # The new page might trigger a download or show PDF
        try:
            with new_page.expect_download(timeout=15000) as download_info:
                pass  # download may already be in progress
            download = download_info.value
            download.save_as(str(file_path))
            print(f"  [download] saved {ext.upper()} (via new tab): {file_path.name}")
            new_page.close()
            rel_path = str(file_path)
            return (rel_path, ext.upper())
        except Exception:
            # New page might be a PDF viewer — check URL
            new_url = new_page.url
            if "pdf" in new_url.lower() or new_url.endswith(".pdf"):
                # Download the PDF directly via URL
                import requests
                cookies = {c["name"]: c["value"] for c in context.cookies()}
                resp = requests.get(new_url, cookies=cookies, timeout=30, stream=True)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    file_path.write_bytes(resp.content)
                    print(f"  [download] saved {ext.upper()} (via URL): {file_path.name}")
                    new_page.close()
                    rel_path = str(file_path)
                    return (rel_path, ext.upper())
            new_page.close()
    except Exception as e:
        print(f"  [download] {ext.upper()} new-tab strategy failed: {e}")

    print(f"  [download] {ext.upper()} download failed")
    return None
