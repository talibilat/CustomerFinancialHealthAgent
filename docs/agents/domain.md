# Domain documentation

This repository uses a single domain context for Customer Financial Health.

## Before exploring or implementing

Read these documents in order:

1. `CONTEXT.md` for canonical domain terms and explicitly avoided synonyms.
2. `docs/research/PRD.md` for canonical product behavior and requirements.
3. `docs/research/coding-agent-ingestion.md` for consolidated decisions, research, testing guidance, and historical context.
4. Relevant accepted ADRs embedded in the ingestion document or preserved under `docs/archive/adr/`.

New ADRs should be added under `docs/adr/` only when the decision is difficult to reverse, surprising without context, and the result of a genuine trade-off.

If an expected domain document does not exist, continue without treating its absence as an error.

## Vocabulary

Use the terms defined in `CONTEXT.md` when naming domain concepts in issues, specifications, tests, interfaces, and implementation plans.

Do not substitute words listed under `_Avoid_`.

If a required concept is missing or conflicts with existing language, use the `domain-modeling` skill before introducing a new term.

## ADR conflicts

Surface any proposal that contradicts an accepted ADR.
Do not silently replace or bypass an existing architectural decision.
