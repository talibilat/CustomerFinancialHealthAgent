# Project agent guidance

Read [docs/research/coding-agent-ingestion.md](./docs/research/coding-agent-ingestion.md) completely before implementing or changing product behavior, architecture, AI authority, persistence, tests, customer content, deployment, or submission documentation.
Treat [docs/research/PRD.md](./docs/research/PRD.md) as the canonical product specification.
Read [CONTEXT.md](./CONTEXT.md) before changing domain language or naming public interfaces.
Use the archived sources under `docs/archive/` only for provenance and deeper source context.

Use vertical red-green TDD cycles at the confirmed seams.
Keep financial arithmetic, result states, warnings, support routes, and history deterministic.
Use Python `Decimal` for money and preserve original values and frequencies alongside normalized monthly values.
Do not let Azure OpenAI calculate money, select results, recommend repayments, choose support routes, mutate snapshots, or access the database.
Keep the complete core journey functional without Azure OpenAI configuration.

Treat confirmed snapshots as immutable.
Create corrections as new snapshots with explicit supersession relationships.
Make customer-scoped ownership explicit even while production authentication is deferred.
Do not log financial line items, raw prompts, AI output, credentials, database URLs, or authorization tokens.

Use calm, qualified, non-judgmental customer language.
Do not describe a non-negative balance as proof of long-term affordability.
Do not rely on color, charts, or AI prose alone to communicate a result.

Do not manually modify generated clients or generated migration output without reviewing how the generation source should change.
Do not claim a run command, test command, deployment, or compliance property that has not been verified.
Keep `DECISIONS.md`, `docs/research/PRD.md`, `docs/research/coding-agent-ingestion.md`, and the README aligned when scope or behavior changes.

## Agent skills

### Issue tracker

Issues and specifications are tracked in GitHub Issues for `talibilat/CustomerFinancialHealthAgent`.
See `docs/agents/issue-tracker.md`.

### Triage labels

The repository uses the default five-role triage vocabulary.
See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository with its canonical glossary in `CONTEXT.md`.
See `docs/agents/domain.md`.
