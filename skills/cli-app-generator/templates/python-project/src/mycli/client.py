"""HTTP client: auth injection, proxy normalization, retries, stderr logging.

All logging goes to stderr so stdout stays pipe-safe.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

import httpx

from .config import Profile

__all__ = ["ClientError", "NetworkError", "SolrHTTPError", "Client"]  # rename SolrHTTPError → APIHTTPError as fits


class ClientError(Exception):
    pass


class NetworkError(ClientError):
    """Connection failed / timed out after all retries."""


class SolrHTTPError(ClientError):
    """Non-2xx from the API (or a proxy in front of it)."""

    def __init__(self, status_code: int, message: str, body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


_RETRYABLE_STATUS = {429, 502, 503, 504}
_PROXY_ENV_VARS = ("ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy")


def _normalize_proxy_env() -> None:
    """Rewrite bare ``socks://`` proxy URLs to ``socks5://`` in this process.

    curl (and v2ray/clash shell exports) treat ``socks://`` as SOCKS5, but
    httpx raises ``ValueError: Unknown scheme for proxy URL`` on it.
    """
    for var in _PROXY_ENV_VARS:
        val = os.environ.get(var)
        if val and val.lower().startswith("socks://"):
            os.environ[var] = "socks5://" + val[len("socks://"):]


class Client:
    """httpx wrapper: trust_env, retries with backoff, verbose logging."""

    def __init__(self, profile: Profile, *, verify: bool | None = None, timeout: float | None = None) -> None:
        self.profile = profile
        self._verify = profile.verify_tls if verify is None else verify
        self._timeout = profile.timeout if timeout is None else timeout
        self._client: httpx.Client | None = None

    def _build_client(self) -> httpx.Client:
        _normalize_proxy_env()  # socks:// → socks5:// before httpx sees env
        headers = {
            "User-Agent": "mycli/0.1",
            "Accept": "application/json",
        }
        if self.profile.token:
            headers["Authorization"] = f"Bearer {self.profile.token}"
        headers.update(self.profile.extra_headers)
        return httpx.Client(
            base_url=self.profile.url,
            headers=headers,
            verify=self._verify,
            timeout=self._timeout,
            follow_redirects=True,
            trust_env=True,  # honor HTTP(S)_PROXY / ALL_PROXY / NO_PROXY
        )

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = self._build_client()
        return self._client

    def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            self._client.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _log(self, msg: str) -> None:  # verbose only, always stderr
        if os.environ.get("MYCLI_QUIET"):
            return
        if os.environ.get("MYCLI_VERBOSE"):
            print(msg, file=sys.stderr)

    def _warn(self, msg: str) -> None:  # default-visible warnings, stderr
        if os.environ.get("MYCLI_QUIET"):
            return
        print(msg, file=sys.stderr)

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: dict[str, str] | None = None,
        retries: int | None = None,
        retry_delay: float | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send with retry/backoff; returns parsed JSON. Raises NetworkError/APIHTTPError."""
        max_attempts = (retries if retries is not None else self.profile.retries) + 1
        delay = retry_delay if retry_delay is not None else self.profile.retry_delay
        client = self._get_client()
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            try:
                self._log(f"--> {method} {client.base_url}{path} (attempt {attempt}/{max_attempts})")
                response = client.request(
                    method, path, json=json_body, params=params, timeout=timeout,
                )
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout,
                    httpx.WriteTimeout, httpx.PoolTimeout) as exc:
                if attempt < max_attempts:
                    self._warn(f"<-- attempt {attempt}/{max_attempts} failed: {exc}; retrying in {delay:.1f}s")
                    time.sleep(delay)
                    delay = min(delay * 2, 30.0)
                    continue
                raise NetworkError(f"{self.profile.url} failed after {max_attempts} attempts: {exc}") from exc

            if response.status_code in _RETRYABLE_STATUS and attempt < max_attempts:
                self._warn(f"<-- HTTP {response.status_code} (attempt {attempt}/{max_attempts}); retrying in {delay:.1f}s")
                time.sleep(delay)
                delay = min(delay * 2, 30.0)
                continue

            body = response.text
            self._log(f"<-- HTTP {response.status_code} {body[:200]}")
            if response.is_error:
                raise SolrHTTPError(response.status_code, f"HTTP {response.status_code}: {body[:500]}", body=body)
            try:
                return response.json()
            except ValueError as exc:
                raise SolrHTTPError(
                    response.status_code,
                    f"expected JSON but got {response.headers.get('content-type')!r} "
                    f"(auth wall? token expired?) body: {body[:300]}",
                    body=body,
                ) from exc
        raise NetworkError(f"request failed after {max_attempts} attempts")
