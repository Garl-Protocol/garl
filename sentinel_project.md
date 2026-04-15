# GARL Sentinel — Proje Brief'i

> **Bu dosyayı okuyan Claude session'ı için**: Bu bir greenfield proje brief'idir. Kullanıcı (Arda Kutsal) bu proje üzerine yeni bir session açıyor. Kod yazmaya başlamadan önce **Faz 1 kapsamını doğrula + plan onayı al**. Memory'den `project_garl_overview.md`, `feedback_collaboration_style.md` (Türkçe tablolu iletişim), `feedback_known_gotchas.md` oku. Tasarım kararları için kullanıcıya tek tek sor, varsayma.
>
> Ayrıca ilgili kaynak: aynı dizindeki `audit_2026-04-15.md` — GARL'ın mevcut durumu, bulguları, F2 (PR bot) önceliği; Sentinel F11 olarak bu listeye eklenecek.

---

## 1. Özet

**GARL Sentinel**, GARL Protocol'ün GitHub (ve sonrasında diğer mecraların) üzerindeki organik kullanıcı sinyallerini — issue, comment, discussion, PR review, mention — otomatik olarak izleyen, triage eden, Arda'ya task atan ve (aşamalı olarak) kamuya cevap yazan bir AI agent.

**Neden GARL için özel**: Sentinel'in attığı her public yorum kendi GARL receipt'i ile imzalanır (`did:garl:sentinel-xxx`). Her eylemi public `garl.ai/r/xxxxx` URL'siyle doğrulanabilir olur. Sentinel'in kendi itibar skoru kamuya açık bir leaderboard'da yaşar. **GARL'ın kendi ürününü canlı demo etmesi** — her organic user etkileşimi aynı anda pazarlama eventine dönüşür.

**Ticarileşme potansiyeli**: Aynı altyapı "GARL Sentinel for your open source project" olarak B2B ürüne dönüşebilir. Dosu.dev, CodeRabbit vb. yapmıyor; **cryptographic receipt per-reply** tek başına differentiator.

---

## 2. Kullanım senaryosu (AI Village örneği, 15 Nisan 2026)

Gerçek olay: AI Village (12+ LLM collective) GARL'a auto-register oldu, `github.com/Garl-Protocol/garl/issues/1`'de pozitif intro + feedback yazdı (A2A PascalCase spec divergence dahil). Arda issue'dan 4+ saat sonra haberdar oldu. Sentinel olsaydı:

| Zaman | Olay |
|---|---|
| T+0 | AI Village issue açtı |
| T+30sn | Webhook → Sentinel triage: **kategori=agent_intro**, **öncelik=high**, **task_suggestion=A2A PascalCase alias fix**, **landing_testimonial_opp=true** |
| T+1dk | Slack/dashboard'a Arda'ya digest: "1 yeni intro issue, draft hazır, görmek ister misin?" |
| T+2dk (Arda onayı ile) | Sentinel issue'ya imzalı welcome reply post'lar + `agent-intro` label ekler + GitHub Project'e `[BUG] A2A method naming: PascalCase vs spec slash format` task'ı açar |
| T+5dk | Arda launch post'a "AI Village is on GARL" satırını eklemek için draft görür |

---

## 3. Faz planı (aşamalı risk + aşamalı dogfood)

| Faz | Kapsam | İnsan gate | Süre | Ana çıktı |
|---|---|---|---|---|
| **F1 — Triage-only** | webhook alıcı, LLM kategori+öncelik+label+task taslağı, morning digest email/Slack | %100 insan, hiç post yok | 1 hafta | Günde 1 digest, 0 public post |
| **F2 — Draft generation** | F1 + agent GitHub Discussion'a veya özel issue'ya **Arda için draft** yazıyor, sen tek-tık post'luyorsun | %100 insan | 1 hafta | Tek tık workflow |
| **F3 — Auto-reply (selective)** | Düşük-risk kategorilerde (agent_intro, how-to, doc typo) otomatik cevap + GARL receipt imza. Bug/security/feature_request her zaman insan | Kısmi | 2 hafta | İlk imzalı kamu yorumu |
| **F4 — Proactive listening** | Twitter/HN/Reddit/dev.to GARL mention izleme → draft | İnsan | 2 hafta | Organic discovery yüzeyi |
| **F5 — B2B SaaS** | GitHub App packaging, multi-tenant, Sentinel'i başka projelere sat | — | 1 ay | Revenue stream |

**Toplam Faz 1–3 MVP**: ~4 hafta, Arda onaylı her fazda demo.

---

## 4. Teknik mimari

```
┌─────────────────────────────────────────────────────────────┐
│  GitHub (issues, comments, PR reviews, discussions)         │
└───────────────────┬─────────────────────────────────────────┘
                    │ webhook (X-GitHub-Event: issues, issue_comment, ...)
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  Cloudflare Worker / Railway endpoint                       │
│  POST /sentinel/webhook                                     │
│  - HMAC signature verify (GitHub webhook secret)            │
│  - Idempotency: delivery_id deduplication                   │
└───────────────────┬─────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  Triage engine (Claude Haiku 4.5)                           │
│  Input: issue body + repo context + recent activity         │
│  Output JSON: {                                             │
│    category: "agent_intro"|"bug"|"feature"|"question"|...   │
│    priority: "p0"|"p1"|"p2"|"p3"                            │
│    labels: ["agent-intro", "a2a-spec"]                      │
│    detected_tasks: [{title, body, priority}]                │
│    draft_reply: "..."                                       │
│    safe_for_auto_reply: bool                                │
│    testimonial_value: bool                                  │
│  }                                                          │
└───────────────────┬─────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  Supabase: garl_signals tablosu                             │
│  + Slack/email digest (schedule: her sabah 09:00 TR)        │
│  + Arda dashboard (opsiyonel)                               │
└───────────────────┬─────────────────────────────────────────┘
                    ▼ (Arda onayı)
┌─────────────────────────────────────────────────────────────┐
│  Action executor                                            │
│  - gh issue comment / label / project item add              │
│  - GARL trace submit (agent_id=sentinel) → receipt URL      │
│  - Reply body'sine receipt URL footer'ı ekle                │
└─────────────────────────────────────────────────────────────┘
```

### Bileşenler

| Bileşen | Tech | Niye |
|---|---|---|
| Webhook alıcı | Cloudflare Worker veya FastAPI route (`backend/app/api/sentinel.py`) | Free tier, Railway'e kolay ekleme |
| Triage LLM | Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) | Hızlı + ucuz (~0.0005$/issue) |
| Draft LLM (F2+) | Claude Opus 4.6 | Kalite, tone match |
| Storage | Supabase `garl_signals` tablosu | Mevcut stack, migration basit |
| Queue | Supabase realtime subscriptions VEYA Inngest free tier | Idempotency + retry |
| Digest | Resend (email) veya Slack webhook | Hangi kanal tercih ediliyorsa |
| Identity | Sentinel kendi `did:garl:...` agent'ı, API key env'de | GARL kendi user'ı |

### Veri modeli

```sql
CREATE TABLE garl_signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source TEXT NOT NULL,                    -- 'github'|'twitter'|'hn'|...
  source_event TEXT NOT NULL,              -- 'issue_opened'|'comment_created'|...
  source_id TEXT NOT NULL UNIQUE,          -- github delivery_id; idempotency
  repo TEXT,                               -- 'Garl-Protocol/garl'
  author TEXT,                             -- 'claude-opus-4-6'
  url TEXT,                                -- canonical public URL
  body TEXT,
  category TEXT,                           -- triage output
  priority TEXT,
  labels JSONB,
  detected_tasks JSONB,                    -- array of {title, body, priority}
  draft_reply TEXT,
  safe_for_auto_reply BOOLEAN DEFAULT FALSE,
  testimonial_value BOOLEAN DEFAULT FALSE,
  human_approved_at TIMESTAMPTZ,
  reply_posted_at TIMESTAMPTZ,
  reply_receipt_url TEXT,                  -- GARL trace receipt
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_signals_priority_pending ON garl_signals(priority)
  WHERE human_approved_at IS NULL;
```

### System prompt (triage, özet)

```
Sen GARL Sentinel'sin — GARL Protocol'ün GitHub aktivitesini izleyen triage agent'ı.

Girdi: yeni bir GitHub issue veya comment.
Çıktı: yukarıdaki JSON şema.

Kurallar:
1. Asla deadline veya commitment verme (cevap taslağında bile).
2. Bug rapordaysa kesinlikle safe_for_auto_reply=false.
3. Kategoriler: agent_intro, question, bug, feature_request, doc_feedback, integration_request, other.
4. Tone: Arda'nın yazım stili — direkt, kısa cümleler, "teşekkür ederim"den çok "faydalı feedback, not ettim".
5. Asla "Great question!", "Excellent point!", em-dash veya template expression kullanma.
6. GARL özelinde teknik bilgi: [... project_garl_overview.md özet buraya]
7. Eğer issue GARL'ın yanlış anlaşıldığını gösteriyorsa, doğru açıklamayı draft'a koy.
```

---

## 5. Risk matrisi

| Risk | Olasılık | Etki | Mitigasyon |
|---|---|---|---|
| AI-yazımı kokan cevap | Orta | Yüksek (reputation) | Negative-example prompt + temperature 0.3 + Faz 2'de insan gate, Faz 3 sadece düşük risk |
| Yanlış technical acknowledge | Düşük | Çok yüksek | Bug kategorisi asla auto-reply; her zaman insan |
| Spam percepsion | Orta | Orta | Sadece kendi repo'su; sadece ilk yanıt, thread'lerde yok; rate limit |
| Agent manipülasyonu | Düşük | Orta | Issue body sanitize, prompt injection detection, role boundaries |
| Recursive AI chatter (agent→agent→agent) | Orta | Düşük | `author=bot` ise auto-reply kapalı, insan gate |
| GitHub API rate limit | Düşük | Düşük | App installation (5000/h) vs PAT (1000/h) — App kullan |
| Sentinel kendi bug fix çağırır | Orta | Düşük | detected_tasks her zaman insan onayı ile Project'e düşer |

---

## 6. Rakip landscape ve moat

| Rakip | Ne yapıyor | GARL Sentinel farkı |
|---|---|---|
| **Dosu.dev** | AI issue triage + label + reply, VC-funded 2024+ | Sentinel'in her yanıtı **cryptographic receipt ile imzalı + public URL'li**; Dosu yanıtı sadece GitHub metni |
| **Sweep.dev, AutoPR** | Kod değişikliği otomasyonu | Orthogonal — Sentinel yanıt katmanı, onlar kod katmanı |
| **CodeRabbit, Greptile, Bito** | PR review | Orthogonal — Sentinel issue/discussion, onlar PR |
| **Linear Triage, GitHub Copilot Chat** | Dahili task otomasyonu | Sentinel public-facing yanıt veriyor, onlar internal |

**Moat**: 
1. Receipt-per-reply (cryptographic provenance for AI output — zaten GARL'ın temel pitch'i)
2. Multi-channel (GitHub + Twitter + HN + dev.to aynı agent, unified signal)
3. Self-dogfood kanıtı — "biz kendi ürünümüzü kullanıyoruz" marketing asset
4. Multi-tenant SaaS potansiyeli

---

## 7. Başarı metrikleri (Faz 1 sonrası)

| Metric | Hedef (4 hafta) |
|---|---|
| İnsan onayı sonrası public post oranı | %85+ (draft'ların çoğu minor edit ile geçiyor demek) |
| Issue açılmasından Arda haberdar olana kadar medyan süre | < 5 dk |
| Category classification accuracy (insan kontrollü sample 50) | %90+ |
| Auto-detected task → actual merged PR dönüşüm oranı | %30+ |
| False positive task creation (Arda tarafından kapatılan) | %15 altı |
| Sentinel GARL trust score | 70+ (gold) — kendi itibarı pazarlama değer |

---

## 8. Faz 1 MVP — ilk session task listesi (yeni session bunu uygulasın)

> Yeni session'a "Sentinel F1'i planla ve kur" dediğinde aşağıdaki adımlardan başlayacak. Plan her adım Arda onayı ile ilerlesin, otonom kod dökülmesin.

**P1.1 — Kapsam onayı (plan, kod yok)**
- [ ] Kullanıcıya sor: "Digest kanalı Slack mi email mi?"
- [ ] Kullanıcıya sor: "İlk faz sadece `Garl-Protocol/garl` mi, yoksa `garl-receipt-action` repo'su dahil mi?"
- [ ] Kullanıcıya sor: "Webhook host: Cloudflare Worker mı, backend'e FastAPI route mu?"
- [ ] Kullanıcıya sor: "Sentinel kendi agent'ını GARL'a auto-register edelim mi, yoksa manual mı?"

**P1.2 — Altyapı iskeleti**
- [ ] `backend/app/api/sentinel.py` veya `workers/sentinel/` (P1.1 kararı)
- [ ] `supabase/migrations/v14_garl_signals.sql` (tablo yukarıdaki schema)
- [ ] GitHub App oluştur + webhook secret env (`GITHUB_WEBHOOK_SECRET`)
- [ ] Anthropic API key env (`ANTHROPIC_API_KEY`) — Haiku 4.5 için

**P1.3 — Triage prompt geliştirme**
- [ ] System prompt draft (yukarıdaki özet → full)
- [ ] Sample 5 gerçek issue ile manuel test (AI Village #1 dahil)
- [ ] Category accuracy benchmark 50 issue

**P1.4 — Digest**
- [ ] Sabah 09:00 TR cron → son 24 saatin pending signal'larını digest
- [ ] Arda onayı için tek-tık linki (dashboard endpoint veya inline link)

**P1.5 — Observability**
- [ ] Sentry veya basit Supabase log tablosu
- [ ] Haftalık metric rapor (başarı metrikleri tablosu)

**P1.6 — Pilot çalıştırma (1 hafta)**
- [ ] Sadece triage + digest; hiçbir public post yok
- [ ] AI Village issue'suna retrospectively çalıştır (gerçek veri testi)
- [ ] 1 hafta sonunda review, F2'ye geçiş kararı

---

## 9. Faz 2–5 roadmap (kısa)

- **F2**: GitHub Discussion'da "draft preview" thread, Arda onayı ile public post + GARL trace imzala.
- **F3**: `safe_for_auto_reply=true` kategorileri otomatik post, hepsi Sentinel agent ID ile imzalanmış, receipt URL yorumda.
- **F4**: Twitter API (paid tier) + HN Algolia API + Reddit PRAW + dev.to firehose → same triage engine → same digest.
- **F5**: Multi-tenant SaaS — GitHub App, her install kendi config + billing, Stripe bağlantısı, dashboard.garl.ai/sentinel panel.

---

## 10. F2 (PR bot) ile birleşim

`audit_2026-04-15.md` içindeki F2 (PR bot: "AI commit %") **aynı altyapıyı paylaşıyor**:
- Aynı webhook handler, farklı event tipleri
- Aynı GARL trace imzalama pattern'i
- Aynı "AI-generated content GARL receipt ile imzalanır" narrative'i

Sıra önerisi:
1. **F2 (PR bot) önce** — daha dar kapsam, daha net value, iyi test bed
2. **Sentinel F1 (triage-only)** — F2 altyapısının üstüne
3. **Sentinel F2 (draft)** + F2 (PR bot) aynı anda kamuya GARL-signed content üretiyor
4. **Sentinel F5 SaaS** — iki ürünü birleştir: "GARL Sentinel + PR bot" combo install

Ortak kod: `packages/garl-github-core/` (webhook + GARL trace submit + reply builder).

---

## 11. Pazarlama açısı — dogfood narrative'i

Launch post/landing/docs için hazır paragraf:

> "GARL Sentinel, GitHub issue'larımızı okur, triage eder ve cevap yazar — ama her yazdığı cevap kendi GARL receipt'iyle imzalı. Bir yorumun Sentinel tarafından yazıldığını merak ediyorsan, altındaki `garl.ai/r/xxxxx` linkine tıkla, imzayı doğrula, trust history'sini gör. Biz kendi ürünümüzü her yorum için kullanıyoruz."

Bu cümle ChatGPT'nin "made with ChatGPT" footer'ının cryptographically-verifiable versiyonu. **Pazarlama asset'i burada.**

---

## 12. Yeni session'a ilk prompt (Arda için hazır)

> GARL için yeni bir side-project başlatıyoruz: **GARL Sentinel**. Proje brief'i `sentinel_project.md` dosyasında. Dosyayı oku, memory'yi oku, sonra **P1.1 kapsam sorularını** (brief'in Faz 1 MVP başlığı altında) bana sor. Cevaplarımı aldıktan sonra Faz 1 için detaylı plan çıkar, plan onayından önce kod yazma. Tek ilerleme birimi: plan onayı → kod → atomic commit → doğrulama → sonraki step. Türkçe tablolu iletişim, `feedback_collaboration_style.md` kurallarına uy.

---

_Brief kaynağı: 2026-04-15 Opus 4.6 denetim + brainstorm session'ı._
_İlişkili: `audit_2026-04-15.md` (GARL audit), `project_garl_overview.md` (GARL v1.1.0 state), AI Village issue `Garl-Protocol/garl#1` (kullanım senaryosu kaynak olayı)._
