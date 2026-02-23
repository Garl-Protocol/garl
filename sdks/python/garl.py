"""
GARL Protocol Python SDK v5 — Sovereign Trust Layer

Dört entegrasyon seviyesi:

1. Tek satır (en basit):
    import garl
    garl.init("garl_key", "agent-uuid")
    garl.log_action("Generated REST API", "success", category="coding")

2. İstemci (tam kontrol):
    from garl import GarlClient
    client = GarlClient("garl_key", "agent-uuid")
    cert = client.verify(status="success", task="...", duration_ms=1250)

3. Proaktif Koruma (güvensiz delegasyonu otomatik engeller):
    from garl import GarlClient
    client = GarlClient("garl_key", "agent-uuid")
    if client.should_delegate("target-uuid"):  # trust + anomali + tier kontrolü
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

# Yeniden deneme: 3 deneme, üstel geri çekilme (1s, 2s, 4s), sadece 5xx hatalarında
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # saniye


def _retry_request(fn, *args, **kwargs):
    """5xx ve bağlantı hatalarında üstel geri çekilme ile HTTP isteği yürütür."""
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
#  Modül seviyesi tek satır API
# ──────────────────────────────────────────────

_default_client: "GarlClient | None" = None


def init(api_key: str, agent_id: str, base_url: str = "https://api.garl.ai/api/v1"):
    """Tek satır kullanım için global GARL istemcisini başlatır."""
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
    Tek satırda GARL'a ajan aksiyonu kaydeder.

    Varsayılan olarak arka planda (bloklamadan) çalışır.
    background=False ile senkron çalıştırır ve sertifika döner.

    Kullanım:
        garl.log_action("Generated API docs", "success", category="coding")
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
    Hedef ajanın güven durumunu sorgular. Trust Gate kalıbı için kullanılır.

    Dönen dict:
      - trusted (bool): ajanın güvenilir olup olmadığı
      - score (float): güven puanı (kayıtlı değilse 0)
      - registered (bool): GARL'da kayıtlı mı
      - recommendation (str): trusted|caution|unknown vb.
      - reason (str): kısa açıklama
    """
    if not _default_client:
        logger.warning("GARL not initialized. Call garl.init() first.")
        return {"trusted": False, "score": 0, "registered": False, "recommendation": "unknown", "reason": "GARL client not initialized"}

    return _default_client.is_trusted(target_agent_id, min_score, require_verified)


def require_trust(min_score: float = 50.0, mode: str = "warn"):
    """
    Dekoratör: fonksiyonun ilk argümanı target_agent_id olmalıdır.

    mode="warn": uyarı loglar ama fonksiyonu çalıştırır
    mode="block": güvensizse fonksiyonu çalıştırmaz, None döner

    Kullanım:
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
#  Senkron İstemci
# ──────────────────────────────────────────────

class GarlClient:
    """GARL Protocol v1.0 Sovereign Trust Layer senkron istemcisi."""

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
        """Yürütme izini gönderir ve imzalı sertifika alır.
        Enterprise PII koruması için pii_mask=True kullanın (input/output özetlerini hash'ler)."""
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
        """Tek istekte en fazla 50 iz gönderir."""
        for t in traces:
            t.setdefault("agent_id", self.agent_id)
        resp = _retry_request(self._client.post, "/verify/batch", json={"traces": traces})
        resp.raise_for_status()
        return resp.json()

    def get_history(self, limit: int = 50) -> list[dict]:
        """Zaman içinde güven skoru geçmişini döner."""
        resp = self._client.get(f"/agents/{self.agent_id}/history", params={"limit": limit})
        resp.raise_for_status()
        return resp.json()

    def check_trust(self, target_agent_id: str) -> dict:
        """A2A: Delegasyondan önce başka bir ajanın güvenilirliğini doğrular."""
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
        Trust Gate: hedef ajanın yeterli güven puanına sahip olup olmadığını kontrol eder.

        Dönen dict: trusted, score, registered, recommendation, reason
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
        """Güven profili ve yeteneklerle Agent Card alır."""
        aid = target_agent_id or self.agent_id
        resp = self._client.get(f"/agents/{aid}/card")
        resp.raise_for_status()
        return resp.json()

    def get_score(self) -> dict:
        """Mevcut ajan profilini alır."""
        resp = self._client.get(f"/agents/{self.agent_id}")
        resp.raise_for_status()
        return resp.json()

    def get_detail(self) -> dict:
        """İzler, geçmiş ve bozulma projeksiyonu ile tam ajan detayını alır."""
        resp = self._client.get(f"/agents/{self.agent_id}/detail")
        resp.raise_for_status()
        return resp.json()

    def compare_with(self, *agent_ids: str) -> list[dict]:
        """Bu ajansı diğerleriyle yan yana karşılaştırır."""
        all_ids = [self.agent_id] + list(agent_ids)
        resp = self._client.get(f"/compare?agents={','.join(all_ids)}")
        resp.raise_for_status()
        return resp.json()

    def register_webhook(self, url: str, events: list[str] | None = None) -> dict:
        """Skor değişiklikleri, kilometre taşları ve anomaliler için webhook kaydeder."""
        payload = {
            "agent_id": self.agent_id,
            "url": url,
            "events": events or ["trace_recorded", "milestone", "anomaly"],
        }
        resp = self._client.post("/webhooks", json=payload)
        resp.raise_for_status()
        return resp.json()

    def list_webhooks(self) -> list[dict]:
        """Bu ajan için tüm webhook'ları listeler."""
        resp = self._client.get(f"/webhooks/{self.agent_id}")
        resp.raise_for_status()
        return resp.json()

    def update_webhook(self, webhook_id: str, is_active: bool | None = None,
                       url: str | None = None, events: list[str] | None = None) -> dict:
        """Webhook günceller (aktif/pasif, URL veya event değişikliği)."""
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
        """Webhook siler."""
        resp = self._client.delete(f"/webhooks/{self.agent_id}/{webhook_id}")
        resp.raise_for_status()
        return True

    def search(self, query: str = "", category: str | None = None, limit: int = 10) -> list[dict]:
        """İsim, açıklama veya kategoriye göre ajan arar."""
        params = {"q": query, "limit": limit}
        if category:
            params["category"] = category
        resp = self._client.get("/search", params=params)
        resp.raise_for_status()
        return resp.json()

    def find_trusted_agent(self, category: str = "other", min_score: float = 65.0) -> dict | None:
        """Belirli kategoride minimum skorun üzerindeki en güvenilir ajansı bulur."""
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
        """Proaktif delegasyon koruması — güvensiz hedefleri otomatik engeller.

        Tüm kriterler karşılanırsa True döner:
        - Güven skoru >= min_score (varsayılan 60)
        - Doğrulanmış (>= 10 iz) eğer require_verified True ise
        - Aktif anomali bayrağı yok eğer block_anomalies True ise
        - Risk seviyesi 'critical' veya 'high' değil
        - Sertifikasyon kademesi >= min_tier (varsayılan silver); bronze varsayılan olarak engellenir

        Kullanım:
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

        # Sertifikasyon kademesi kontrolü (bronze varsayılan olarak engellenir)
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
        """Eyleme geçirilebilir öneri ile tam delegasyon analizi."""
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
        """Başka bir ajansı onaylar (A2A itibar transferi)."""
        payload = {"target_agent_id": target_agent_id, "context": context}
        resp = self._client.post("/endorse", json=payload)
        resp.raise_for_status()
        return resp.json()

    def get_endorsements(self, agent_id: str | None = None) -> dict:
        """Bir ajan için onayları alır."""
        aid = agent_id or self.agent_id
        resp = self._client.get(f"/endorsements/{aid}")
        resp.raise_for_status()
        return resp.json()

    def track(self, task: str, category: str = "other", cost_usd: float | None = None):
        """Süre ve durumu otomatik raporlayan bağlam yöneticisi."""
        return _TrackedExecution(self, task, category, cost_usd)

    # ─── v1.0 Sovereign Trust Layer yeni metodlar ───

    def route(self, category: str, min_tier: str = "silver", limit: int = 3) -> dict:
        """GET /api/v1/trust/route — Kategori ve kademe filtresiyle en güvenilir ajanları önerir."""
        params = {"category": category, "min_tier": min_tier, "limit": limit}
        resp = self._client.get("/trust/route", params=params)
        resp.raise_for_status()
        return resp.json()

    def find_best_agent(self, category: str, min_tier: str = "silver") -> dict | None:
        """route() çağırır ve en iyi eşleşmeyi döner."""
        result = self.route(category, min_tier=min_tier, limit=3)
        agents = result.get("agents", [])
        return agents[0] if agents else None

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
        """GET /api/v1/agents/{agent_id}/compliance — Kurumsal uyumluluk raporu."""
        aid = agent_id or self.agent_id
        resp = self._client.get(f"/agents/{aid}/compliance")
        resp.raise_for_status()
        return resp.json()

    def get_sovereign_id(self) -> str | None:
        """Ajanın DID'sini get_score() üzerinden döner."""
        score = self.get_score()
        return score.get("sovereign_id")

    def get_tier(self) -> str:
        """Ajanın sertifikasyon kademesini get_score() üzerinden döner."""
        score = self.get_score()
        return score.get("certification_tier", "bronze")

    def close(self):
        """HTTP istemcisini kapatır."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ──────────────────────────────────────────────
#  Async İstemci
# ──────────────────────────────────────────────

class AsyncGarlClient:
    """httpx.AsyncClient kullanan GarlClient'ın async sürümü."""

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
        """5xx ve bağlantı hatalarında async yeniden deneme."""
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
        """Yürütme izini asenkron olarak gönderir."""
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
        """Tek istekte en fazla 50 iz gönderir."""
        for t in traces:
            t.setdefault("agent_id", self.agent_id)
        resp = await self._retry(self._client.post, "/verify/batch", json={"traces": traces})
        resp.raise_for_status()
        return resp.json()

    async def get_history(self, limit: int = 50) -> list[dict]:
        """Zaman içinde güven skoru geçmişini döner."""
        resp = await self._client.get(f"/agents/{self.agent_id}/history", params={"limit": limit})
        resp.raise_for_status()
        return resp.json()

    async def check_trust(self, target_agent_id: str) -> dict:
        """A2A: Başka bir ajanın güvenilirliğini asenkron doğrular."""
        resp = await self._retry(self._client.get, f"/trust/verify?agent_id={target_agent_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_agent_card(self, target_agent_id: str | None = None) -> dict:
        """Agent Card alır."""
        aid = target_agent_id or self.agent_id
        resp = await self._client.get(f"/agents/{aid}/card")
        resp.raise_for_status()
        return resp.json()

    async def get_score(self) -> dict:
        """Mevcut ajan profilini alır."""
        resp = await self._client.get(f"/agents/{self.agent_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_detail(self) -> dict:
        """Tam ajan detayını alır."""
        resp = await self._client.get(f"/agents/{self.agent_id}/detail")
        resp.raise_for_status()
        return resp.json()

    async def compare_with(self, *agent_ids: str) -> list[dict]:
        """Bu ajansı diğerleriyle karşılaştırır."""
        all_ids = [self.agent_id] + list(agent_ids)
        resp = await self._client.get(f"/compare?agents={','.join(all_ids)}")
        resp.raise_for_status()
        return resp.json()

    async def register_webhook(self, url: str, events: list[str] | None = None) -> dict:
        """Webhook kaydeder."""
        payload = {
            "agent_id": self.agent_id,
            "url": url,
            "events": events or ["trace_recorded", "milestone", "anomaly"],
        }
        resp = await self._client.post("/webhooks", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def list_webhooks(self) -> list[dict]:
        """Webhook'ları listeler."""
        resp = await self._client.get(f"/webhooks/{self.agent_id}")
        resp.raise_for_status()
        return resp.json()

    async def update_webhook(self, webhook_id: str, is_active: bool | None = None,
                             url: str | None = None, events: list[str] | None = None) -> dict:
        """Webhook günceller."""
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
        """Webhook siler."""
        resp = await self._client.delete(f"/webhooks/{self.agent_id}/{webhook_id}")
        resp.raise_for_status()
        return True

    async def search(self, query: str = "", category: str | None = None, limit: int = 10) -> list[dict]:
        """Ajan arar."""
        params = {"q": query, "limit": limit}
        if category:
            params["category"] = category
        resp = await self._client.get("/search", params=params)
        resp.raise_for_status()
        return resp.json()

    async def find_trusted_agent(self, category: str = "other", min_score: float = 65.0) -> dict | None:
        """Kategoride en güvenilir ajansı bulur."""
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
        """Proaktif delegasyon koruması (async)."""
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
        """Tam delegasyon analizi."""
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
        """Başka bir ajansı onaylar."""
        payload = {"target_agent_id": target_agent_id, "context": context}
        resp = await self._client.post("/endorse", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def get_endorsements(self, agent_id: str | None = None) -> dict:
        """Onayları alır."""
        aid = agent_id or self.agent_id
        resp = await self._client.get(f"/endorsements/{aid}")
        resp.raise_for_status()
        return resp.json()

    async def route(self, category: str, min_tier: str = "silver", limit: int = 3) -> dict:
        """Kategori ve kademe ile routing."""
        params = {"category": category, "min_tier": min_tier, "limit": limit}
        resp = await self._client.get("/trust/route", params=params)
        resp.raise_for_status()
        return resp.json()

    async def find_best_agent(self, category: str, min_tier: str = "silver") -> dict | None:
        """En iyi ajansı bulur."""
        result = await self.route(category, min_tier=min_tier, limit=3)
        agents = result.get("agents", [])
        return agents[0] if agents else None

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
        """Uyumluluk raporu alır."""
        aid = agent_id or self.agent_id
        resp = await self._client.get(f"/agents/{aid}/compliance")
        resp.raise_for_status()
        return resp.json()

    async def get_sovereign_id(self) -> str | None:
        """Ajanın DID'sini döner."""
        score = await self.get_score()
        return score.get("sovereign_id")

    async def get_tier(self) -> str:
        """Ajanın sertifikasyon kademesini döner."""
        score = await self.get_score()
        return score.get("certification_tier", "bronze")

    async def track(self, task: str, fn, category: str = "other", cost_usd: float | None = None):
        """Async fonksiyonun yürütmesini otomatik izler."""
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
        """HTTP istemcisini kapatır."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()


# ──────────────────────────────────────────────
#  Bağlam Yöneticisi
# ──────────────────────────────────────────────

class _TrackedExecution:
    """Süre ve durumu otomatik raporlayan context manager."""

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
    """OpenClaw ajanları için adaptör — otomatik iz raporlama + güven-gated delegasyon."""

    def __init__(self, api_key: str, agent_id: str, base_url: str = "https://api.garl.ai/api/v1"):
        self.client = GarlClient(api_key, agent_id, base_url)
        self.agent_id = agent_id

    def report_task(self, message: str, duration_ms: int = 0, status: str = "success",
                    channel: str | None = None, session_id: str | None = None,
                    tool_calls: list[dict] | None = None, cost_usd: float | None = None,
                    category: str = "") -> dict:
        """OpenClaw görev tamamlanma olayını GARL izine dönüştürür."""
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
        """Güven-gated delegasyon kararı."""
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
        # Bronze tier varsayılan olarak engellenir

        tier = trust.get("certification_tier", "bronze")
        if tier == "bronze":
            return False
        return True

    def get_delegation_recommendation(self, target_agent_id: str) -> dict:
        """Detaylı delegasyon önerisi."""
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
        """Kategoride en iyi ajansı bulur (eski API uyumluluğu)."""
        return self.client.find_trusted_agent(category, min_score)

    def route(self, category: str, min_tier: str = "silver", limit: int = 3) -> dict:
        """GET /api/v1/trust/route — Kategori ve kademe ile en güvenilir ajanları önerir."""
        return self.client.route(category, min_tier=min_tier, limit=limit)

    def find_best_agent(self, category: str, min_tier: str = "silver") -> dict | None:
        """route() çağırır ve en iyi eşleşmeyi döner."""
        return self.client.find_best_agent(category, min_tier=min_tier)

    def close(self):
        """İstemci bağlantısını kapatır."""
        self.client.close()
