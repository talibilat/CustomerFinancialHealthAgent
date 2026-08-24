# Customer Financial Health

A customer-facing financial-health feature for the Ophelos engineering take-home.

The product turns existing income and outgoing records into an explainable monthly position, optional financial-resilience view, repayment scenarios, and immutable history.
Financial results are deterministic and auditable.
Azure OpenAI is limited to unconfirmed outgoing-classification suggestions and optional personalized explanations.

## Status

Product discovery, primary-source research, domain language, architecture decisions, test seams, and Azure configuration are complete.
The first tracer-bullet slice is implemented and verified: Docker Compose starts the frontend, backend, PostgreSQL, and a one-shot migration-and-seed step, and the browser overview shows a seeded fictional customer's normalized monthly income, outgoings, and headroom calculated by the deterministic financial-health module.
Financial resilience is also implemented: the overview separately shows accessible savings, protected reserve, current-account balance, and known arrears, with a below/at/above-reserve result that never changes the monthly cash-flow figures above it.
Outgoings are classified deterministically first: a customer's own remembered correction wins, then global whole-phrase rules.
When configured, Azure OpenAI may propose a bounded classification for an otherwise unknown outgoing.
The proposal is visibly optional, never changes the classification by itself, and ambiguous descriptions still require the customer to confirm their meaning.
Without Azure OpenAI, unknown or ambiguous entries continue through the complete manual classification flow.
The update flow is implemented as well: the customer can review and change their editable financial statement, add and remove income, outgoings, existing repayment commitments, irregular costs, and protected future provisions, supply or omit resilience information, and preview the recalculated position without confirming anything or changing history.
A repayment can be explored against the confirmed snapshot without changing it: the result is limited to not enough reported headroom, may leave limited room, or appears manageable from the information provided, judged only against the customer's own monthly buffer rather than an invented threshold.
A confirmed record can be corrected by creating a new snapshot that supersedes it; the original is never edited or deleted and stays visible in history with the reason given.
History lists every confirmed record with the policy version, labels, and categories that were stored at the time, and explains changes by decomposing them into reported amounts that reconcile exactly to the change in monthly headroom, without ever inferring a cause.
A reviewed statement can be confirmed as an immutable snapshot in one atomic transaction, with a retry or double-click returning the original record rather than duplicating history.
Unusable values are refused against their own field, an invalid submission preserves everything entered and states that nothing was saved, and a submission built from a superseded version returns a conflict the customer can refresh from.
The frontend uses Tailwind CSS and shadcn/ui components.
The remaining planned journey steps are personalized explanations and demonstration presets.

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
npm ci
npm run test
```

The normal backend suite excludes the separately gated live Azure check.
Run that check only with complete Azure configuration and an explicit opt-in:

```bash
cd backend
RUN_LIVE_AZURE_OPENAI_TESTS=1 uv run pytest -m live -o addopts= tests/live/test_azure_classification_live.py
```

The Playwright journeys start or reuse the Docker Compose application and verify the connected statement preview, the 375px layout, and the complete manual classification and confirmation fallback without Azure:

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```

The suite reuses an already-running stack rather than rebuilding it, so rebuild the frontend image after changing frontend code or the run will test the previous build:

```bash
docker compose up --build -d frontend
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
6. **Done.** See each outgoing classified deterministically. Rent, food, and communications resolve from global rules with no provider involved.
7. **Done.** Add an ambiguous outgoing such as `Apple`. It refuses to guess, asks what it was for, and can remember the answer so the same wording resolves next time regardless of case, spacing, or punctuation.
8. **Done.** With Azure configured, add an unknown outgoing to receive a bounded optional classification proposal. The category and treatment stay empty until the customer explicitly chooses the suggestion. With Azure unavailable or disabled, the same entry follows the manual flow.
9. **Done.** Preview, review the summary, tick that you have checked the information, and confirm. The record is written once even if you double-click, and the screen explains that corrections create a new snapshot rather than editing this one.
10. **Done.** Open **History** to see every confirmed record, one row per statement period with exact amounts, and a deterministic explanation of what moved between the two most recent periods. The first confirmed statement is shown as a starting point rather than a trend.
11. **Done.** Correct a confirmed record from History. The correction becomes the record in effect for that period, the original stays readable at its own values with the reason given, and a correction can itself be corrected.
12. **Done.** Open **Explore a repayment** to compare a hypothetical repayment against your confirmed statement. Both an extra repayment and a change to an existing one are supported, the arithmetic is shown, and nothing is saved, changed, or recommended.
13. Planned: request an optional personalized explanation.
14. Planned: load a zero-income, shortfall, or AI-unavailable demonstration state.

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
