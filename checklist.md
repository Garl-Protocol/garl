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

## 3. Railway deploy

- [ ] Backend service `dee17e34-...` son deploy status + build log.
- [ ] Frontend service `d6341c13-...` son deploy status + build log.
- [ ] Environment variables — secret sızıntısı veya eksik anahtar var mı (listele, değer görme).
- [ ] Domain / CNAME konfigürasyonu — api.garl.ai, garl.ai yönlendirmeleri.
- [ ] Auto-deploy GitHub entegrasyonu hâlâ aktif mi?
- [ ] Runtime logları (son 1 saat) — 5xx, kritik exception var mı?

## 4. GitHub repo denetimi

- [ ] `Garl-Protocol/garl` (monorepo): star, fork, open issue/PR, traffic, last release.
- [ ] `Garl-Protocol/garl-receipt-action`: aynı metrikler + Marketplace listing canlı mı.
- [ ] GitHub Actions CI runs — son 30 runs pass/fail oranı.
- [ ] Dependabot / security advisories listesi.
- [ ] Branch protection (`main`) — required reviews, status checks.
- [ ] Secret scanning, push protection durumu.
- [ ] `CODEOWNERS`, issue/PR template var mı?

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

## 8. Güvenlik & operasyon

- [ ] Secret scanning: `git log --all -p | grep -i "SUPABASE_KEY\|SECRET"` (scripted).
- [ ] `security.txt` geçerliliği + PGP key parmak izi.
- [ ] HTTP security headers skor (securityheaders.com benzeri puan).
- [ ] TLS sertifika son kullanma tarihi (garl.ai + api.garl.ai).
- [ ] Dependabot alerts + `npm audit` / `pip-audit`.
- [ ] Docker image pinleri, supply chain (base image sha).
- [ ] Cloudflare WAF kuralları + rate limit etkin mi.

## 9. Deep web research (current month = Nisan 2026)

- [ ] **Rakipler/komşu projeler**: Sigstore Cosign, SLSA v1.0+, GitHub Artifact Attestations, in-toto, Grafeas, Trivy, OpenSSF Scorecard.
- [ ] AI-code-specific: Claude Code hooks ecosystem, GitHub Copilot commit metadata, Cursor telemetry, Sourcegraph Cody logs, aider commit footers.
- [ ] **Standartlar**: C2PA content credentials, W3C Verifiable Credentials, ERC-8004 agent identity güncel durum.
- [ ] **Yasal**: EU AI Act Article 50 implementation regs, NIST AI RMF, ISO/IEC 42001 güncel madde metinleri.
- [ ] Show HN / Product Hunt "AI commit provenance" trendleri (son 6 ay).
- [ ] Benzer pivotlar: "trust layer" kategorisinden "compliance receipt" kategorisine geçen başka başka projeler.
- [ ] "AI slop commit" tartışmaları — developer narrative trendi.

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

_Son güncelleme tarihi: ilk versiyon — ilerleyen oturumlarda tarih güncelle._
