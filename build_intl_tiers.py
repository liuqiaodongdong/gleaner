# build_intl_tiers.py —— 从《总体期刊目录.xlsx》+ Elsevier Serial Title API 重建国际白名单 tier 文件
import json, time, re, sys
from pathlib import Path
import pandas as pd
import requests
from acq.els_config import get_api_key

XLSX = r"C:\Users\laidh\Desktop\总体期刊目录.xlsx"
OUT = Path(__file__).parent / "acq" / "data" / "intl_journal_tiers.json"


def tier_of(level: str) -> int:
    l = str(level)
    if l in ("顶级国际期刊", "顶级国内期刊", "A+++类期刊", "A++类期刊"):
        return 1
    if l == "A+类期刊":
        return 2
    return 3


def _is_intl(name: str) -> bool:
    s = str(name)
    lat = sum(c.isalpha() and ord(c) < 128 for c in s)
    cjk = sum("一" <= c <= "鿿" for c in s)
    return lat > cjk


def build(xlsx: str = XLSX) -> dict:
    df = pd.read_excel(xlsx, sheet_name="期刊目录", header=1)
    df.columns = ["name", "issn", "level", "discount"]
    df = df.dropna(subset=["issn"])
    df = df[df["issn"].astype(str).str.match(r"^\d{4}-\d{3}[\dXx]$")]
    df = df[df["name"].apply(_is_intl)]
    wl = {r.issn.upper(): {"name": r.name, "level": r.level} for r in df.itertuples()}
    issns = list(wl.keys())

    s = requests.Session(); s.trust_env = False
    s.headers.update({"X-ELS-APIKey": get_api_key(), "Accept": "application/json"})
    hits = {}
    for i in range(0, len(issns), 25):
        batch = issns[i:i + 25]
        r = s.get("https://api.elsevier.com/content/serial/title",
                  params={"issn": ",".join(batch), "count": 25}, timeout=50)
        if r.status_code != 200:
            time.sleep(1); continue
        ents = r.json().get("serial-metadata-response", {}).get("entry", [])
        if isinstance(ents, dict):
            ents = [ents]
        for e in ents:
            pub = e.get("dc:publisher", "") or ""
            subj = e.get("subject-area", []); subj = subj if isinstance(subj, list) else [subj]
            codes = [str(x.get("@code", "")) for x in subj]
            if "elsevier" not in pub.lower():
                continue
            if not any(c.startswith("14") or c.startswith("20") for c in codes):
                continue
            cand = {v.upper() for k in ("prism:issn", "prism:eIssn") if (v := e.get(k))}
            key = next((c for c in cand if c in wl), None) or next((b for b in batch if b in cand), None)
            if not key:
                continue
            hits[key] = {"name": e.get("dc:title"), "issn": key,
                         "level": wl[key]["level"], "tier": tier_of(wl[key]["level"]),
                         "asjc": codes}
        time.sleep(0.35)

    out = {"meta": {"source": "总体期刊目录.xlsx 2024",
                    "filter": "Elsevier ∩ ASJC(14/20)", "count": len(hits)},
           "tier1": [], "tier2": [], "tier3": []}
    for rec in sorted(hits.values(), key=lambda x: (x["tier"], str(x["level"]), x["name"])):
        out[f"tier{rec['tier']}"].append(rec)
    return out


def main():
    out = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT} : {out['meta']['count']} journals "
          f"(t1={len(out['tier1'])} t2={len(out['tier2'])} t3={len(out['tier3'])})")


if __name__ == "__main__":
    main()
