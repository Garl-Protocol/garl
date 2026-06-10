-- v20 (merkle) — Persist the on-chain batchId returned by MerkleAnchor.anchor()
-- so a receipt's inclusion proof always references the correct on-chain batch,
-- instead of assuming DB batch_id == on-chain batchId (an ordering invariant
-- that breaks if a batch is built but its broadcast fails).
--
-- NOTE: two migrations carry the "v20" label in the live history (this one,
-- 2026-06-08, and v20_trace_hash_unique, 2026-06-10). They are independent;
-- the duplicate number is historical. Backfilled into version control
-- 2026-06-10 from supabase_migrations.schema_migrations.

alter table merkle_batches add column if not exists onchain_batch_id integer;

comment on column merkle_batches.onchain_batch_id is
  'The batchId assigned on-chain by MerkleAnchor.anchor(); used by verifyProof. May differ from the DB batch_id if a batch broadcast failed.';

-- Genesis batch: DB batch_id=1 was anchored as on-chain batchId=1 (verified:
-- roots(1) on Base mainnet equals this batch root).
update merkle_batches set onchain_batch_id = 1 where batch_id = 1 and tx_hash is not null and onchain_batch_id is null;
