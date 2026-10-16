---
name: source-verification
description: Add or verify a public source (fetch, hash, record in the manifest, check terms, confirm a cited claim is supported by the fetched text). Use before citing anything or ingesting a new document.
---

# Source verification

Goal: nothing is cited unless a tool fetched it and the manifest records it.

## Steps

1. **Catalog it.** Add an entry to `SOURCES/catalog.toml` (id, URL, publisher, kind,
   `expected_phrases` that must appear in the opening text, and the terms page). The catalog says
   what to fetch; it is not evidence. New sources need the owner's approval at a decision gate.
2. **Read the terms first.** Fetch the terms page and record a verbatim `terms_quote`. If terms
   are unclear, unreadable, or gated behind a click-through license, STOP and ask the owner. Do
   not accept licenses or call endpoints that issue tokens.
3. **Fetch and verify:** `uv run python -m claims_copilot.sources.fetch <source_id>`. This uses
   the polite client (rate limit, retries, cache), saves the raw file to gitignored `data/raw/`,
   checks `expected_phrases`, hashes the content, and writes the manifest row.
4. **Read the status.** VERIFIED = fetched, phrases found, terms quote found. UNVERIFIED = could
   not fetch or terms unreadable (record why). MISMATCH = fetched but expected text missing; do
   not use the source until resolved.
5. **Checking a claim.** To confirm a statement is supported, find the verbatim sentence in the
   extracted text (`data/text/<source_id>.jsonl`) and quote it with its page. Containment of an
   exact quote is the test; a paraphrase from memory is not.
6. **PMIDs (supplementary only).** Resolve every PMID with NCBI E-utilities and confirm the title
   and abstract match the claim. Until the NCBI client exists, mark any PMID UNVERIFIED.
7. **CPT descriptors.** Extraction redacts them and logs hashes. Never copy descriptor text into
   notes, fixtures, or prompts.

## Report back

One line per source: `source_id | VERIFIED/UNVERIFIED/MISMATCH | sha256[:12] | reason`.
Never invent a PMID, section number, page number, or quote.
