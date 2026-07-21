from acq.cookie_store import CookieStore

def test_save_load_state(tmp_path):
    cs = CookieStore(tmp_path)
    assert cs.load_state() is None
    cs.save_state({"cookies": [{"name": "a", "value": "1", "domain": ".sciencedirect.com"}], "origins": []})
    s = cs.load_state()
    assert s["cookies"][0]["domain"] == ".sciencedirect.com"
    assert cs.age_hours() is not None and cs.age_hours() < 1
