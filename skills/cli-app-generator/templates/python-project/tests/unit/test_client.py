"""Client tests: proxy normalization, retry/backoff, error mapping (MockTransport — no network)."""

import os

import httpx
import pytest

from mycli.client import APIError, Client, normalize_proxy_env
from mycli.config import Profile


def make_client(handler, **profile_kwargs) -> Client:
    profile = Profile(name="t", url="https://api.test", retry_delay=0, **profile_kwargs)
    client = Client(profile)
    built = client._build_client()
    built._transport = httpx.MockTransport(handler)
    client._client = built
    return client


def test_normalize_socks_scheme(monkeypatch):
    monkeypatch.setenv("ALL_PROXY", "socks://127.0.0.1:10808")
    normalize_proxy_env()
    assert os.environ["ALL_PROXY"] == "socks5://127.0.0.1:10808"


def test_normalize_leaves_other_schemes(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy:8080")
    normalize_proxy_env()
    assert os.environ["HTTPS_PROXY"] == "http://proxy:8080"


def test_retries_on_503_then_success():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"items": [{"id": 1}]})

    result = make_client(handler, retries=3).request("GET", "/x")
    assert result == {"items": [{"id": 1}]}
    assert calls["n"] == 3


def test_retry_exhausted_503_maps_to_api_error():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(503)

    with pytest.raises(APIError) as exc:
        make_client(handler, retries=1).request("GET", "/x")
    assert calls["n"] == 2  # initial + 1 retry
    assert exc.value.status == 503 and exc.value.code == "api"


def test_no_retry_on_401():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(401, text="unauthorized")

    with pytest.raises(APIError) as exc:
        make_client(handler).request("GET", "/x")
    assert calls["n"] == 1
    assert exc.value.status == 401 and exc.value.code == "api"


def test_transport_error_maps_to_network_code():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        raise httpx.ConnectError("connection refused")

    with pytest.raises(APIError) as exc:
        make_client(handler, retries=1).request("GET", "/x")
    assert calls["n"] == 2  # initial + 1 retry, then network envelope code
    assert exc.value.code == "network"


def test_bearer_header_from_token():
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={})

    make_client(handler, token="tok").request("GET", "/x")
    assert captured["auth"] == "Bearer tok"


def test_no_auth_header_without_token():
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={})

    make_client(handler).request("GET", "/x")
    assert captured["auth"] is None


def test_empty_body_returns_empty_dict():
    assert make_client(lambda request: httpx.Response(204)).request("GET", "/x") == {}
