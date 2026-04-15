"""Read-only FortiDLP client — consumes the SIEM event stream and aggregates events."""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

log = logging.getLogger(__name__)


def _parse_ts(ts: str | None) -> datetime:
    """Parse ISO-8601 timestamp to UTC datetime. Returns epoch on failure."""
    if not ts:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, AttributeError):
        return datetime.min.replace(tzinfo=timezone.utc)


def _period_cutoff(period: str) -> datetime:
    now = datetime.now(timezone.utc)
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        return now - timedelta(days=7)
    if period == "month":
        return now - timedelta(days=30)
    return now - timedelta(hours=24)


class _EventCache:
    """Rolling 7-day in-memory store of consumed FortiDLP events."""

    _MAX_AGE = timedelta(days=7)

    def __init__(self) -> None:
        self._events: list[dict] = []

    def ingest(self, events: list[dict]) -> int:
        self._events.extend(events)
        self._prune()
        return len(events)

    def _prune(self) -> None:
        cutoff = datetime.now(timezone.utc) - self._MAX_AGE
        self._events = [e for e in self._events if _parse_ts(e.get("timestamp")) > cutoff]

    def for_period(self, period: str) -> list[dict]:
        cutoff = _period_cutoff(period)
        return [e for e in self._events if _parse_ts(e.get("timestamp")) >= cutoff]

    @property
    def size(self) -> int:
        return len(self._events)


class FortiDLPClient:
    """Async read-only client for the FortiDLP SIEM event stream.

    Consumes events via long-polling GET /api/siem and caches them
    in memory for aggregation queries (top users, top policies, etc.).

    No write methods exist — read-only by design.
    """

    _STREAM_PATH = "/api/siem"
    _POLL_TIMEOUT = 35  # seconds; API waits up to 30 s before returning empty

    def __init__(self, base_url: str, stream_id: str, stream_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._stream_id = stream_id
        self._cache = _EventCache()
        self._http = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {stream_token}"},
            timeout=httpx.Timeout(self._POLL_TIMEOUT + 5),
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    # ── Stream consumption ────────────────────────────────────────────────────

    async def _poll(self) -> list[dict]:
        """One long-poll request. Returns a list of events (may be empty)."""
        resp = await self._http.get(
            f"{self._base_url}{self._STREAM_PATH}",
            params={"stream_id": self._stream_id, "format": "json"},
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("events", "items", "data", "results"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []

    async def refresh(self, max_polls: int = 3) -> int:
        """Drain pending stream events into the local cache.

        Returns the total number of new events ingested.
        """
        total = 0
        for i in range(max_polls):
            events = await self._poll()
            if not events:
                break
            n = self._cache.ingest(events)
            total += n
            log.info(
                "fortidlp_stream poll=%d new=%d cache_size=%d",
                i + 1, n, self._cache.size,
            )
        return total

    # ── High-level query methods (called by tools) ────────────────────────────

    async def top_users(self, period: str = "today", limit: int = 10) -> list[dict]:
        await self.refresh()
        counts: Counter[str] = Counter()
        for e in self._cache.for_period(period):
            user = e.get("user_email") or e.get("user_name")
            if user:
                counts[user] += 1
        return [{"user": u, "events": c} for u, c in counts.most_common(limit)]

    async def top_policies(self, period: str = "week", limit: int = 10) -> list[dict]:
        await self.refresh()

        def _policy_name(e: dict) -> str | None:
            p = e.get("policy")
            if isinstance(p, dict):
                return p.get("name") or None
            return None

        counts: Counter[str] = Counter(
            n for e in self._cache.for_period(period) if (n := _policy_name(e))
        )
        return [{"policy": p, "count": c} for p, c in counts.most_common(limit)]

    async def detection_breakdown(self) -> dict[str, int]:
        await self.refresh()
        counts: Counter[str] = Counter(
            e.get("sensor_type", "unknown")
            for e in self._cache.for_period("week")
        )
        return dict(counts.most_common(10))

    async def top_risky_users(self, period: str = "week", limit: int = 5) -> list[dict]:
        await self.refresh()
        scores: dict[str, int] = {}
        for e in self._cache.for_period(period):
            user = e.get("user_email") or e.get("user_name")
            if user:
                scores[user] = scores.get(user, 0) + int(e.get("score") or 0)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [{"user": u, "total_score": s} for u, s in ranked[:limit]]

    async def top_devices(self, period: str = "week", limit: int = 10) -> list[dict]:
        await self.refresh()
        counts: Counter[str] = Counter(
            e.get("agent_hostname")
            for e in self._cache.for_period(period)
            if e.get("agent_hostname")
        )
        return [{"device": d, "detections": c} for d, c in counts.most_common(limit)]

    async def event_summary(self, period: str = "today") -> dict[str, Any]:
        await self.refresh()
        events = self._cache.for_period(period)
        users = {e.get("user_email") or e.get("user_name") for e in events} - {None}
        devices = {e.get("agent_hostname") for e in events} - {None}
        policies: set[str] = set()
        for e in events:
            p = e.get("policy")
            if isinstance(p, dict) and p.get("name"):
                policies.add(p["name"])
        return {
            "period": period,
            "total_events": len(events),
            "unique_users": len(users),
            "unique_devices": len(devices),
            "unique_policies": len(policies),
        }
