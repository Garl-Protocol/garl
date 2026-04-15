# GARL.ai — Full Audit & Future-Roadmap Checklist

Bu dosya, ileriki Claude session'larında **tek komutla** ("checklist.md'yi yürüt") tüm derinlikli GARL incelemesini tekrar ettirebilmen için yazıldı. Arda'nın orijinal promptunun üstüne, denetim sırasında öğrenilen her yeni "şunu da kontrol etmek gerekiyor"u ekle.

> **Tek satır prompt** → `Checklist.md'yi uygula: memory + docs oku, Supabase+Railway+GitHub+live site+tüm kod satır-satır tara, iddia-gerçek doğrulaması yap, derin web araştırması yap, bulgu+öneri+yeni özellik raporu çıkar. Kod yazma. Yeni bulduğun kontrol noktalarını bu dosyaya ekle.`

---

## 0. Oturum başlangıç kuralları

- [ ] `/Users/ardakutsal/.claude/projects/-Users-ardakutsal-Development-AgentReputation-gemini/memory/` altındaki **tüm** memory dosyalarını oku (MEMORY.md indeksinden başla).
- [ ] `feedback_collaboration_style.md`'deki prensiplere uy: Türkçe yaz, tablolu özet, "kod yazma" talimatına sadık kal, launch post yayınlama.
- [ ] `feedback_known_gotchas.md`'deki 8 kalıntıyı bilerek işle (backdrop-filter/fixed, PEP 604, Cloudflare 1010 UA, next/og headers, Fastly cache, Supabase 404 body, pytest cwd, e2e flake).
- [ ] `project_audit_resolutions.md`'deki **"false positive olarak kapatılmış"** bulguları tekrar araştırma (soft-delete, /verify 404-vs-401).
- [ ] GARL'ın **"for code"** pivot'unu hatırla — öneriler bu odakla tutarlı olmalı.

## 1. Proje dokümantasyonu (repo root)

- [ ] `README.md` — güncel tagline ve mevcut surface listesi ile uyumlu mu?
- [ ] `GARL_MASTER_PLAN.md` — yol haritası ile yapılan iş eşleşiyor mu?
- [ ] `TECHNICAL_SPECIFICATION.md` — scoring formülü, endpoint kontratları kod ile birebir mi?
- [ ] `UI_BLUEPRINT.md` — live site tasarımı ile tutarlı mı?
- [ ] `PITCH_DECK.md` — iddialar (kullanıcı sayısı, özellik listesi) kanıtlanabilir mi?
- [ ] `LAUNCH_PLAYBOOK.md`, `launch/` klasörü — yayınlanmamış olan var mı?
- [ ] `garl_security_audit.md` — kapanmamış P0/P1 kaldı mı?
- [ ] `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `LICENSE` — resmi konular tamam mı?
- [ ] `docs/` altındaki her dosyayı tara (SDK kullanımı, API reference, tutorial).

## 2. Supabase (project `leeuedosogkutlkckwwe`, EU-west-1)

- [ ] `list_tables(public)` — 5 tablo (agents, traces, reputation_history, endorsements, webhooks) + migration geçmişi.
- [ ] `list_migrations` — v12/v13 sonrası yeni bir şey var mı?
- [ ] `get_advisors(security)` + `get_advisors(performance)` — yeni uyarı var mı?
- [ ] Aktif agent sayısı, son 7 gün trace dağılımı (`execute_sql` ile COUNT queries).
- [ ] RLS policy'leri — public schema açık mı yoksa service role mu kullanılıyor?
- [ ] `get_logs(postgres)` — son saatlerde hata var mı?
- [ ] Tablo büyüklükleri, unused/duplicate index şüphesi.
- [ ] `certificate='{}' ` boş sertifika satır sayısı (v0.3 öncesi artıkları).
- [ ] `tool_calls / proof_of_result / security_events / permissions_declared` JSONB populate oranı.
- **[NEW 2026-04-15] `pr_bot_summaries` tablosu (v16)** — RLS aktif mi (public SELECT, service_role writes), kaç satır populate edildi, `model_counts` jsonb pratik shape neye benziyor; sprint-sonrası migration taraması yap (v14/v15/v16 ardışık uygulandı, v17 geldiyse schema drift var mı).

## 3. Railway deploy

- [ ] Backend service `dee17e34-...` son deploy status + build log.
- [ ] Frontend service `d6341c13-...` son deploy status + build log.
- [ ] Environment variables — secret sızıntısı veya eksik anahtar var mı (listele, değer görme).
- [ ] Domain / CNAME konfigürasyonu — api.garl.ai, garl.ai yönlendirmeleri.
- [ ] Auto-deploy GitHub entegrasyonu hâlâ aktif mi?
- [ ] Runtime logları (son 1 saat) — 5xx, kritik exception var mı?
- **[NEW 2026-04-15] PR Bot yüzeyi** — `POST /api/v1/pr-bot/webhook` canlı + `GITHUB_APP_WEBHOOK_SECRET` env'i yoksa **fail-closed 503** dönmeli; `GET /api/v1/pr-bot/summary/{owner}/{repo}/{pr_number}` cache boşsa **404** (tipik new-repo state). Sebep: webhook gate'i aksi halde spoof-able.
- **[NEW 2026-04-15] GitHub App env var envanteri** — Railway backend service'inde `GITHUB_APP_ID` + `GITHUB_APP_WEBHOOK_SECRET` + `GITHUB_APP_PRIVATE_KEY` üçü birden set mi; eksikse installation_token mint edemez, webhook handler sessizce `skipped:github_app_not_configured` döner. Sebep: sprint'te bu 3 var user tarafından eklendi, kaybolursa PR bot "ayakta ama sağır".

## 4. GitHub repo denetimi

- [ ] `Garl-Protocol/garl` (monorepo): star, fork, open issue/PR, traffic, last release.
- [ ] `Garl-Protocol/garl-receipt-action`: aynı metrikler + Marketplace listing canlı mı.
- [ ] GitHub Actions CI runs — son 30 runs pass/fail oranı.
- [ ] Dependabot / security advisories listesi.
- [ ] Branch protection (`main`) — required reviews, status checks.
- [ ] Secret scanning, push protection durumu.
- [ ] `CODEOWNERS`, issue/PR template var mı?
- **[NEW 2026-04-15] GARL PR Bot App install canlılığı** — `https://github.com/apps/garl-pr-bot` 200 döner mi; `installations_count` artıyor mu; App Settings → Advanced → Recent Deliveries son ~10 webhook delivery hepsi 200 mü. Sebep: App id 3390340, owner Garl-Protocol org, fail olan delivery handler crash'ini erken yakalamanın tek yolu.
- **[NEW 2026-04-15] Branch protection + solo-dev merge bypass** — `required_approving_review_count=1` + `enforce_admins=false` kombosu zorunlu; PR author kendini review edemediği için solo merge `gh pr merge --admin` bypass'ı gerektirir. `enforce_admins=true` yapılırsa solo dev stuck olur. Sebep: bu sprint'te PR #3 merge'inde aynen bu yaşandı, not düşüldü.

## 5. Live site (canlı URL'ler)


Her sayfayı fetch + header kontrolü + içerik analizi:

- [ ] `https://garl.ai` — landing (hero, CTA, "for code" vurgusu, SEO meta).
- [ ] `https://garl.ai/for-code` — ana pivot sayfası.
- [ ] `https://garl.ai/docs` veya `/docs/*` — dokümantasyon navigasyonu.
- [ ] `https://garl.ai/agents` — leaderboard / public directory.
- [ ] `https://garl.ai/r/6ff83db8` — canlı receipt örneği (Identicon, OG, signature görünüyor mu).
- [ ] `https://garl.ai/api/og/r/6ff83db8` — OG image content-type + Cache-Control.
- [ ] `https://garl.ai/.well-known/security.txt` — RFC 9116 uyumu.
- [ ] `https://api.garl.ai/api/v1/verify/{hash}` — 200 + JSON şema.
- [ ] `https://api.garl.ai/api/v1/agents/{id}` (slim) ve `?fields=full` (24 vs 39 alan).
- [ ] `https://api.garl.ai/api/v1/agents/{id}/audit?days=30&format=csv` — streaming CSV.
- [ ] `https://api.garl.ai/api/v1/badge/repo/{owner}/{repo}.svg` — SVG render.
- [ ] `https://api.garl.ai/docs` Swagger ve `/openapi.json` erişilebilir mi?
- [ ] Response header'ları: `cf-cache-status`, `x-fastly-*`, `cache-control`, CSP, HSTS, COEP, CORP.
- [ ] Mobile nav drawer (DevTools device mode simulate et) — portal pattern hâlâ çalışıyor mu.
- [ ] 404 ve error sayfaları (garl.ai/rastgele, api.garl.ai/rastgele).
- [ ] robots.txt ve sitemap.xml varlığı.
- **[NEW 2026-04-15] PR Bot sticky comment render** — bir demo PR'da `🔐 GARL Verified AI Code` markdown'u, AI % satırı, `[Verify all →]` linki doğru görünüyor mu; hidden `<!-- garl-pr-bot:v1 -->` marker'ı ekli mi (re-open/synchronize PATCH idempotency için). Sebep: duplicate comment = kötü developer UX.
- **[NEW 2026-04-15] GitHub Check Run görselleştirme** — PR "Checks" tab'ında `GARL PR Bot` check satırı neutral conclusion ile görünmeli; title formatı `{N}% AI-authored ({X}/{Y})`; summary tablosu model breakdown içermeli. Sebep: check run başlığı görünmezse provenance invisible.
- **[NEW 2026-04-15] `?fields=full` no-auth deprecation header'ları** — `GET /api/v1/agents/{id}?fields=full` (x-api-key yok) response'u slim'e sessizce düşmeli + **`Deprecation: true`** + **`Sunset: Thu, 15 Oct 2026 00:00:00 GMT`** + **`Link: <https://garl.ai/docs#fields-full-auth>; rel="deprecation"`** header'ları olmalı. Sebep: RFC 9745 / RFC 8594 uyumlu soft-cut; integrators hard-cut öncesi uyarılsın.

## 6. Kod analizi — satır satır (kod yazma, yalnızca oku)

### Backend (`backend/`)

- [ ] `app/main.py` — FastAPI app, middleware order, CORS policy.
- [ ] `app/api/routes.py` — her endpoint: auth, validation, error path.
- [ ] `app/services/traces.py` — scoring formülü TECHNICAL_SPECIFICATION ile eşleşiyor mu.
- [ ] `app/services/agents.py` — `_apply_lazy_decay` fire-and-forget güvenliği (race condition?).
- [ ] `app/services/reputation.py` — EMA, decay, endorsement bonus hesabı.
- [ ] `app/crypto/signing.py` (veya benzeri) — ECDSA-secp256k1 kullanımı, key storage, replay protection.
- [ ] `app/db/supabase.py` — service-role key loglanıyor mu, connection pool.
- [ ] Input validation — Pydantic modelleri uygulanıyor mu, `extra='ignore'` vs `'forbid'`.
- [ ] Rate limiting / abuse protection (Cloudflare tek başına yeterli mi).
- [ ] API key doğrulama akışı — timing attack, constant-time compare.
- [ ] Hata mesajlarında bilgi sızıntısı (500 stack trace vs sanitized).
- [ ] `backend/tests/*` — coverage, e2e marker kullanımı, happy-path beyond.
- **[NEW 2026-04-15] `backend/app/services/pr_bot/*` tutarlılığı** — `commit_attribution.py` confidence threshold'ları docs ile senkron mu: trailer=0.95, gen-marker=0.9, model-name=0.6-0.7, emoji=0.6, bare `cursor`=0.4; `hmac_verify.py` constant-time compare kullanıyor mu; `rate_limiter.py` per-repo bucket max_events+window değerleri code-default'u ile docs eşleşiyor (30 events / 60s); `github_app.py` JWT ttl 540s + 60s skew headroom; `handler.py` non-relevant action'ları (labeled, assigned, …) skip ediyor. Sebep: launch draft'ları bu rakamları quotes içinde kullanıyor; drift olursa doc-code delta yayınlanır.

### Frontend (`frontend/`)

- [ ] `src/app/**/page.tsx` — tüm route'lar ve `generateMetadata`.
- [ ] `src/app/r/[short]/page.tsx` — receipt render, signature görünürlüğü.
- [ ] `src/app/api/og/r/[short]/route.tsx` — next/og default headers, duplicate Cache-Control yok.
- [ ] `src/components/SiteNav.tsx` — createPortal drawer hâlâ intact.
- [ ] `src/components/Identicon.tsx` — deterministic SVG gradient.
- [ ] Client-side secret var mı (env var leak).
- [ ] `next.config.js` — headers(), redirects(), image domains.
- [ ] Accessibility: keyboard nav, aria-*, color contrast (Identicon).
- [ ] Performance: bundle size, image optimization, font preload.

### SDK / MCP / Action

- [ ] `sdks/javascript/` — public API yüzeyi, README, types.
- [ ] `sdks/python/` — aynı + PEP 604 sürüm matrisi.
- [ ] `integrations/mcp-server/` — `@garl-protocol/mcp-server` v1.2.0 tool listesi güncel mi.
- [ ] `Garl-Protocol/garl-receipt-action` (ayrı repo) — `action.yml`, `src/`, User-Agent düzeltmesi mevcut.
- [ ] Published sürüm ile repo HEAD uyumlu mu (`npm view`, `pip index`, `gh release list`).

## 7. İddia-gerçek doğrulaması

- [ ] "Cryptographic verification" — ECDSA-secp256k1 imza gerçekten doğrulanabiliyor mu? Public key nerede yayınlı? Test vektörü üret.
- [ ] "Immutable ledger" — DB row `UPDATE`'ine karşı koruma var mı (trigger? append-only view?)
- [ ] "EU AI Act Article 50 ready" — makalenin hükmü ne diyor, GARL gerçekten hangi kısmı karşılıyor?
- [ ] README/landing'deki kullanıcı sayıları live DB ile eşleşiyor mu?
- [ ] "GitHub Marketplace" listing'i aktif mi (anonim kullanıcı olarak eriş).
- [ ] SDK `README`'deki kod örnekleri çalışıyor mu (read-only olarak gözle kontrol).
- [ ] OpenAPI spec `/openapi.json` documented endpoint'leri canlı kod ile eşleşiyor mu.
- [ ] Tagline "Starting with code" → kod-dışı özellikler (`/trust/*`, A2A, `erc8004`) hâlâ tanıtım yüzeyinde mi?
- **[NEW 2026-04-15] PyPI paket adı tutarlılığı** — kod tabanında + launch/ + docs/ + README her yerde **`garl-protocol`** olmalı; **`garl-sdk`** hiçbir yerde olmamalı. Sebep: bu sprint'te `garl-sdk` tipo'su bir mesajda geçti, repoda zero match teyit edildi, drift oluşursa integrator karışır.
- **[NEW 2026-04-15] Article 50 solo iddia yok** — "EU AI Act Article 50 provenance obligations for code" gibi bir cümle **hiçbir public surface'de olmamalı**; triple-pitch (CA SB 942 aktif Oca 2026 + EU AI Act Code of Practice Haz 2026 + ISO/IEC 42001 Annex B) kullan. Sebep: Article 50 deepfake/public-interest text hedefli, kod değil; HN/dev.to okurları teknik stretch'i yakalar.
- **[NEW 2026-04-15] Octoverse 2025 anchor** — "46% of new code is AI-generated" ham iddiası yerine "Octoverse 2025 — ~45% AI-touched, sub-44% accepted unchanged" source-anchored form kullanılmalı. Sebep: rakam kaynağı tartışılır, savunulabilir form daha sağlam.
- **[NEW 2026-04-15] MCP tool count — "12+ batch variants"** — "20 tools" iddiası artık yok; gerçek 12 named + batch varyantları. `README.md` badge'i, docs/architecture.md, skill.md, integrations/mcp-server/README.md, launch drafts hepsi "12+ named + batch variants" kullanmalı.
- **[NEW 2026-04-15] RFC 6979 deterministic ECDSA** — `/verify/{hash}` iki arka arkaya çağrıda **byte-identical imza** dönmeli; `sign_digest_deterministic` kullanılıyor mu; `proof.key_id` mevcutsa lokal `sha256(publicKey)[:16]` ile eşleşmeli. Sebep: HN'in "neden aynı imza tekrarlanabilir?" sorusunun tek cevabı bu.

## 8. Güvenlik & operasyon

- [ ] Secret scanning: `git log --all -p | grep -i "SUPABASE_KEY\|SECRET"` (scripted).
- [ ] `security.txt` geçerliliği + PGP key parmak izi.
- [ ] HTTP security headers skor (securityheaders.com benzeri puan).
- [ ] TLS sertifika son kullanma tarihi (garl.ai + api.garl.ai).
- [ ] Dependabot alerts + `npm audit` / `pip-audit`.
- [ ] Docker image pinleri, supply chain (base image sha).
- [ ] Cloudflare WAF kuralları + rate limit etkin mi.
- **[NEW 2026-04-15] Webhook HMAC + per-repo rate-limit + fork-PR güvenliği** — `X-Hub-Signature-256` yoksa veya hatalıysa **401**; `GITHUB_APP_WEBHOOK_SECRET` env'i eksikse **503** (fail-closed); per-repo limit default 30 events / 60s; fork-PR'ları installation token üzerinden handle edilir, secret sızdırmaz. Sebep: webhook spoof → sahte sticky comment'ler = narrative kirliliği.
- **[NEW 2026-04-15] Webhook secret rotation prosedürü** — secret rotation için: (1) yeni secret üret (`python -c "import secrets; print(secrets.token_hex(32))"`), (2) App Settings → Webhook → Secret'ı güncelle, (3) Railway env var `GITHUB_APP_WEBHOOK_SECRET`'i aynı değere güncelle + redeploy, (4) App Settings → Recent Deliveries'te sonraki delivery'nin 200 döndüğünü doğrula. Sebep: eski secret leak olursa, bu dört-adım eşzamanlı yapılmazsa webhook pipeline 401'e kitlenir.

## 9. Deep web research (current month = Nisan 2026)

- [ ] **Rakipler/komşu projeler**: Sigstore Cosign, SLSA v1.0+, GitHub Artifact Attestations, in-toto, Grafeas, Trivy, OpenSSF Scorecard.
- [ ] AI-code-specific: Claude Code hooks ecosystem, GitHub Copilot commit metadata, Cursor telemetry, Sourcegraph Cody logs, aider commit footers.
- [ ] **Standartlar**: C2PA content credentials, W3C Verifiable Credentials, ERC-8004 agent identity güncel durum.
- [ ] **Yasal**: EU AI Act Article 50 implementation regs, NIST AI RMF, ISO/IEC 42001 güncel madde metinleri.
- [ ] Show HN / Product Hunt "AI commit provenance" trendleri (son 6 ay).
- [ ] Benzer pivotlar: "trust layer" kategorisinden "compliance receipt" kategorisine geçen başka başka projeler.
- [ ] "AI slop commit" tartışmaları — developer narrative trendi.
- **[NEW 2026-04-15] PR bot pazarı güncel snapshot** — Dosu ($0-pro user, CodeRabbit partner), Sweep (acquired by Cursor 2026 Q1?), CodeRabbit ($15-24/dev/mo enterprise pricing), Greptile, Qodo — pricing modeli + AI commit provenance'a destekleri. Sebep: GARL PR Bot bu pazara giriyor; rakip hangi layer'da konumlanmış bilinmeli.
- **[NEW 2026-04-15] `sentinel_project.md` = ayrı oturum brief'i** — sprint işi **değil**, F2 (PR Bot) ile **karıştırılmamalı**. F2: kullanıcı PR açınca sticky comment. Sentinel: GitHub üzerindeki GARL ile ilgili issue/comment/mention sinyallerini izleyen ayrı auto-triage agent'ı (kendi GARL-signed receipt'leri ile). Yeni session'da `gsd:new-project` akışı ile başla.
- **[NEW 2026-04-15] `launch/credentials-inventory.md` referansı** — agent-otomatik (PyPI keyring / npm / GitHub Releases) vs UI-only (Marketplace / App register / dev.to / HN / LinkedIn personal / Product Hunt / Slack) vs paid-tier (X/Twitter API / dev.to programmatic / LinkedIn company page) kategorileri orada. Yeni launch planlarken önce oku.

## 10. Rapor + öneri formatı

Raporu şu bölümlerle ver:

1. **Özet** (1 paragraf — durum, risk, fırsat).
2. **Doğrulanan iddialar** (tablolu).
3. **Tespit edilen bug / tutarsızlıklar** (severity + dosya + öneri).
4. **İyileştirmeler** (quick-win, mid-term, long-term).
5. **Yeni özellik önerileri** (for-code loop'u güçlendirenlere öncelik).
6. **Deep-research özeti** (rakip manzarası + regülasyon penceresi).
7. **"Senin yapman gereken"** (UI-only tasks, credential needed).

## 11. Bu dosyayı büyüt

Oturum sırasında yeni kontrol noktası fark ettiğinde (ör. "bir de Resend email templatesini kontrol etmeli") bu listeye bir satır ekle, commit etme — Arda inceleyip merge kararı versin. Eklerken şu başlıkları kullan:

- **[NEW] konu** — açıklama (hangi riskin kapsanması için).

---

_Son güncelleme tarihi: 2026-04-15 — F2 PR bot deploy + audit resolutions sprint'i eklendi._
