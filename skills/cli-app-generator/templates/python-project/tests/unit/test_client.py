"""Client tests: proxy normalization, retries, error mapping (mock transport)."""

import httpx
import pytest

from mycli.client import Client, NetworkError, SolrHTTPError, _normalize_proxy_env


def make_client(handler, **kwargs):
    from mycli.config import Profile

    profile = Profile(name="t", url="https://api.test", token="tok", **{
        k: v for k, v in kwargs.items() if k in {"verify_tls", "timeout", "retries", "retry_delay"}
    })
    client = Client(profile)
    built = client._build_client()
    built._transport = httpx.MockTransport(handler)
    client._client = built
    return client


def test_normalize_socks_scheme(monkeypatch):
    from mycli.client import _normalize_proxy_env
    import os

    monkeypatch.setenv("ALL_PROXY", "socks://127.0.0.1:10808")
    _normalize_proxy_env()
    assert os.environ["ALL_PROXY"] == "socks5://127.0.0.1:10808"


def test_retries_on_503_then_success():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, json={"error": "overloaded"})
        return httpx.Response(200, json={"items": [{"id": 1}]})

    from mycli.config import Profile

    c = Client(Profile(name="t", url="https://api.test", retries=3, retry_delay=0))
    c._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.test")
    result = c.request("GET", "/x")
    assert result == {"items": [{"id": 1}]}
    assert calls["n"] == 3


def test_network_error_after_exhausted_retries():
    def handler(request):
        raise httpx.ConnectError("connection refused")

    from mycli.config import Profile

    c = Client(Profile(name="t", url="https://api.test", retries=1, retry_delay=0))
    c._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.test")
    with pytest.raises(NetworkError):
        c.request("GET", "/x")


def test_401_raises_http_error():
    def handler(request):
        return httpx.Response(401, text="unauthorized", headers={"content-type": "text/html"})

    from mycli.config import Profile

    c = Client(Profile(name="t", url="https://api.test"))
    c._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.test")
    with pytest.raises(SolrHTTPError) as exc:
        c.request("GET", "/x")
    assert exc.value.status_code == 401
