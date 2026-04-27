# GARL — Next-Session Bootstrap

> Bu dosyayı okuyan Claude oturumu: aşağıdaki sırayla durumu topla, sonra Arda'ya tablolu bir özet sun, **kod yazmadan** plan onayı al, sonra uygula. Stil: Türkçe, tablolu, kısa, emoji yok, sonuna uzun "summary" yazma. `feedback_collaboration_style.md` bağlayıcıdır.

---

## 0. Memory'yi yükle (zorunlu — 2 dakika)

`/Users/ardakutsal/.claude/projects/-Users-ardakutsal-Development-garl/memory/` altındaki dosyaların hepsini oku, başlayarak:

1. `MEMORY.md` — index
2. `user_role.md` — Arda'nın profili
3. `feedback_collaboration_style.md` — Türkçe + tablo + emoji yok
4. `feedback_known_gotchas.md` — 10 landmine (pytest cwd, py3.11, branch protection, drift sweep, vb.)
5. `feedback_force_push_policy.md` — main'e force-push asla per-action onay olmadan
6. `project_garl_overview.md` — mevcut mimari (Wave 1+2+3 sonrası)
7. `project_wave_history.md` — bu session'ın 4 PR + 3 migration + 3 publish + 1 release özeti
8. `project_pricing_posture.md` — fiyatlandırma kararı: "şu anda yok"
9. `project_open_blockers.md` — 3 dış-blocker + 1 history-scrub kararı
10. `reference_supabase.md` — DB schema + advisor + key
11. `reference_publish_credentials.md` — PyPI keyring, npm whoami, gh auth
12. `reference_repos.md` — `Garl-Protocol/garl` + `Garl-Protocol/garl-receipt-action`
13. `reference_endpoints.md` — full /api/v1 catalog (Wave 1+2+3 dahil)
14. `reference_strategy.md` — `garl-strategy-2026-04-27.md` özeti

**Önemli:** `garl-strategy-2026-04-27.md`, `audit_*.md`, `PITCH_DECK.md`, `LAUNCH_PLAYBOOK.md`, `UI_BLUEPRINT.md`, `GARL_MASTER_PLAN.md`, `garl_security_audit.md` — hepsi `.gitignore`'da, sadece local. Bunları **ASLA commit etme**.

---

## 1. Canlı durum smoke testi (3 dakika — sırayla çalıştır)

```bash
# Repo state
cd /Users/ardakutsal/Development/garl
git log --oneline -10
git status --short

# Backend tests (484 baseline)
cd backend && python3.11 -m pytest tests/ -m "not e2e" --tb=no -q | tail -5
cd ..

# Frontend build (19 routes, hepsi temiz olmalı)
cd frontend && npx next build 2>&1 | tail -5
cd ..

# Live API
curl -sS https://api.garl.ai/health
curl -sS https://api.garl.ai/api/v1/public-stats | python3 -m json.tool | head -25
curl -sS "https://api.garl.ai/api/v1/agents/3216b8ed-fa2c-452a-bda2-925cde273314/trust-vector" | python3 -m json.tool | head -25
curl -sS https://api.garl.ai/.well-known/garl-keys.json | python3 -m json.tool | head -10

# OpenAPI snapshot (60 endpoint olmalı)
curl -sS https://api.garl.ai/openapi.json | python3 -c "import sys,json; d=json.load(sys.stdin); print('paths:',len(d['paths']))"

# Live frontend
curl -sS -o /dev/null -w "garl.ai/stats: %{http_code}\n" https://garl.ai/stats
curl -sS -o /dev/null -w "garl.ai/agents.txt: %{http_code}\n" https://garl.ai/agents.txt
curl -sS -o /dev/null -w "garl.ai/r/6ff83db8: %{http_code}\n" https://garl.ai/r/6ff83db8
curl -sS -o /dev/null -w "garl.ai/for-code: %{http_code}\n" https://garl.ai/for-code

# Published packages
curl -sS https://pypi.org/pypi/garl-protocol/json | python3 -c "import sys,json; d=json.load(sys.stdin); print('pypi garl-protocol:',d['info']['version'])"
npm view @garl-protocol/sdk version
npm view @garl-protocol/mcp-server version

# GitHub state
gh repo view Garl-Protocol/garl --json description,latestRelease,stargazerCount
gh pr list --repo Garl-Protocol/garl --state all --limit 5
gh release list --repo Garl-Protocol/garl --limit 5
```

**Beklenen baseline (2026-04-27 session sonu):**
- Backend: **484 passed, 6 skipped, 10 deselected**
- Frontend: 19 route, hepsi clean
- API health: `{"status":"healthy","version":"1.1.0","protocol":"garl"}`
- public-stats: 58+ agents, 2011+ traces, 1+ capability_tokens_issued, 0 receipts (Wave 2 fresh)
- /openapi.json: 60 endpoint (Wave 1+2+3 + legacy)
- /stats, /agents.txt, /r/6ff83db8, /for-code: HTTP 200
- PyPI: `garl-protocol@1.3.0`
- npm: `@garl-protocol/sdk@1.2.0`, `@garl-protocol/mcp-server@1.4.0`
- Latest release: `v1.2.0`

Herhangi biri uyuşmazsa, kullanıcıyla konuşmadan önce nedeni araştır.

---

## 2. Supabase + Railway durum (1 dakika)

```bash
# Supabase advisors (security 0 lints, performance ~12 INFO unused index normaldir)
# Use mcp__plugin_supabase_supabase__get_advisors with project_id "leeuedosogkutlkckwwe"
# Tables (10 olmalı: agents, traces, reputation_history, webhooks, endorsements, pr_bot_summaries, receipts, capability_tokens, compensations, merkle_batches)

# Railway deploy state — backend service dee17e34, frontend service d6341c13
# Auto-deploy on main; verify via curl /openapi.json having latest endpoints
```

---

## 3. GitHub repo durum (1 dakika)

```bash
# Branch protection (Backend Tests + Frontend Build, byte-match)
gh api repos/Garl-Protocol/garl/branches/main/protection | python3 -m json.tool | grep -E "contexts|required_approving_review_count" | head -5

# Open issues / PRs
gh issue list --repo Garl-Protocol/garl --state open --limit 5
gh pr list --repo Garl-Protocol/garl --state open --limit 5

# Action repo metadata (topics + homepage olmalı)
gh repo view Garl-Protocol/garl-receipt-action --json description,homepageUrl,repositoryTopics
```

---

## 4. Tablolu raporu sun (Türkçe, kısa)

Aşağıdaki şablona göre tek mesajda Arda'ya rapor ver:

```markdown
## Önceki session sonu durumu doğrulama

**Beklenen baseline ile karşılaştırma:**
| Alan | Beklenen | Bulduğum | Durum |
|---|---|---|---|
| Backend tests | 484 | <gerçek> | OK / drift |
| Frontend routes | 19 | <gerçek> | OK / drift |
| /api/v1/public-stats | 200, agent_count > 0 | <gerçek> | OK / drift |
| garl.ai/stats | HTTP 200, 6 section render | <gerçek> | OK / drift |
| PyPI version | 1.3.0 | <gerçek> | OK / drift |
| npm @garl-protocol/mcp-server | 1.4.0 | <gerçek> | OK / drift |
| Latest GH release | v1.2.0 | <gerçek> | OK / drift |
| Supabase tables | 10 | <gerçek> | OK / drift |
| Migration history latest | v19_advisor_fixes | <gerçek> | OK / drift |

**Yeni sinyaller:**
- (örn. "/api/v1/public-stats wave2.action_receipts.total = 5 → ilk gerçek v0.1 receipt'ler geldi!")
- (örn. "GitHub stars: 0 → 12 → traction sinyali")
- (örn. "Open issue #2: 'X feature gerek' geldi")

**Kalan açık 3 dış-blocker (önceki session'dan):**
1. Mainnet Base broadcast — wallet bekliyor
2. Cloud SaaS — pricing kararı bekliyor
3. v0.1 → v1.0 sealing — prod data bekliyor
4. (decision) audit_2026-04-15.md history scrub — Arda onayı bekliyor

**Bu session ne yapmak istiyorsun?**
```

Sonra Arda'nın yönlendirmesini bekle. **Kendiliğinden kod yazmaya başlama.**

---

## 5. Bu session'da NE YAPMA

- Kod yazma / commit / push — Arda `başla` demeden.
- `main` branch'e direkt push — branch protection aktif. Feature branch + PR + admin merge.
- Force-push, history rewrite, filter-repo — `feedback_force_push_policy.md`'ye uy.
- Launch post yayınlama — `launch/` altındaki draft'lar sadece local.
- `audit_*.md`, `garl-strategy-*.md`, `PITCH_DECK.md`, `LAUNCH_PLAYBOOK.md`, `UI_BLUEPRINT.md`, `GARL_MASTER_PLAN.md`, `garl_security_audit.md`, `TECHNICAL_SPECIFICATION.md`'i commit etme — `.gitignore`'da.
- Pricing/billing/SSO/Cloud SaaS scaffolding — `project_pricing_posture.md`'ye karşı.
- Cüzdan key, secret value, JWT token chat'e yazma. Kullanıcı paylaşırsa ortam değişkenine yönlendir.
- `python3` kullanma — macOS'ta 3.9. **Her zaman `python3.11`**.
- Test'lerde cwd yanlışlığı — pytest **`backend/`** dizininden çalışır, repo root'tan değil.
- "Universal Trust Standard", "SOVEREIGN TRUST LAYER", "OpenClaw", "Article 50 ready" (kod için), "20 MCP tools" (gerçek 28) — bu drift kelimelerini hiçbir yere ekleme.

---

## 6. Bu session'da YAPABILECEĞIN tek-tıklık iş varsa

Eğer Arda `tek tıklık iş yap` derse veya açıkça onay verirse, aşağıdakiler **iç onay olmadan** çalıştırılabilir:

| İş | Komut |
|---|---|
| Backend test suite tekrar çalıştır | `cd /Users/ardakutsal/Development/garl/backend && python3.11 -m pytest tests/ -m "not e2e" -v` |
| Frontend build doğrula | `cd /Users/ardakutsal/Development/garl/frontend && npx next build` |
| Live deploy state kontrol | `curl -sS https://api.garl.ai/health` + `gh pr list` + `gh release list` |
| Supabase advisor recheck | MCP `get_advisors` tool |
| OpenAPI snapshot fark | `curl /openapi.json` + `git diff` öncekiyle |

İç onay GEREKEN işler:
- Migration apply (Supabase MCP)
- npm/PyPI publish
- `gh release create`
- `gh pr merge --admin`
- Yeni dosya commit / push / PR open

---

## 7. Kullanıcı "başla" dedikten sonra çalışma protokolü

1. **Tek bir feature branch aç**: `<scope>/<short-name>` (örn. `feat/v0.1-issuer-2`, `ops/rekor-bridge`).
2. **Atomic commit**, her commit anlamlı. Co-Author trailer otomatik.
3. **Test sonra commit**: değişiklik → test → commit. Kırık commit asla.
4. **Push → CI yeşil bekle → admin merge** (Arda onayı per-action gerekir).
5. **Railway propagation**: ~2-3 dakika; openapi.json'da yeni endpoint görünene kadar bekle.
6. **Live verify**: smoke endpoint testleri (Bölüm 1).
7. **Memory güncelle**: değişen referansları (`reference_endpoints.md`, `project_wave_history.md`, vb.) update et.

---

## 8. Kritik canlı sabitler (2026-04-27 itibarıyla)

| Alan | Değer |
|---|---|
| Active ECDSA key_id | `8c6e8f25ef3bf704` |
| GitHub App id | `3390340` (`Garl-Protocol/garl-pr-bot`) |
| Supabase project | `leeuedosogkutlkckwwe` (eu-west-1) |
| Railway project | `551b6c47-e07b-4ab8-b2c0-f57267133538` |
| Backend service | `dee17e34-080f-4385-be09-ed8d75f42bb2` |
| Frontend service | `d6341c13-9d90-4c77-96d1-017a4db6f676` |
| Last migration | `v19_advisor_fixes` (2026-04-27) |
| Last GH release | `v1.2.0` (2026-04-27) |
| Branch protection contexts | `Backend Tests`, `Frontend Build` |
| MCP tool count | **28** named (+ batch variants) |
| Top agent | `Terminator2` `3216b8ed-fa2c-452a-bda2-925cde273314` |
| PyPI / npm whoami | `__token__` (keyring) / `garlai` |
| gh auth | `ardakutsal` |

---

## 9. Sıradaki muhtemel iş kategorileri (öneriler, Arda onaylarsa)

Arda yön belirtmezse, aşağıdakilerden birini öner:

| Kategori | İçerik | Süre |
|---|---|---|
| **A — Foundry test + testnet deploy** | `forge install foundry-rs/forge-std --no-commit && forge test -vvv` (12 testin yeşil olduğunu doğrula) + Sepolia testnet'e Deploy.s.sol broadcast | 1 saat |
| **B — Reverse-action demos** (mock-mode) | GitHub-scope agent + Calendly/Notion/Stripe-test reversible demos. Mock backend yeterli. | 2-3 saat |
| **C — UX iyileştirmesi** | `/stats` yeni veri renderı + receipt page Capability token verifier widget + dashboard Trust Vector radar overlay | 2-3 saat |
| **D — Trust Vector dimensions canlandır** | `reversible_action_success`, `human_override_rate`, `payment_dispute_rate` recompute job — null'lar gerçek verilerle dolsun | 2 saat |
| **E — Documentation + spec hardening** | Action Receipt v0.1 ek örnekler, capability-token spec yaz (`protocol/spec/capability-token-v0.1.md`), self-host docs güncelleme | 1.5 saat |
| **F — Distribution side** | "Why agents need a reputation layer" essay draft + AAIF Silver application copy + Felicis intro mail draft | Sen yapacaksın, ben sadece taslakları yazarım |
| **G — Yeni özellik / pivot kararı** | Arda'nın getirdiği yeni yön | — |

---

## 10. Sıfır sürpriz ilkesi

- Her yeni session "Önceki session şöyle bıraktı, şu 5 şey doğrulanmalı" diye açar (Bölüm 4 şablonu).
- Arda'ya 3 maddeden fazla soru sorma; kendi kararını ver, belgeleyerek ilerle.
- "Hepsini yap" tarzı serbest emir gelirse yine tablolu plan + faz bölünmesi sun, **sonra** kodla.
- Her dalga sonu tablolu brief: ne yaptın + test sayısı + canlı doğrulama + sonraki adım.
- Memory'yi her session sonu güncelle (özellikle `project_wave_history.md` ve `reference_endpoints.md`).

---

_Son güncelleme: 2026-04-27 — session-end-cleanup PR (Wave 1+2+3 ship sonrası)._
