"""httpx client factory + retry — the extension point for real API commands.

Wire a command like: ``rows = Client(resolve_profile(profile)).request("GET", f"/{resource}")["items"]``.
"""

import os

import httpx
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

from .config import Profile

_RETRY_STATUSES = {429, 502, 503, 504}  # transient: retry with backoff


class APIError(Exception):
    """API/network failure. code "network" → exit 3, anything else → exit 1 (see cli.main)."""

    def __init__(self, message: str, status: int | None = None, code: str = "api"):
        super().__init__(message)
        self.status, self.code = status, code


def _retryable(error: BaseException) -> bool:
    return isinstance(error, httpx.TransportError) or (
        isinstance(error, APIError) and error.status in _RETRY_STATUSES
    )


def normalize_proxy_env() -> None:
    """httpx rejects bare socks:// — rewrite to socks5:// in place (single source of truth)."""
    for var in ("ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"):
        if os.environ.get(var, "").startswith("socks://"):
            os.environ[var] = "socks5://" + os.environ[var][len("socks://"):]


class Client:
    """Bearer-authenticated client for a Profile; retries transient failures."""

    def __init__(self, profile: Profile):
        self.profile = profile
        self._client: httpx.Client | None = None

    def _build_client(self) -> httpx.Client:
        normalize_proxy_env()
        headers = {"Authorization": f"Bearer {self.profile.token}"} if self.profile.token else {}
        return httpx.Client(
            base_url=self.profile.url, timeout=self.profile.timeout,
            verify=self.profile.verify_tls, trust_env=True, headers=headers,
        )

    def request(self, method: str, path: str, **kwargs) -> dict | list:
        """Request with retry + exponential backoff; returns the parsed JSON body."""
        self._client = self._client or self._build_client()

        def attempt() -> dict | list:
            response = self._client.request(method, path, **kwargs)
            if response.status_code >= 400:
                raise APIError(f"{path}: HTTP {response.status_code}", status=response.status_code)
            return response.json() if response.content else {}

        retryer = Retrying(
            stop=stop_after_attempt(self.profile.retries + 1),
            wait=wait_exponential(multiplier=self.profile.retry_delay, exp_base=2, max=30),
            retry=retry_if_exception(_retryable), reraise=True,
        )
        try:
            return retryer(attempt)
        except httpx.TransportError as e:
            raise APIError(f"network unreachable: {e}", code="network") from e
