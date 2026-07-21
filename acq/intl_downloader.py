# acq/intl_downloader.py
from pathlib import Path
from acq.sources import oa, scihub
from acq.identifiers import safe_filename

def download(meta, out_dir, guards, *, email, scihub_enabled=True,
             nber_enabled=True, carsi_enabled=False, carsi_store=None, carsi_cfg=None):
    doi = meta.get("doi") or ""
    if not doi:
        return ("", "")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{safe_filename(meta.get('title') or doi)}.pdf"
    if out_path.exists() and out_path.stat().st_size > 0:
        return (str(out_path), "cache")

    # 1) OA 优先（合法、免费）
    g = guards.get("oa")
    if not g or g.can_download():
        g and g.wait()
        try:
            if oa.download_oa(doi, out_path, email=email):
                g and g.record(ok=True)
                return (str(out_path), "oa")
        except Exception:
            pass
        g and g.record(ok=False)

    # 2) NBER 工作论文（免费合法，econ 近年 2022+ 缺口主通道；下的是 WP 版，内容≈正刊）
    if nber_enabled:
        g = guards.get("nber")
        if not g or g.can_download():
            g and g.wait()
            try:
                from acq.sources import nber as nber_src
                if nber_src.download_nber(meta, out_path):
                    g and g.record(ok=True)
                    return (str(out_path), "nber")
            except Exception:
                pass
            g and g.record(ok=False)

    # 3) CARSI 机构订阅（合法授权，优先于法律灰色的 Sci-Hub）
    # guard 完全由 carsi.download_subscription() 内部管理（can_download/wait/record/trip）
    # 此处不包裹外层 guard，避免双重 wait（~30s 实际等待）和双重 record（有效配额减半）
    if carsi_enabled and carsi_store is not None and carsi_cfg is not None:
        from acq.sources import carsi as carsi_src
        carsi_path = out_dir / f"{safe_filename(meta.get('title') or doi)}.pdf"
        try:
            if carsi_src.download_subscription(doi, carsi_path,
                                               store=carsi_store, cfg=carsi_cfg,
                                               guard=guards.get("carsi")):
                return (str(carsi_path), "carsi")
        except Exception:
            pass

    # 4) Sci-Hub 兜底（闭源顶刊；灰色，受 guard 管）
    if scihub_enabled:
        g = guards.get("scihub")
        if not g or g.can_download():
            g and g.wait()
            try:
                if scihub.download_scihub(doi, out_path):
                    g and g.record(ok=True)
                    return (str(out_path), "scihub")
            except Exception:
                pass
            g and g.record(ok=False)
    return ("", "")
