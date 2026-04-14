"""
GARL Protocol Python SDK v5 — Sovereign Trust Layer

Four integration levels:

1. One-liner (simplest):
    import garl
    garl.init("garl_key", "agent-uuid")
    r = garl.log_action("Generated REST API", "success",
                         category="coding", background=False)
    # r["receipt_url"] -> "https://garl.ai/r/a8f3c2d1"  (shareable)

2. Client (full control):
    from garl import GarlClient
    client = GarlClient("garl_key", "agent-uuid")
    cert = client.verify(status="success", task="...", duration_ms=1250)

3. Proactive Guard (auto-blocks unsafe delegation):
    from garl import GarlClient
    client = GarlClient("garl_key", "agent-uuid")
    if client.should_delegate("target-uuid"):
        delegate_to(target)

4. Async:
    from garl import AsyncGarlClient
    client = AsyncGarlClient("garl_key", "agent-uuid")
    cert = await client.verify(status="success", task="...", duration_ms=1250)
"""

import time
import threading
import logging
from typing import Literal
import httpx

logger = logging.getLogger("garl")

# Retry: 3 attempts, exponential backoff (1s, 2s, 4s), only on 5xx errors
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # seconds


def _retry_request(fn, *args, **kwargs):
    """Execute HTTP request with exponential backoff on 5xx and connection errors."""
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
            last_exc = e
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code < 500:
                raise
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                time.sleep(wait)
    raise last_exc


# ──────────────────────────────────────────────
#  Module-level one-liner API
# ──────────────────────────────────────────────

_default_client: "GarlClient | None" = None


def init(api_key: str, agent_id: str, base_url: str = "https://api.garl.ai/api/v1"):
    """Initialize the global GARL client for one-liner usage."""
    global _default_client
    _default_client = GarlClient(api_key, agent_id, base_url)


def log_action(
    task: str,
    result: str = "success",
    category: str = "other",
    duration_ms: int | None = None,
    cost_usd: float | None = None,
    token_count: int | None = None,
    tool_calls: list[dict] | None = None,
    proof_of_result: dict | None = None,
    background: bool = True,
) -> dict | None:
    """
    Log an agent action to GARL in one line.

    Runs in background (non-blocking) by default.
    Use background=False to run synchronously and return the certificate.
    The returned dict includes a ``receipt_url`` — a public shareable
    page (https://garl.ai/r/{short}) with an ECDSA-signed proof card.

    Usage:
        r = garl.log_action("Generated API docs", "success",
                             category="coding", background=False)
        print(r["receipt_url"])
    """
    if not _default_client:
        logger.warning("GARL not initialized. Call garl.init() first.")
        return None

    if background:
        t = threading.Thread(
            target=_log_action_sync,
            args=(task, result, category, duration_ms, cost_usd, token_count, tool_calls, proof_of_result),
            daemon=True,
        )
        t.start()
        return None

    return _log_action_sync(task, result, category, duration_ms, cost_usd, token_count, tool_calls, proof_of_result)


def _log_action_sync(task, result, category, duration_ms, cost_usd, token_count, tool_calls, proof_of_result):
    try:
        return _default_client.verify(
            status=result,
            task=task,
            duration_ms=duration_ms or 0,
            category=category,
            cost_usd=cost_usd,
            token_count=token_count,
            tool_calls=tool_calls,
            proof_of_result=proof_of_result,
        )
    except Exception as e:
        logger.warning("GARL log_action failed: %s", e)
        return None


def is_trusted(
    target_agent_id: str,
    min_score: float = 50.0,
    require_verified: bool = False,
) -> dict:
    """
    Query a target agent's trust status. Used for the Trust Gate pattern.

    Returns dict:
      - trusted (bool): whether the agent is trusted
      - score (float): trust score (0 if not registered)
      - registered (bool): whether registered on GARL
      - recommendation (str): trusted|caution|unknown etc.
      - reason (str): short explanation
    """
    if not _default_client:
        logger.warning("GARL not initialized. Call garl.init() first.")
        return {"trusted": False, "score": 0, "registered": False, "recommendation": "unknown", "reason": "GARL client not initialized"}

    return _default_client.is_trusted(target_agent_id, min_score, require_verified)


def require_trust(min_score: float = 50.0, mode: str = "warn"):
    """
    Decorator: the function's first argument must be target_agent_id.

    mode="warn": logs a warning but executes the function
    mode="block": blocks execution if untrusted, returns None

    Usage:
        @garl.require_trust(min_score=60, mode="warn")
        def delegate_task(target_agent_id, task):
            ...
    """
    import functools

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(target_agent_id, *args, **kwargs):
            result = is_trusted(target_agent_id, min_score)
            if not result["trusted"]:
                msg = (
                    f"Warning: Target agent {target_agent_id} is not verified on GARL. "
                    f"Delegation is risky. Register at https://garl.ai — "
                    f"Reason: {result['reason']}"
                )
                if mode == "block":
                    logger.warning(msg + " — Delegation BLOCKED.")
                    return None
                logger.warning(msg)
            return fn(target_agent_id, *args, **kwargs)
        return wrapper
    return decorator


# ──────────────────────────────────────────────
#  Synchronous Client
# ──────────────────────────────────────────────

class GarlClient:
    """GARL Protocol v1.0 Sovereign Trust Layer synchronous client."""

    def __init__(
        self,
        api_key: str,
        agent_id: str,
        base_url: str = "https://api.garl.ai/api/v1",
    ):
        self.api_key = api_key
        self.agent_id = agent_id
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"x-api-key": self.api_key, "Content-Type": "application/json"},
            timeout=30.0,
        )

    def verify(
        self,
        status: Literal["success", "failure", "partial"],
        task: str,
        duration_ms: int,
        category: str = "other",
        input_summary: str = "",
        output_summary: str = "",
        metadata: dict | None = None,
        runtime_env: str = "",
        tool_calls: list[dict] | None = None,
        cost_usd: float | None = None,
        token_count: int | None = None,
        proof_of_result: dict | None = None,
        pii_mask: bool = False,
    ) -> dict:
        """Submit an execution trace and receive a signed certificate.

        The returned dict includes ``receipt_url`` — a public shareable page
        (e.g. ``https://garl.ai/r/a8f3c2d1``) rendering a cryptographic proof
        card with Open Graph preview for Slack/Twitter/GitHub.

        Use pii_mask=True for enterprise PII protection (hashes input/output
        summaries).
        """
        payload = {
            "agent_id": self.agent_id,
            "task_description": task,
            "status": status,
            "duration_ms": duration_ms,
            "category": category,
            "input_summary": input_summary,
            "output_summary": output_summary,
            "metadata": metadata or {},
            "runtime_env": runtime_env,
            "pii_mask": pii_mask,
        }
        if tool_calls:
            payload["tool_calls"] = tool_calls
        if cost_usd is not None:
            payload["cost_usd"] = cost_usd
        if token_count is not None:
            payload["token_count"] = token_count
        if proof_of_result is not None:
            payload["proof_of_result"] = proof_of_result

        resp = _retry_request(self._client.post, "/verify", json=payload)
        resp.raise_for_status()
        return resp.json()

    def verify_batch(self, traces: list[dict]) -> dict:
        """Submit up to 50 traces in a single request."""
        for t in traces:
            t.setdefault("agent_id", self.agent_id)
        resp = _retry_request(self._client.post, "/verify/batch", json={"traces": traces})
        resp.raise_for_status()
        return resp.json()

    def get_history(self, limit: int = 50) -> list[dict]:
        """Return trust score history over time."""
        resp = self._client.get(f"/agents/{self.agent_id}/history", params={"limit": limit})
        resp.raise_for_status()
        return resp.json()

    def check_trust(self, target_agent_id: str) -> dict:
        """A2A: Verify another agent's trustworthiness before delegation."""
        resp = _retry_request(self._client.get, f"/trust/verify?agent_id={target_agent_id}")
        resp.raise_for_status()
        return resp.json()

    def is_trusted(
        self,
        target_agent_id: str,
        min_score: float = 50.0,
        require_verified: bool = False,
    ) -> dict:
        """
        Trust Gate: check whether a target agent has a sufficient trust score.

        Returns dict: trusted, score, registered, recommendation, reason
        """
        try:
            data = self.check_trust(target_agent_id)
        except Exception as e:
            return {
                "trusted": False, "score": 0, "registered": False,
                "recommendation": "unknown",
                "reason": f"Trust check failed: {e}",
            }

        if not data.get("registered", True):
            return {
                "trusted": False, "score": 0, "registered": False,
                "recommendation": "unknown",
                "reason": "Agent not registered on GARL",
            }

        score = data.get("trust_score", 0)
        verified = data.get("verified", False)
        recommendation = data.get("recommendation", "unknown")

        if score < min_score:
            return {
                "trusted": False, "score": score, "registered": True,
                "recommendation": recommendation,
                "reason": f"Trust score {score:.1f} below threshold {min_score}",
            }

        if require_verified and not verified:
            return {
                "trusted": False, "score": score, "registered": True,
                "recommendation": recommendation,
                "reason": "Agent not verified (requires 10+ traces)",
            }

        return {
            "trusted": True, "score": score, "registered": True,
            "recommendation": recommendation,
            "reason": "Agent meets trust requirements",
        }

    def get_agent_card(self, target_agent_id: str | None = None) -> dict:
        """Retrieve the Agent Card with trust profile and capabilities."""
        aid = target_agent_id or self.agent_id
        resp = self._client.get(f"/agents/{aid}/card")
        resp.raise_for_status()
        return resp.json()

    def get_score(self) -> dict:
        """Retrieve the current agent profile."""
        resp = self._client.get(f"/agents/{self.agent_id}")
        resp.raise_for_status()
        return resp.json()

    def get_detail(self) -> dict:
        """Retrieve full agent detail with traces, history and decay projection."""
        resp = self._client.get(f"/agents/{self.agent_id}/detail")
        resp.raise_for_status()
        return resp.json()

    def compare_with(self, *agent_ids: str) -> list[dict]:
        """Compare this agent side-by-side with others."""
        all_ids = [self.agent_id] + list(agent_ids)
        resp = self._client.get(f"/compare?agents={','.join(all_ids)}")
        resp.raise_for_status()
        return resp.json()

    def register_webhook(self, url: str, events: list[str] | None = None) -> dict:
        """Register a webhook for score changes, milestones, and anomalies."""
        payload = {
            "agent_id": self.agent_id,
            "url": url,
            "events": events or ["trace_recorded", "milestone", "anomaly"],
        }
        resp = self._client.post("/webhooks", json=payload)
        resp.raise_for_status()
        return resp.json()

    def list_webhooks(self) -> list[dict]:
        """List all webhooks for this agent."""
        resp = self._client.get(f"/webhooks/{self.agent_id}")
        resp.raise_for_status()
        return resp.json()

    def update_webhook(self, webhook_id: str, is_active: bool | None = None,
                       url: str | None = None, events: list[str] | None = None) -> dict:
        """Update a webhook (active/inactive, URL, or event changes)."""
        payload = {}
        if is_active is not None:
            payload["is_active"] = is_active
        if url is not None:
            payload["url"] = url
        if events is not None:
            payload["events"] = events
        resp = self._client.patch(f"/webhooks/{self.agent_id}/{webhook_id}", json=payload)
        resp.raise_for_status()
        return resp.json()

    def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook."""
        resp = self._client.delete(f"/webhooks/{self.agent_id}/{webhook_id}")
        resp.raise_for_status()
        return True

    def search(self, query: str = "", category: str | None = None, limit: int = 10) -> list[dict]:
        """Search agents by name, description, or category."""
        params = {"q": query, "limit": limit}
        if category:
            params["category"] = category
        resp = self._client.get("/search", params=params)
        resp.raise_for_status()
        result = resp.json()
        return result.get("data", result) if isinstance(result, dict) else result

    def find_trusted_agent(self, category: str = "other", min_score: float = 65.0) -> dict | None:
        """Find the most trusted agent in a category above the minimum score."""
        agents = self.search(category=category, limit=5)
        for agent in agents:
            if float(agent.get("trust_score", 0)) >= min_score:
                return agent
        return None

    def should_delegate(
        self,
        target_agent_id: str,
        min_score: float = 60.0,
        require_verified: bool = True,
        block_anomalies: bool = True,
        block_bronze: bool = True,
        min_tier: str = "silver",
    ) -> bool:
        """Proactive delegation guard — automatically blocks unsafe targets.

        Returns True when all criteria are met:
        - Trust score >= min_score (default 60)
        - Verified (>= 10 traces) if require_verified is True
        - No active anomaly flags if block_anomalies is True
        - Risk level is not 'critical' or 'high'
        - Certification tier >= min_tier (default silver); bronze is blocked by default

        Usage:
            if client.should_delegate("target-uuid"):
                result = delegate_to(target)
            else:
                logger.warning("Delegation blocked by GARL trust guard")
        """
        tier_order = ["bronze", "silver", "gold", "enterprise"]
        min_tier_idx = tier_order.index(min_tier) if min_tier in tier_order else 1

        try:
            trust = self.check_trust(target_agent_id)
        except Exception as e:
            logger.warning("GARL trust check failed for %s: %s — delegation blocked",
                          target_agent_id, e)
            return False

        score = float(trust.get("trust_score", 0))
        if score < min_score:
            logger.info("GARL guard: %s blocked (score %.1f < %.1f)", target_agent_id, score, min_score)
            return False

        if require_verified and not trust.get("verified", False):
            logger.info("GARL guard: %s blocked (unverified)", target_agent_id)
            return False

        if block_anomalies and len(trust.get("anomalies", [])) > 0:
            tier = trust.get("certification_tier", "bronze")
            logger.info("GARL guard: %s blocked (active anomalies, tier=%s)", target_agent_id, tier)
            return False

        risk = trust.get("risk_level", "unknown")
        if risk in ("critical", "high"):
            tier = trust.get("certification_tier", "bronze")
            logger.info("GARL guard: %s blocked (risk_level=%s, tier=%s)", target_agent_id, risk, tier)
            return False

        # Certification tier check (bronze blocked by default)
        target_tier = trust.get("certification_tier", "bronze")
        target_tier_idx = tier_order.index(target_tier) if target_tier in tier_order else 0
        if block_bronze and target_tier == "bronze":
            logger.info("GARL guard: %s blocked (tier=bronze, min_tier=%s)", target_agent_id, min_tier)
            return False
        if target_tier_idx < min_tier_idx:
            logger.info("GARL guard: %s blocked (tier=%s < min_tier=%s)", target_agent_id, target_tier, min_tier)
            return False

        logger.info("GARL guard: %s eligible for delegation (score=%.1f, tier=%s)", target_agent_id, score, target_tier)
        return True

    def get_delegation_report(self, target_agent_id: str) -> dict:
        """Full delegation analysis with actionable recommendation."""
        trust = self.check_trust(target_agent_id)
        return {
            "agent_id": target_agent_id,
            "name": trust.get("name", "Unknown"),
            "trust_score": trust.get("trust_score", 0),
            "recommendation": trust.get("recommendation", "unknown"),
            "risk_level": trust.get("risk_level", "unknown"),
            "certification_tier": trust.get("certification_tier", "bronze"),
            "safe_for_general": trust.get("recommendation") in ("trusted", "trusted_with_monitoring"),
            "safe_for_sensitive": trust.get("recommendation") == "trusted",
            "has_anomalies": len(trust.get("anomalies", [])) > 0,
            "dimensions": trust.get("dimensions", {}),
            "last_active": trust.get("last_active"),
        }

    def endorse(self, target_agent_id: str, context: str = "") -> dict:
        """Endorse another agent (A2A reputation transfer)."""
        payload = {"target_agent_id": target_agent_id, "context": context}
        resp = self._client.post("/endorse", json=payload)
        resp.raise_for_status()
        return resp.json()

    def get_endorsements(self, agent_id: str | None = None) -> dict:
        """Retrieve endorsements for an agent."""
        aid = agent_id or self.agent_id
        resp = self._client.get(f"/endorsements/{aid}")
        resp.raise_for_status()
        return resp.json()

    def track(self, task: str, category: str = "other", cost_usd: float | None = None):
        """Context manager that automatically reports duration and status."""
        return _TrackedExecution(self, task, category, cost_usd)

    # ─── v1.0 Sovereign Trust Layer new methods ───

    def route(self, category: str, min_tier: str = "silver", limit: int = 3) -> dict:
        """GET /api/v1/trust/route — Recommend most trusted agents by category and tier filter."""
        params = {"category": category, "min_tier": min_tier, "limit": limit}
        resp = self._client.get("/trust/route", params=params)
        resp.raise_for_status()
        return resp.json()

    def find_best_agent(self, category: str, min_tier: str = "silver") -> dict | None:
        """Call route() and return the best match."""
        result = self.route(category, min_tier=min_tier, limit=3)
        recs = result.get("recommendations", [])
        return recs[0] if recs else None

    def soft_delete(self, confirmation: str = "DELETE_CONFIRMED") -> dict:
        """DELETE /api/v1/agents/{agent_id} — GDPR compliant soft delete."""
        if confirmation != "DELETE_CONFIRMED":
            raise ValueError("confirmation must be 'DELETE_CONFIRMED'")
        resp = self._client.delete(f"/agents/{self.agent_id}", json={"confirmation": confirmation})
        resp.raise_for_status()
        return resp.json()

    def anonymize(self, confirmation: str = "ANONYMIZE_CONFIRMED") -> dict:
        """POST /api/v1/agents/{agent_id}/anonymize — GDPR compliant anonymization."""
        if confirmation != "ANONYMIZE_CONFIRMED":
            raise ValueError("confirmation must be 'ANONYMIZE_CONFIRMED'")
        resp = self._client.post(f"/agents/{self.agent_id}/anonymize", json={"confirmation": confirmation})
        resp.raise_for_status()
        return resp.json()

    def get_compliance(self, agent_id: str | None = None) -> dict:
        """GET /api/v1/agents/{agent_id}/compliance — Enterprise compliance report."""
        aid = agent_id or self.agent_id
        resp = self._client.get(f"/agents/{aid}/compliance")
        resp.raise_for_status()
        return resp.json()

    def get_sovereign_id(self) -> str | None:
        """Return the agent's DID via get_score()."""
        score = self.get_score()
        return score.get("sovereign_id")

    def get_tier(self) -> str:
        """Return the agent's certification tier via get_score()."""
        score = self.get_score()
        return score.get("certification_tier", "bronze")

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def heartbeat(
        self,
        interval_seconds: int = 300,
        category: str = "other",
    ) -> threading.Thread:
        """Start a background heartbeat that sends periodic 'alive' traces.

        Args:
            interval_seconds: seconds between heartbeats (default 300 = 5 min)
            category: task category for heartbeat traces

        Returns:
            The background daemon thread (stops when main process exits).
        """
        self._heartbeat_active = True

        def _loop():
            while getattr(self, "_heartbeat_active", False):
                try:
                    self.verify(
                        status="success",
                        task="heartbeat",
                        duration_ms=0,
                        category=category,
                    )
                except Exception:
                    pass
                time.sleep(interval_seconds)

        t = threading.Thread(target=_loop, daemon=True)
        t.start()
        logger.info("GARL heartbeat started (interval=%ds)", interval_seconds)
        return t

    def stop_heartbeat(self):
        """Stop the background heartbeat loop."""
        self._heartbeat_active = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop_heartbeat()
        self.close()


# ──────────────────────────────────────────────
#  Async Client
# ──────────────────────────────────────────────

class AsyncGarlClient:
    """Async version of GarlClient using httpx.AsyncClient."""

    def __init__(
        self,
        api_key: str,
        agent_id: str,
        base_url: str = "https://api.garl.ai/api/v1",
    ):
        self.api_key = api_key
        self.agent_id = agent_id
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"x-api-key": self.api_key, "Content-Type": "application/json"},
            timeout=30.0,
        )

    async def _retry(self, fn, *args, **kwargs):
        """Async retry on 5xx and connection errors."""
        import asyncio
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                return await fn(*args, **kwargs)
            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
                last_exc = e
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code < 500:
                    raise
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                    await asyncio.sleep(wait)
        raise last_exc

    async def verify(
        self,
        status: Literal["success", "failure", "partial"],
        task: str,
        duration_ms: int,
        category: str = "other",
        input_summary: str = "",
        output_summary: str = "",
        metadata: dict | None = None,
        runtime_env: str = "",
        tool_calls: list[dict] | None = None,
        cost_usd: float | None = None,
        token_count: int | None = None,
        proof_of_result: dict | None = None,
        pii_mask: bool = False,
    ) -> dict:
        """Submit an execution trace asynchronously."""
        payload = {
            "agent_id": self.agent_id,
            "task_description": task,
            "status": status,
            "duration_ms": duration_ms,
            "category": category,
            "input_summary": input_summary,
            "output_summary": output_summary,
            "metadata": metadata or {},
            "runtime_env": runtime_env,
            "pii_mask": pii_mask,
        }
        if tool_calls:
            payload["tool_calls"] = tool_calls
        if cost_usd is not None:
            payload["cost_usd"] = cost_usd
        if token_count is not None:
            payload["token_count"] = token_count
        if proof_of_result is not None:
            payload["proof_of_result"] = proof_of_result

        resp = await self._retry(self._client.post, "/verify", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def verify_batch(self, traces: list[dict]) -> dict:
        """Submit up to 50 traces in a single request."""
        for t in traces:
            t.setdefault("agent_id", self.agent_id)
        resp = await self._retry(self._client.post, "/verify/batch", json={"traces": traces})
        resp.raise_for_status()
        return resp.json()

    async def get_history(self, limit: int = 50) -> list[dict]:
        """Return trust score history over time."""
        resp = await self._client.get(f"/agents/{self.agent_id}/history", params={"limit": limit})
        resp.raise_for_status()
        return resp.json()

    async def check_trust(self, target_agent_id: str) -> dict:
        """A2A: Asynchronously verify another agent's trustworthiness."""
        resp = await self._retry(self._client.get, f"/trust/verify?agent_id={target_agent_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_agent_card(self, target_agent_id: str | None = None) -> dict:
        """Retrieve the Agent Card."""
        aid = target_agent_id or self.agent_id
        resp = await self._client.get(f"/agents/{aid}/card")
        resp.raise_for_status()
        return resp.json()

    async def get_score(self) -> dict:
        """Retrieve the current agent profile."""
        resp = await self._client.get(f"/agents/{self.agent_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_detail(self) -> dict:
        """Retrieve full agent detail."""
        resp = await self._client.get(f"/agents/{self.agent_id}/detail")
        resp.raise_for_status()
        return resp.json()

    async def compare_with(self, *agent_ids: str) -> list[dict]:
        """Compare this agent with others."""
        all_ids = [self.agent_id] + list(agent_ids)
        resp = await self._client.get(f"/compare?agents={','.join(all_ids)}")
        resp.raise_for_status()
        return resp.json()

    async def register_webhook(self, url: str, events: list[str] | None = None) -> dict:
        """Register a webhook."""
        payload = {
            "agent_id": self.agent_id,
            "url": url,
            "events": events or ["trace_recorded", "milestone", "anomaly"],
        }
        resp = await self._client.post("/webhooks", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def list_webhooks(self) -> list[dict]:
        """List all webhooks."""
        resp = await self._client.get(f"/webhooks/{self.agent_id}")
        resp.raise_for_status()
        return resp.json()

    async def update_webhook(self, webhook_id: str, is_active: bool | None = None,
                             url: str | None = None, events: list[str] | None = None) -> dict:
        """Update a webhook."""
        payload = {}
        if is_active is not None:
            payload["is_active"] = is_active
        if url is not None:
            payload["url"] = url
        if events is not None:
            payload["events"] = events
        resp = await self._client.patch(f"/webhooks/{self.agent_id}/{webhook_id}", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook."""
        resp = await self._client.delete(f"/webhooks/{self.agent_id}/{webhook_id}")
        resp.raise_for_status()
        return True

    async def search(self, query: str = "", category: str | None = None, limit: int = 10) -> list[dict]:
        """Search agents by name, description, or category."""
        params = {"q": query, "limit": limit}
        if category:
            params["category"] = category
        resp = await self._client.get("/search", params=params)
        resp.raise_for_status()
        result = resp.json()
        return result.get("data", result) if isinstance(result, dict) else result

    async def find_trusted_agent(self, category: str = "other", min_score: float = 65.0) -> dict | None:
        """Find the most trusted agent in a category."""
        agents = await self.search(category=category, limit=5)
        for agent in agents:
            if float(agent.get("trust_score", 0)) >= min_score:
                return agent
        return None

    async def should_delegate(
        self,
        target_agent_id: str,
        min_score: float = 60.0,
        require_verified: bool = True,
        block_anomalies: bool = True,
        block_bronze: bool = True,
        min_tier: str = "silver",
    ) -> bool:
        """Proactive delegation guard (async)."""
        tier_order = ["bronze", "silver", "gold", "enterprise"]
        min_tier_idx = tier_order.index(min_tier) if min_tier in tier_order else 1

        try:
            trust = await self.check_trust(target_agent_id)
        except Exception as e:
            logger.warning("GARL trust check failed for %s: %s — delegation blocked",
                          target_agent_id, e)
            return False

        score = float(trust.get("trust_score", 0))
        if score < min_score:
            logger.info("GARL guard: %s blocked (score %.1f < %.1f)", target_agent_id, score, min_score)
            return False

        if require_verified and not trust.get("verified", False):
            logger.info("GARL guard: %s blocked (unverified)", target_agent_id)
            return False

        if block_anomalies and len(trust.get("anomalies", [])) > 0:
            tier = trust.get("certification_tier", "bronze")
            logger.info("GARL guard: %s blocked (active anomalies, tier=%s)", target_agent_id, tier)
            return False

        risk = trust.get("risk_level", "unknown")
        if risk in ("critical", "high"):
            tier = trust.get("certification_tier", "bronze")
            logger.info("GARL guard: %s blocked (risk_level=%s, tier=%s)", target_agent_id, risk, tier)
            return False

        target_tier = trust.get("certification_tier", "bronze")
        target_tier_idx = tier_order.index(target_tier) if target_tier in tier_order else 0
        if block_bronze and target_tier == "bronze":
            logger.info("GARL guard: %s blocked (tier=bronze, min_tier=%s)", target_agent_id, min_tier)
            return False
        if target_tier_idx < min_tier_idx:
            logger.info("GARL guard: %s blocked (tier=%s < min_tier=%s)", target_agent_id, target_tier, min_tier)
            return False

        logger.info("GARL guard: %s eligible for delegation (score=%.1f, tier=%s)", target_agent_id, score, target_tier)
        return True

    async def get_delegation_report(self, target_agent_id: str) -> dict:
        """Full delegation analysis."""
        trust = await self.check_trust(target_agent_id)
        return {
            "agent_id": target_agent_id,
            "name": trust.get("name", "Unknown"),
            "trust_score": trust.get("trust_score", 0),
            "recommendation": trust.get("recommendation", "unknown"),
            "risk_level": trust.get("risk_level", "unknown"),
            "certification_tier": trust.get("certification_tier", "bronze"),
            "safe_for_general": trust.get("recommendation") in ("trusted", "trusted_with_monitoring"),
            "safe_for_sensitive": trust.get("recommendation") == "trusted",
            "has_anomalies": len(trust.get("anomalies", [])) > 0,
            "dimensions": trust.get("dimensions", {}),
            "last_active": trust.get("last_active"),
        }

    async def endorse(self, target_agent_id: str, context: str = "") -> dict:
        """Endorse another agent."""
        payload = {"target_agent_id": target_agent_id, "context": context}
        resp = await self._client.post("/endorse", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def get_endorsements(self, agent_id: str | None = None) -> dict:
        """Retrieve endorsements."""
        aid = agent_id or self.agent_id
        resp = await self._client.get(f"/endorsements/{aid}")
        resp.raise_for_status()
        return resp.json()

    async def route(self, category: str, min_tier: str = "silver", limit: int = 3) -> dict:
        """Route by category and tier."""
        params = {"category": category, "min_tier": min_tier, "limit": limit}
        resp = await self._client.get("/trust/route", params=params)
        resp.raise_for_status()
        return resp.json()

    async def find_best_agent(self, category: str, min_tier: str = "silver") -> dict | None:
        """Find the best agent."""
        result = await self.route(category, min_tier=min_tier, limit=3)
        recs = result.get("recommendations", [])
        return recs[0] if recs else None

    async def soft_delete(self, confirmation: str = "DELETE_CONFIRMED") -> dict:
        """GDPR soft delete."""
        if confirmation != "DELETE_CONFIRMED":
            raise ValueError("confirmation must be 'DELETE_CONFIRMED'")
        resp = await self._client.delete(f"/agents/{self.agent_id}", json={"confirmation": confirmation})
        resp.raise_for_status()
        return resp.json()

    async def anonymize(self, confirmation: str = "ANONYMIZE_CONFIRMED") -> dict:
        """GDPR anonymization."""
        if confirmation != "ANONYMIZE_CONFIRMED":
            raise ValueError("confirmation must be 'ANONYMIZE_CONFIRMED'")
        resp = await self._client.post(f"/agents/{self.agent_id}/anonymize", json={"confirmation": confirmation})
        resp.raise_for_status()
        return resp.json()

    async def get_compliance(self, agent_id: str | None = None) -> dict:
        """Retrieve compliance report."""
        aid = agent_id or self.agent_id
        resp = await self._client.get(f"/agents/{aid}/compliance")
        resp.raise_for_status()
        return resp.json()

    async def get_sovereign_id(self) -> str | None:
        """Return the agent's DID."""
        score = await self.get_score()
        return score.get("sovereign_id")

    async def get_tier(self) -> str:
        """Return the agent's certification tier."""
        score = await self.get_score()
        return score.get("certification_tier", "bronze")

    async def track(self, task: str, fn, category: str = "other", cost_usd: float | None = None):
        """Automatically track an async function's execution."""
        start = time.time()
        status = "success"
        result = None
        cert = None
        try:
            result = await fn()
        except Exception:
            status = "failure"
            raise
        finally:
            elapsed = int((time.time() - start) * 1000)
            cert = await self.verify(status=status, task=task, duration_ms=elapsed, category=category, cost_usd=cost_usd)
        if status == "success":
            return {"result": result, "certificate": cert}

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()


# ──────────────────────────────────────────────
#  Context Manager
# ──────────────────────────────────────────────

class _TrackedExecution:
    """Context manager that automatically reports duration and status."""

    def __init__(self, client: GarlClient, task: str, category: str, cost_usd: float | None):
        self.client = client
        self.task = task
        self.category = category
        self.cost_usd = cost_usd
        self._start: float = 0
        self.certificate: dict | None = None

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = int((time.time() - self._start) * 1000)
        status = "failure" if exc_type else "success"
        self.certificate = self.client.verify(
            status=status,
            task=self.task,
            duration_ms=elapsed,
            category=self.category,
            cost_usd=self.cost_usd,
        )
        return False


# ──────────────────────────────────────────────
#  OpenClaw Adapter
# ──────────────────────────────────────────────

class OpenClawAdapter:
    """Adapter for OpenClaw agents — automatic trace reporting + trust-gated delegation."""

    def __init__(self, api_key: str, agent_id: str, base_url: str = "https://api.garl.ai/api/v1"):
        self.client = GarlClient(api_key, agent_id, base_url)
        self.agent_id = agent_id

    def report_task(self, message: str, duration_ms: int = 0, status: str = "success",
                    channel: str | None = None, session_id: str | None = None,
                    tool_calls: list[dict] | None = None, cost_usd: float | None = None,
                    category: str = "") -> dict:
        """Convert an OpenClaw task completion event into a GARL trace."""
        payload = {
            "agent_id": self.agent_id, "message": message, "status": status,
            "duration_ms": duration_ms, "category": category, "runtime_env": "openclaw",
            "channel": channel, "session_id": session_id,
        }
        if tool_calls:
            payload["tool_calls"] = tool_calls
        if cost_usd is not None:
            payload["usage"] = {"cost_usd": cost_usd}
        resp = self.client._client.post("/ingest/openclaw", json=payload)
        resp.raise_for_status()
        return resp.json()

    def should_delegate(self, target_agent_id: str, min_score: float = 50.0,
                        require_verified: bool = False, block_anomalies: bool = False) -> bool:
        """Trust-gated delegation decision."""
        try:
            trust = self.client.check_trust(target_agent_id)
        except Exception:
            return False
        score = float(trust.get("trust_score", 0))
        if score < min_score:
            return False
        if require_verified and not trust.get("verified", False):
            return False
        if block_anomalies and len(trust.get("anomalies", [])) > 0:
            return False
        # Bronze tier blocked by default

        tier = trust.get("certification_tier", "bronze")
        if tier == "bronze":
            return False
        return True

    def get_delegation_recommendation(self, target_agent_id: str) -> dict:
        """Detailed delegation recommendation."""
        trust = self.client.check_trust(target_agent_id)
        return {
            "agent_id": target_agent_id,
            "name": trust.get("name", "Unknown"),
            "score": trust.get("trust_score", 0),
            "recommendation": trust.get("recommendation", "unknown"),
            "risk_level": trust.get("risk_level", "unknown"),
            "certification_tier": trust.get("certification_tier", "bronze"),
            "safe_for_general": trust.get("recommendation") in ("trusted", "trusted_with_monitoring"),
            "safe_for_sensitive": trust.get("recommendation") == "trusted",
            "has_anomalies": len(trust.get("anomalies", [])) > 0,
            "dimensions": trust.get("dimensions", {}),
        }

    def find_best_agent_for(self, category: str, min_score: float = 65.0) -> dict | None:
        """Find the best agent in a category (legacy API compatibility)."""
        return self.client.find_trusted_agent(category, min_score)

    def route(self, category: str, min_tier: str = "silver", limit: int = 3) -> dict:
        """GET /api/v1/trust/route — Recommend most trusted agents by category and tier."""
        return self.client.route(category, min_tier=min_tier, limit=limit)

    def find_best_agent(self, category: str, min_tier: str = "silver") -> dict | None:
        """Call route() and return the best match."""
        return self.client.find_best_agent(category, min_tier=min_tier)

    def close(self):
        """Close the client connection."""
        self.client.close()
