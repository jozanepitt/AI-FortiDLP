"""Thin, strictly read-only wrapper around the FortiDLP REST API.

Endpoint paths below are placeholders. They match the shapes most FortiDLP
(NextDLP/Reveal) tenants expose but should be confirmed against the actual
API docs for your tenant during the first-run spike. Response parsing is
defensive: we normalize to simple dicts so downstream tools don't have to
care about minor shape drift.

Only GET requests are permitted. There is no write helper.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class FortiDLPClient:
    """Read-only async client for the FortiDLP console API."""

    def __init__(self, base_url: str, token: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # --- core request helper (read-only) ---

    async def _get(self, path: str, **params: Any) -> Any:
        clean_params = {k: v for k, v in params.items() if v is not None}
        resp = await self._client.get(path, params=clean_params)
        resp.raise_for_status()
        return resp.json()

    # --- high-level endpoints ---

    async def top_users(self, period: str = "today", limit: int = 10) -> list[dict]:
        """Return the users with the most policy triggers in `period`.

        `period` is one of: today, week, month.
        """
        data = await self._get(
            "/analytics/top-users",
            period=period,
            limit=limit,
        )
        return _as_list(data)

    async def top_policies(self, period: str = "today", limit: int = 10) -> list[dict]:
        """Return the most-triggered policies in `period`."""
        data = await self._get(
            "/analytics/top-policies",
            period=period,
            limit=limit,
        )
        return _as_list(data)

    async def os_breakdown(self) -> dict[str, int]:
        """Return a mapping of OS family (macos/windows/linux/...) to device count."""
        data = await self._get("/analytics/os-breakdown")
        if isinstance(data, dict):
            return data
        # tolerate [{os: "windows", count: 42}, ...]
        result: dict[str, int] = {}
        for row in _as_list(data):
            os_name = row.get("os") or row.get("platform") or "unknown"
            count = row.get("count") or row.get("value") or 0
            result[str(os_name).lower()] = int(count)
        return result

    async def license_usage(self) -> dict[str, Any]:
        """Return license usage (used / total / available / expiration)."""
        data = await self._get("/licenses")
        return data if isinstance(data, dict) else {"raw": data}

    async def unhealthy_devices(self, limit: int = 50) -> list[dict]:
        """Return devices reported as unhealthy, with reasons."""
        data = await self._get(
            "/devices",
            status="unhealthy",
            limit=limit,
        )
        return _as_list(data)


def _as_list(data: Any) -> list[dict]:
    """Normalize common API response shapes to a flat list of dicts."""
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("items", "results", "data"):
            if isinstance(data.get(key), list):
                return [row for row in data[key] if isinstance(row, dict)]
    return []
