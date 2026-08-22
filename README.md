# Customer Financial Health

A customer-facing financial-health feature for the Ophelos engineering take-home.

The product turns existing income and outgoing records into an explainable monthly position, optional financial-resilience view, repayment scenarios, and immutable history.
Financial results are deterministic and auditable.
Azure OpenAI is limited to unconfirmed outgoing-classification suggestions and optional personalized explanations.

## Status

Product discovery, primary-source research, domain language, architecture decisions, test seams, and Azure configuration have been prepared.
The first tracer-bullet slice is implemented and verified: Docker Compose starts the frontend, backend, PostgreSQL, and a one-shot migration-and-seed step, and the browser overview shows a seeded fictional customer's normalized monthly income, outgoings, and headroom calculated by the deterministic financial-health module.
Financial resilience is also implemented: the overview separately shows accessible savings, protected reserve, current-account balance, and known arrears, with a below/at/above-reserve result that never changes the monthly cash-flow figures above it.
The update flow is implemented as well: the customer can review and change their editable financial statement, add and remove income, outgoings, existing repayment commitments, irregular costs, and protected future provisions, supply or omit resilience information, and preview the recalculated position without confirming anything or changing history.
Unusable values are refused against their own field, an invalid submission preserves everything entered and states that nothing was saved, and a submission built from a superseded version returns a conflict the customer can refresh from.
The frontend uses Tailwind CSS and shadcn/ui components.
Later journey steps below (classification, snapshot confirmation, history, repayment scenarios, personalized explanations, demonstration presets) remain planned and will follow the same vertical test-driven approach.

## Quick start

```bash
cp .env.example .env  # optional; Docker Compose also reads .env.example directly
docker compose up --build
```

Then open http://localhost:5173 for the overview and http://localhost:8000/health/live and http://localhost:8000/health/ready for backend health.
This has been verified from a clean checkout (`docker compose down -v` followed by `docker compose up --build`) with no Azure OpenAI variables set.

## Running the tests

Backend tests require a running PostgreSQL instance. The simplest way to get one locally:

```bash
docker run -d --name cfha-test-postgres \
  -e POSTGRES_USER=cfha -e POSTGRES_PASSWORD=cfha_test_password \
  -e POSTGRES_DB=customer_financial_health_test -p 55432:5432 postgres:16-alpine

cd backend
uv run pytest
```

`TEST_DATABASE_URL` defaults to `postgresql+psycopg://cfha:cfha_test_password@localhost:55432/customer_financial_health_test`; override it if you use a different local Postgres.

Frontend component tests:

```bash
cd frontend
npm install
npm run test
```

To regenerate the TypeScript client after a backend API change:

```bash
cd backend && PYTHONPATH=src uv run export-openapi
cd ../frontend && npm run generate-client
```

## Product principles

- Lead with exact amounts and calm plain language.
- Protect essential costs, flexible living costs, and customer-defined reserves before discussing repayment scenarios.
- Keep monthly cash flow separate from accessible savings and resilience.
- Never let AI calculate money, choose a result, recommend a repayment, or select support.
- Preserve confirmed historical results through immutable versioned snapshots.
- Keep the complete core journey available without Azure OpenAI.

## Reviewer journey

1. **Done.** Start the frontend, backend, PostgreSQL, and migrations with Docker Compose.
2. **Done.** Open the seeded customer's financial-health overview, showing normalized monthly income, outgoings, and headroom with the calculation formula, original amounts and frequencies, and calculation-policy version.
3. **Done.** Review financial resilience separately from monthly cash flow: accessible savings, protected reserve, current-account balance, known arrears, and a below/at/above-reserve result that never changes the monthly headroom above it.
4. **Done.** Open **Update my information**, change a reported amount, and preview the recalculated monthly position. The preview states that nothing has been saved, and the overview's confirmed figures are unchanged behind it.
5. **Done.** Enter an unusable amount such as a negative number, a blank, or `NaN`. Every invalid field is listed in an error summary that takes focus and links back to the control, everything already entered is preserved, and the response says nothing was saved.
6. Planned: add a known outgoing and observe deterministic classification.
7. Planned: add an ambiguous outgoing and confirm or correct the Azure OpenAI suggestion.
8. Planned: confirm a new immutable snapshot.
9. Planned: inspect the updated history and deterministic change explanation.
10. Planned: explore and save a repayment scenario without modifying the statement.
11. Planned: request an optional personalized explanation.
12. Planned: load a zero-income, shortfall, correction, or AI-unavailable demonstration state.

Run and test commands are documented above only once they have been exercised from a clean checkout.

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
