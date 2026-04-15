# Start-of-session prompt for the next GARL agent

> Bu dosyayı okuyan Claude oturumu: **kod yazmadan önce** aşağıdaki
> yönergelere uy, durumu topla, rapor + plan ile geri dön, onay al,
> sonra uygula. Kullanıcı (Arda Kutsal) "kod yazma" diyene kadar tek
> satır yeni kod/diff çıkarma.
>
> Stil kuralı: Türkçe yaz, tablolu özetle; identifier/shell komutu
> İngilizce kalsın. `feedback_collaboration_style.md`'deki prensipler
> bağlayıcıdır.

---

## 0. Context yükle (zorunlu, bu sırayla)

1. `MEMORY.md` + altındaki **tüm** memory dosyaları:
   - `project_garl_overview.md` — v1.2.0 mimari, F2 PR bot state, yeni
     API surface, signing, backfill, branch protection
   - `project_audit_resolutions.md` — B1-B14 resolved; **iki
     false-positive re-investigate yok** (soft-delete, /verify 404
     vs 401)
   - `project_garl_for_code_pivot.md` — Nisan 2026 pivot gerekçesi
   - `project_launch_state.md` — launch draftları post-sprint state,
     yayın ertelenme nedeni, publish sırası
   - `project_f2_pr_bot.md` — F2 mimari, HMAC/rate-limit/fail-closed
     policy, Sentinel ile farkı
   - `reference_publish_credentials.md` — PyPI keyring'de, GitHub App
     3 env var Railway'de, channel matrix
   - `feedback_known_gotchas.md` — 13 landmine (backdrop-filter,
     PEP 604, Cloudflare 1010 UA, next/og headers, Fastly cache,
     pytest cwd, garl-sdk/garl-protocol tipo, Article 50
     mis-attribution, HN fresh-account, branch-protection context
     names byte-match, solo-dev `--admin` bypass)
   - `feedback_railway_deploy.md` — push to main → auto-deploy
   - `feedback_collaboration_style.md` — Türkçe tablolu, atomik
     commit, kod yazmadan plan, launch publish yayın izni

2. Repo root planning artefactları:
   - `checklist.md` — tek-promptta tam audit reçetesi (11 başlık +
     [NEW 2026-04-15] sprint eklentileri)
   - `audit_2026-04-15.md` — B1-B14 + improvements + feature bank +
     user-task listesi, detaylı
   - `sentinel_project.md` — **ayrı greenfield proje brief'i**,
     F2 ile karıştırma, bu session'da açma

3. Canlı yüzeylerin kanıtı (eskirse yenilenir):
   - `launch/credentials-inventory.md` — agent-otomatik / UI-only /
     paid-tier kategorileri
   - `docs/security.md`, `docs/compliance.md`, `docs/ecosystem.md`,
     `docs/deprecations.md`, `docs/policy-gate.md`, `docs/self-host.md`
   - `TRADEMARK.md`, `GOVERNANCE.md`, `.github/CODEOWNERS`

## 1. Hızlı canlı durum taraması (3 dakika)

Memory'nin iddiaları **her zaman eskiyebilir**. Önce şu smoke'u koş:

```bash
# git state
git log --oneline -10
git status --short

# canlı API sanity
curl -sS https://api.garl.ai/health
curl -sS https://api.garl.ai/api/v1/verify/6ff83db8 | python3 -m json.tool | head -20
curl -sS https://api.garl.ai/.well-known/garl-keys.json | python3 -m json.tool | head -15

# Railway + deploy + branch prot
railway deployment list --json | python3 -c "import sys,json;d=json.load(sys.stdin);[print(r['status'], r['meta'].get('commitHash','')[:8]) for r in d[:3]]"
gh api repos/Garl-Protocol/garl/branches/main/protection 2>&1 | head -5

# PR bot still live?
curl -s -o /dev/null -w "pr-bot webhook: %{http_code}\n" -X POST https://api.garl.ai/api/v1/pr-bot/webhook -H "X-GitHub-Event: ping" -d '{}'
# 503 = secret env var dropped — check Railway; 200 = ping accepted (unlikely w/o sig)

# PyPI latest + npm latest
curl -sS https://pypi.org/pypi/garl-protocol/json | python3 -c "import sys,json;d=json.load(sys.stdin);print('pypi:',d['info']['version'])"
npm view @garl-protocol/mcp-server version
npm view @garl-protocol/sdk version
```

Smoke sonuçlarını memory'deki son-bilinen-durum ile kıyasla. Herhangi
biri uyuşmazsa `audit_2026-04-15.md`'deki sınıflandırma (false
positive listesi dahil) ile çelişmeden incele.

## 2. Tam checkup — `checklist.md`'yi yürüt

`checklist.md` 11 başlık + Nisan 15 `[NEW]` eklentileri içerir. Her
maddeye paralel olarak şunları yap:

- Tek-promptla: "checklist.md'yi uygula" — explore agent'ları veya
  paralel Bash çağrılarıyla kapsa. 14 başlığın hepsi ayrı paralel iş.
- Her bulgu için: `hâlâ geçerli` / `kapandı` / `kısmen` etiketleyerek
  tablolaştır.
- Tamamlananları yeniden-araştırma; yeni sinyal geldiyse işle.
- Sprint Nisan 15 sonrası değişiklikleri **özellikle** gözden geçir:
  PyPI 1.2.0, F2 PR bot ops state, v16 migration, branch protection,
  launch draft accuracy.

## 3. Hazırlayacağın rapor

Tablolu, Türkçe. Bölümler:

1. **Özet** (1 paragraf — durum, değişen şeyler, yeni riskler)
2. **Doğrulanan iddialar** (tablolu — son session sonundan bu yana
   hâlâ yerinde olanlar)
3. **Yeni tutarsızlıklar / bug'lar** (severity + dosya + öneri)
4. **Değişen dış ortam** (rakip, regülasyon, pazar — aynı kullanıcı
   son audit'te research agent'ını paralel çalıştırmıştı; fark
   varsa bildir)
5. **Öncelikli iyileştirmeler + yeni özellik önerileri** (quick-win
   / mid / long-term ayrımı)
6. **Senin yapman gereken** (UI-only, credential, tasarım kararı)
7. **Plan** (dalga/faz kırılımı + her dalga için dosya listesi +
   test planı)

**Kod yazma.** Son satır: "plan onayına sunuluyor, `başla` dersen
kod aşamasına geçerim".

## 4. Bu session'da NE YAPMA

- Kod yazma / commit / push — kullanıcı `başla` demeden.
- `main` branch'e direkt push — branch protection aktif, CI çalışmalı.
  Yeni feature her zaman feature branch + PR + `gh pr merge --admin
  --squash --delete-branch`.
- Launch post yayınlama — memory rule. `launch/` altındaki draftlar
  sadece güncellenebilir, dış platformlara gitmez.
- Sentinel projesine başlama — `sentinel_project.md` "yeni session'da
  `gsd:new-project`" der; bu session'da açma.
- PEM / token / secret chat'e yazdırma. Kullanıcı gönderse de
  `launch/credentials-inventory.md`'deki akışa çevir (keyring /
  Railway variable --stdin).
- `.gitignore`'daki dosyaları commit etme (`frontend/tsconfig.tsbuildinfo`,
  `.env`, `LAUNCH_PLAYBOOK.md` gibi internal docs).

## 5. Bilmen gereken canlı sabitler (Nisan 15 itibarıyla)

| Alan | Değer |
|---|---|
| Active ECDSA key_id | `8c6e8f25ef3bf704` |
| GitHub App id | `3390340` (`Garl-Protocol/garl-pr-bot`) |
| App install URL | `https://github.com/apps/garl-pr-bot` |
| Webhook URL | `https://api.garl.ai/api/v1/pr-bot/webhook` |
| Supabase project | `leeuedosogkutlkckwwe` (eu-west-1) |
| Railway project | `551b6c47-e07b-4ab8-b2c0-f57267133538` |
| Backend service | `dee17e34-080f-4385-be09-ed8d75f42bb2` |
| Frontend service | `d6341c13-9d90-4c77-96d1-017a4db6f676` |
| Last migration | `v16_pr_bot_summaries` (2026-04-15) |
| Last backend deploy | `a5fc2ca` (2026-04-15, SUCCESS) |
| Branch protection required checks | `Backend Tests`, `Frontend Build` (byte-match) |
| PyPI latest | `garl-protocol 1.2.0` (ships `garl-verify` CLI) |
| npm latest | `@garl-protocol/mcp-server 1.2.0`, `@garl-protocol/sdk 1.1.0` |
| Trace state | 0 unsigned / 528 backfilled / 978 original (toplam 1506) |
| Active agents | 58, sandbox 70, deleted 48 (toplam 131) |
| Terminator2 share | ~%48.6 (gold, trust_score ~80) |
| PyPI token | macOS keyring `https://upload.pypi.org/legacy/` + `__token__` |
| PR Bot local PEM backup | `~/Downloads/garl-pr-bot.2026-04-15.private-key.pem` (asla commit etme) |

## 6. Dış repo + marketplace

- `Garl-Protocol/garl` — monorepo (backend + frontend + SDK + MCP +
  docs + launch drafts)
- `Garl-Protocol/garl-receipt-action` — GitHub Action (ayrı repo, tag
  `v1.0.0` Marketplace'te listed)
- PR Bot App içinde barındırılan `backend/app/services/pr_bot/`
  (monorepo içi — Sentinel brief'teki `packages/garl-github-core/`
  öngörüsüyle uyumlu)

## 7. Araç kullanım protokolü

- **Büyük kod taramaları**: `Explore` agent'ı paralel.
- **Live API / HTTP**: WebFetch agent'ı veya paralel curl.
- **Supabase**: `mcp__plugin_supabase_supabase__*` tool'ları.
- **Railway**: `railway` CLI (login Arda Kutsal / Webrazzi).
- **GitHub**: `gh` CLI (login `ardakutsal`).
- **Test koşusu**: `cd backend && python3.11 -m pytest tests/ -m "not
  e2e"` — 313+ test olmalı geçmesi gereken. Son bilinen yeşil durum:
  **313 passed, 5 skipped, 10 deselected**.

## 8. Frequent traps (yukarıdaki gotcha'ların kısaltılmış özeti)

- `python3` macOS'ta 3.9 — pytest fail. **Her zaman `python3.11`**.
- Launch post'larda `46% of new code is AI-generated` kullanma; onay
  yok → Octoverse 2025 anchor form.
- "EU AI Act Article 50" solo kullanma; triple pitch.
- MCP "20 tools" yok; "12 named + batch variants".
- `garl-sdk` asla paket adı değil — PyPI'da **`garl-protocol`**.
- Branch protection `required_status_checks.contexts` job name ile
  byte-match; drift = merge indefinitely stuck.
- Fork PR'lar için **Action workflow yetersiz**; GitHub App (PR Bot)
  fork-safe.
- Webhook secret rotation 4-adım eşzamanlı (App settings + Railway
  env + redeploy + recent deliveries verify); aksi halde 401
  kilit.

## 9. Eğer kullanıcı "başla" dedikten sonra iş yaparken

- Atomic commit, her commit push + Railway auto-deploy bekle, sonra
  smoke.
- Feature branch'i `<scope>/<short-name>` (ör. `f3/vscode-ext`,
  `ops/rekor-rotation`).
- PR title: scope + ≤70 char; PR body: summary + test plan + kapatır-
  bulgu referansı.
- Her dalga sonu tablolu brief (ne yaptın + test sayısı + canlı
  doğrulama + sonraki adım).
- Bitirirken MEMORY artefactlarını güncelle (bu file format).

## 10. Özel talimat: sıfır sürpriz

- İşe başlarken "Önceki oturum şöyle bıraktı, şu 5 şey sende
  doğrulanmalı:" diye tek mesajla aç.
- Kullanıcıya 3 maddeden fazla soru sorma; kendi kararını ver,
  belgeleyerek ilerle.
- Kullanıcı "hepsini yap" tarzı serbest emir verirse yine tablolu
  plan + dalga bölümlendirmesi ile dön, **sonra** kodla.

---

_Bu dosya artefact — repo'da durur, her yeni session'ın ilk okuduğu
şey olmalı. Güncelleme gerekirse Son güncelleme satırına tarih/commit
hash yaz._

_Son güncelleme: 2026-04-15 — F2 PR bot deploy + audit resolutions
sprint bitişi._
