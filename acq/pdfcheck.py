# acq/pdfcheck.py
import os
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlparse

_BAD_PATH = ("/data-providers/", "/providers/", "/journals/", "/subjects/")

def is_plausible_pdf_url(url: str) -> bool:
    if not url or not url.lower().startswith(("http://", "https://")):
        return False
    p = urlparse(url)
    path = p.path.lower()
    if any(b in path for b in _BAD_PATH):
        return False
    q = p.query.lower()
    return (path.endswith(".pdf") or "/pdf" in path or "download/pdf" in path
            or "format=pdf" in q or "type=pdf" in q
            or path.endswith("/document"))  # HAL 特例

def response_looks_pdf(first_chunk: bytes, content_type: str) -> bool:
    if first_chunk[:5] == b"%PDF-":
        return True
    return "application/pdf" in (content_type or "").lower()

def is_pdf_file(path, min_size: int = 1000) -> bool:
    path = Path(path)
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size < min_size:
        return False
    with open(path, "rb") as f:
        if f.read(5) != b"%PDF-":
            return False
        f.seek(max(0, size - 1024))
        return b"%%EOF" in f.read()

def write_pdf_atomic(resp_iter: Iterable[bytes], out_path: Path) -> bool:
    """resp_iter: 可迭代 bytes 块。写 .part→校验→原子改名。"""
    out_path = Path(out_path)
    part = out_path.with_suffix(out_path.suffix + ".part")
    try:
        with open(part, "wb") as f:
            for chunk in resp_iter:
                if chunk:
                    f.write(chunk)
        if not is_pdf_file(part):
            part.unlink(missing_ok=True)
            return False
        os.replace(part, out_path)
        return True
    except Exception:
        part.unlink(missing_ok=True)
        return False
