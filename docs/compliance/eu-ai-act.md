# GARL × EU AI Act Articles 12 & 19 (logging and record-keeping)

**Reference:** Regulation (EU) 2024/1689 (the AI Act), Article 12
(*record-keeping* — automatic recording of events over the lifetime of a
high-risk AI system) and Article 19 (*automatically generated logs* — the
provider keeps the Article 12 logs, for at least six months unless other
law says longer).

**Scope of this document:** how GARL's signed Action Receipts and the
Evidence Pack export map to what those articles ask for. This is an
engineering-accuracy document, not legal advice, and GARL is evidence
tooling, not a conformity assessment.

## The one-line summary

Every action an agent reports mints a signed, append-only receipt; the
**Evidence Pack** (`GET /api/v1/receipts/{id}/evidence-pack`, also as
`.pdf`) bundles one receipt with its authorization chain, Merkle inclusion
proof, on-chain anchor, surrounding session alerts, and the key registry —
one self-contained, offline-verifiable log unit an operator can export and
retain locally.

## Article 12 — automatic recording of events

Article 12(1) requires high-risk AI systems to *technically allow the
automatic recording of events (logs) over the lifetime of the system*.
Article 12(2) sketches what the logs must at minimum enable for the
Article 79(1) risk scenarios: identifying periods of use, the reference
data checked, the inputs involved, and the persons involved in
verification.

How receipt envelope fields (`garl/action-receipt/v0.1`) map:

| Art. 12(2)-style requirement | GARL field(s) | Notes |
|---|---|---|
| (a) Recording of the period of each use (start/end timestamps) | `timestamp` on every receipt; `previous_receipt_hash` chains consecutive receipts into an ordered, tamper-evident sequence per agent session | A session's span is the first-to-last receipt in the chain; gaps are visible because each link commits to its predecessor |
| (b) The reference database against which input data has been checked | **Not applicable to GARL** — GARL is not a biometric-identification system and records no reference-database lookups. If your system performs them, log them as receipts (`action_type: api_call`, `tool_server` naming the database) — but GARL does not synthesize this field for you | Honest gap: stated rather than papered over |
| (c) The input data for which the search has led to a match | `input_hash` + `hash_scheme` — a commitment to the exact input, keyed (HMAC-SHA-256) by default so the hash itself is not personal data | The operator retains the payload; the receipt proves *which* input it was without GARL ever holding it. See [edpb.md](edpb.md) for the ¶52 hashing/GDPR analysis |
| (d) Identification of the natural persons involved in verification | `human_delegate` (the human on whose behalf the agent acts) + `policy_decision: requires_human` (actions gated on human sign-off) | Identification is by the operator-supplied delegate identifier; GARL does not verify natural-person identity |

Additional lifecycle facts each receipt records automatically: the acting
agent (`agent_identity`, a DID), the runtime and protocol, the action type
and side-effect class, the output commitment (`output_hash`), the
authorization used (`capability_request.token_hash`, expandable to the
full chain in the Evidence Pack), and the registry's ECDSA-secp256k1
signature over all of it.

## Article 19 — keeping the logs

Article 19(1): providers keep the automatically generated logs, to the
extent under their control, **for at least six months**.

- **The Evidence Pack is the exportable log unit.** One receipt →
  one signed, self-contained JSON (or PDF) bundle. It embeds everything an
  auditor needs to verify it offline — envelope, capability chain, Merkle
  proof, anchor coordinates, key registry, verification steps — so a pack
  exported today remains verifiable even if garl.ai disappears tomorrow.
- **Retention story.** GARL's ledger is append-only Postgres; receipt
  batches are Merkle-rooted and anchored on Base mainnet (contract
  `0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2`, chain 8453; every batch
  listed at [garl.ai/anchors](https://garl.ai/anchors)). Silent truncation
  or retro-editing of the log is therefore *detectable*: a removed or
  altered receipt no longer proves inclusion under the anchored root.
- **The operator exports packs for local retention.** GARL keeping the
  hosted ledger does not discharge the provider's own Article 19 duty —
  logs must be kept "to the extent [they] are under their control".
  Export the pack per receipt (or bulk export via
  `GET /api/v1/agents/{id}/audit`) and retain it >= 6 months under your
  own retention regime. The pack's `retention.policy` field states this.

## Timeline and standards status — plainly

- **No harmonized standard for AI Act logging exists yet.** CEN-CENELEC
  JTC 21 has published **zero** logging standards as of August 2026; the
  harmonized-standards programme is running late across the board. GARL's
  Evidence Pack is a **candidate format** — a concrete, verifiable shape
  you can use today — not "the" Article 12 format, because no such thing
  has been standardized.
- **The obligations bind high-risk systems from 2 December 2027**
  (the extended Article 6 high-risk application date). Prohibitions and
  GPAI duties started earlier, but Article 12/19 record-keeping bites with
  the high-risk regime.
- **GARL is evidence tooling, not a conformity assessment.** Using GARL
  does not make a system compliant; it produces tamper-evident records
  that a compliance process can rely on.

## Limitations, stated up-front

- **GARL records what the agent reports.** A receipt proves that a
  specific, signed statement was made at a specific time and was never
  altered afterwards — not that the statement was true. Runtime-level
  attestation (CI-witnessed receipts via `garl-receipt-action`) narrows
  this gap for the git rail; for other rails it remains.
- **Coverage equals instrumentation.** Actions the operator never submits
  never become receipts. Article 12 asks for *automatic* recording over
  the lifetime — that property holds only if the agent runtime is wired
  to emit a receipt per action (see [/connect](https://garl.ai/connect)).
- **Art. 12(2)(b) reference-database logging is not synthesized.** See
  the table above — GARL will faithfully record such checks *if the
  operator logs them as actions*, and does nothing otherwise.
- **The six-month clock is the operator's.** GARL currently retains the
  hosted ledger indefinitely, but makes no contractual retention promise;
  the exported pack in the operator's own storage is what satisfies
  Article 19, which is why the export exists.
- **Hashes, not payloads.** Inputs/outputs are recorded as (keyed) hash
  commitments. That is deliberate (data minimisation, see
  [edpb.md](edpb.md)) — but it means reconstructing *content* during an
  investigation requires the operator's retained payloads plus, for keyed
  hashes, the HMAC key. Key destruction (the GDPR erasure mechanism)
  irreversibly degrades that linkage; erasure and evidence retention pull
  in opposite directions and the operator must sequence them consciously.

## Pointers

- Evidence Pack: `GET /api/v1/receipts/{receipt_id}/evidence-pack`
  (JSON, signed) and `.../evidence-pack.pdf` (A4 document);
  implementation `backend/app/services/evidence_pack.py`
- Receipt wire format: `protocol/spec/action-receipt-v0.1.md`
- Hashing / GDPR side: [`docs/compliance/edpb.md`](edpb.md)
- On-chain anchoring: `backend/app/services/merkle_batch.py`,
  `GET /api/v1/receipts/{id}/proof`, [garl.ai/anchors](https://garl.ai/anchors)
- Other export shapes (SB 942, ISO 42001, in-toto): [`docs/compliance.md`](../compliance.md)
