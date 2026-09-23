"""Retry/backoff behaviour of the rate-limited HTTP client."""
from __future__ import annotations

import ebook_sorter.lookup.http as http_mod
from ebook_sorter.lookup.http import RateLimitedClient


class _FakeResp:
    def __init__(self, status: int) -> None:
        self.status_code = status
        self.headers: dict[str, str] = {}


def test_429_fails_fast_after_max_retries(monkeypatch):
    calls = {"get": 0, "sleep": 0}
    monkeypatch.setattr(http_mod.httpx, "get", lambda url, **kw: (calls.__setitem__("get", calls["get"] + 1), _FakeResp(429))[1])
    monkeypatch.setattr(http_mod.time, "sleep", lambda s: calls.__setitem__("sleep", calls["sleep"] + 1))
    monkeypatch.setattr(http_mod, "_MAX_RETRIES", 2)
    monkeypatch.setattr(http_mod, "_MAX_BACKOFF", 0.0)

    resp = RateLimitedClient(min_interval=0.0).get("https://example.test")

    assert resp.status_code == 429            # surfaces the 429 to the caller
    assert calls["get"] == 2                  # tried exactly _MAX_RETRIES times
    assert calls["sleep"] <= 1                # at most one backoff between the two tries


def test_backoff_is_capped(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(http_mod.httpx, "get", lambda url, **kw: _FakeResp(429))
    monkeypatch.setattr(http_mod.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(http_mod, "_MAX_RETRIES", 5)
    monkeypatch.setattr(http_mod, "_MAX_BACKOFF", 3.0)

    RateLimitedClient(min_interval=0.0).get("https://example.test")

    assert slept, "expected at least one backoff"
    assert all(s <= 3.0 for s in slept)       # never sleeps longer than the cap
