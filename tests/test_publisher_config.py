import json
from pathlib import Path

def test_config_shape():
    cfg = json.loads(Path("acq/data/publisher_carsi.json").read_text("utf-8"))
    for key in ("sciencedirect", "springer", "ebsco", "emerald", "proquest"):
        assert key in cfg, f"缺 {key}"
        assert "domains" in cfg[key] and isinstance(cfg[key]["domains"], list)
