"""Per-repository rate limiter for the PR bot webhook handler.

Fork-author PRs arrive under the victim repo's webhook, so a single bad
actor could spam synchronize events and force us to repeatedly re-render
the sticky comment. We cap each repository's webhook processing at N
events per rolling window; events above the cap are dropped silently
and counted for observability.

In-memory only. Fine for a single replica and drops cleanly across
replicas because the bucket is keyed by (owner, repo) — duplicate
events in a multi-replica world are safe to process independently.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict


class PerRepoRateLimiter:
    def __init__(self, max_events: int = 30, window_seconds: int = 60) -> None:
        self._max = max_events
        self._window = window_seconds
        self._hits: dict[tuple[str, str], list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self.dropped: dict[tuple[str, str], int] = defaultdict(int)

    def allow(self, owner: str, repo: str) -> bool:
        key = (owner.lower(), repo.lower())
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            recent = [t for t in self._hits[key] if t > cutoff]
            if len(recent) >= self._max:
                self._hits[key] = recent
                self.dropped[key] += 1
                return False
            recent.append(now)
            self._hits[key] = recent
            return True
