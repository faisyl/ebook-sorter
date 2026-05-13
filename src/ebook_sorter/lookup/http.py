from __future__ import annotations

import logging
import time

import httpx

logger = logging.getLogger(__name__)

_USER_AGENT = "ebook-sorter/0.1.0 (https://github.com/faisyl/ebook-sorter)"

_MAX_RETRIES = 5
_BACKOFF_BASE = 2.0


class RateLimitedClient:
    def __init__(self, min_interval: float = 1.0, timeout: float = 15.0) -> None:
        self._min_interval = min_interval
        self._timeout = timeout
        self._last_request: float = 0.0

    def _throttle(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = time.monotonic()

    def get(self, url: str, **kwargs) -> httpx.Response:
        kwargs.setdefault("timeout", self._timeout)
        kwargs.setdefault("headers", {})
        kwargs["headers"].setdefault("User-Agent", _USER_AGENT)

        resp = None
        for attempt in range(1, _MAX_RETRIES + 1):
            self._throttle()
            try:
                resp = httpx.get(url, **kwargs)
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", _BACKOFF_BASE * attempt))
                    logger.warning("Rate limited (429) on %s, backing off %.1fs (attempt %d/%d)", url, retry_after, attempt, _MAX_RETRIES)
                    time.sleep(retry_after)
                    self._min_interval = min(self._min_interval * 2, 30.0)
                    continue
                if resp.status_code >= 500 and attempt < _MAX_RETRIES:
                    wait = _BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.debug("Server error %d, retrying in %.1fs", resp.status_code, wait)
                    time.sleep(wait)
                    continue
                return resp
            except httpx.TimeoutException:
                if attempt < _MAX_RETRIES:
                    logger.debug("Timeout on attempt %d, retrying", attempt)
                    continue
                raise

        return resp
