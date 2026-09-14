"""Domain operations, shared by CLI and tests: request builders + parsers.

Keep CLI wiring here-thin: this module is where testable logic lives.
"""

from __future__ import annotations

from typing import Any

from .client import Client

__all__ = ["health_check", "list_resource"]


def health_check(client: Client) -> dict[str, Any]:
    """One cheap authenticated call for the setup wizard. Adapt to your API."""
    return client.request("GET", "/health")


def list_resource(client: Client, resource: str, *, timeout=None, retries=None) -> list[dict[str, Any]]:
    """Fetch a list endpoint and return rows for CSV/JSON output."""
    payload = client.request("GET", f"/{resource}", timeout=timeout, retries=retries)
    return payload.get("items", payload) if isinstance(payload, dict) else payload
