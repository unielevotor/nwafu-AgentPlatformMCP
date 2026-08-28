from nwafu_mcp import config


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload
        self.text = payload if isinstance(payload, str) else ""

    def raise_for_status(self):
        return None

    def json(self):
        if isinstance(self._payload, str):
            raise ValueError("not json")
        return self._payload


def _fake_get(url, headers=None, timeout=None):
    assert headers["Authorization"] == "Bearer secret-token"
    return _FakeResp({"cookie_header": "p_uin=1; uuid=2; EO-Bot-Js-Token=3"})


def test_fetch_remote_cookie(monkeypatch):
    config._REMOTE_COOKIE_CACHE.clear()
    monkeypatch.setattr(config.requests, "get", _fake_get)
    value = config.fetch_remote_cookie(
        "http://127.0.0.1:8765/cookie", token="secret-token", ttl=600
    )
    assert value == "p_uin=1; uuid=2; EO-Bot-Js-Token=3"


def test_fetch_remote_cookie_cache_and_fallback(monkeypatch):
    config._REMOTE_COOKIE_CACHE.clear()
    monkeypatch.setattr(config.requests, "get", _fake_get)
    url = "http://127.0.0.1:8765/cookie"
    first = config.fetch_remote_cookie(url, token="secret-token", ttl=600)
    assert first

    def _boom(url, headers=None, timeout=None):
        raise OSError("network down")

    monkeypatch.setattr(config.requests, "get", _boom)
    # TTL 内命中缓存，不触发网络请求
    assert config.fetch_remote_cookie(url, token="secret-token", ttl=600) == first
    # TTL 过期后刷新失败，回退到旧缓存
    config._REMOTE_COOKIE_CACHE[url]["fetched_at"] = 0
    assert config.fetch_remote_cookie(url, token="secret-token", ttl=600) == first
