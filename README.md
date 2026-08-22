# Customer Financial Health

A customer-facing financial-health feature for the Ophelos engineering take-home.

The product turns existing income and outgoing records into an explainable monthly position, optional financial-resilience view, repayment scenarios, and immutable history.
Financial results are deterministic and auditable.
Azure OpenAI is limited to unconfirmed outgoing-classification suggestions and optional personalized explanations.

## Status

Product discovery, primary-source research, domain language, architecture decisions, test seams, and Azure configuration have been prepared.
Application implementation is the next step and will follow vertical test-driven slices.

## Product principles

- Lead with exact amounts and calm plain language.
- Protect essential costs, flexible living costs, and customer-defined reserves before discussing repayment scenarios.
- Keep monthly cash flow separate from accessible savings and resilience.
- Never let AI calculate money, choose a result, recommend a repayment, or select support.
- Preserve confirmed historical results through immutable versioned snapshots.
- Keep the complete core journey available without Azure OpenAI.

## Planned reviewer journey

1. Start the frontend, backend, PostgreSQL, and migrations with Docker Compose.
2. Open the seeded customer's financial-health overview.
3. Review the current monthly position, resilience, and historical change.
4. Add a known outgoing and observe deterministic classification.
5. Add an ambiguous outgoing and confirm or correct the Azure OpenAI suggestion.
6. Preview and confirm a new immutable snapshot.
7. Inspect the updated history and deterministic change explanation.
8. Explore and save a repayment scenario without modifying the statement.
9. Request an optional personalized explanation.
10. Load a zero-income, shortfall, correction, or AI-unavailable demonstration state.

The exact run and test commands will be added and verified as each executable slice lands.
The final README will not claim commands that have not been exercised from a clean checkout.

## Documentation

- [Canonical product requirements](./docs/research/PRD.md)
- [Complete coding-agent ingestion context](./docs/research/coding-agent-ingestion.md)
- [Domain language](./CONTEXT.md)
- [Decisions and scope](./DECISIONS.md)
- [Archived source documents](./docs/archive/)

## Configuration

Copy `.env.example` to `.env` when the executable application is available.
The deterministic product will run without Azure OpenAI values.
To enable AI features, provide the Azure resource endpoint, authentication settings, and deployment names described in [.env.example](./.env.example).

Never commit a real Azure OpenAI key.

## Scope

The committed scope covers every Must requirement and the regulated-context, edge-case, and vulnerable-customer considerations in the brief.
Public deployment is optional after the local Docker workflow is complete.
The first gated stretch item is a tested migration adding `currency` and `country_code`.

Production authentication, Open Banking, document verification, repayment recommendations, investment advice, autonomous agents, licensed Standard Financial Statement thresholds, and production compliance claims are explicit non-goals.

## Submission reminders

Before submission, update the time-spent section in `DECISIONS.md`, export the complete AI prompt history, verify every documented command from a clean checkout, and add screenshots or a short demonstration recording.
