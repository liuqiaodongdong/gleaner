# acq/identifiers.py
import re
from urllib.parse import unquote

def normalize_doi(v: str) -> str:
    v = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", v or "", flags=re.I)
    v = re.sub(r"^doi:\s*", "", v, flags=re.I)
    return unquote(v).strip()

def normalize_doi_unicode(v: str):
    if not v:
        return None
    v = normalize_doi(v)
    for ch in ("‐", "‑", "‒", "–", "—"):
        v = v.replace(ch, "-")
    v = re.sub(r"\s+", "", v)
    return v if re.match(r"^10\.\d{4,}/", v) else None

def safe_filename(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._\-一-鿿]+", "_", s or "").strip("_")
    return s[:100] or "paper"

def arxiv_pdf_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
