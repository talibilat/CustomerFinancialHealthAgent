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
A customer may explicitly save that comparison separately from financial-statement history.
The saved scenario retains its exact basis snapshot, selected commitment where applicable, protected buffer, deterministic result, and policy version.
If that basis is later corrected, the scenario remains unchanged and is plainly marked as using a superseded financial statement.
A confirmed record can be corrected by creating a new snapshot that supersedes it; the original is never edited or deleted and stays visible in history with the reason given.
History lists every confirmed record with the policy version, labels, and categories that were stored at the time, and explains changes by decomposing them into reported amounts that reconcile exactly to the change in monthly headroom, without ever inferring a cause.
A reviewed statement can be confirmed as an immutable snapshot in one atomic transaction, with a retry or double-click returning the original record rather than duplicating history.
Unusable values are refused against their own field, an invalid submission preserves everything entered and states that nothing was saved, and a submission built from a superseded version returns a conflict the customer can refresh from.
The frontend uses Tailwind CSS and shadcn/ui components.
The overview now provides deterministic difficulty states for zero income, incomplete information, reported shortfalls, and protected outgoings that exceed income.
These states preserve exact pennies and select review, Ophelos support, and the official MoneyHelper Debt Advice Locator without using AI.
Nine fictional demonstration presets can be loaded from the overview after an explicit reset warning and confirmation.
Preset retries are idempotent, prior aggregates are preserved, and the reset endpoint is unavailable unless `DEMO_MODE=true`.
The remaining planned journey step is personalized explanations.

## Quick start

```bash
cp .env.example .env  # optional; .env overrides the safe defaults in .env.example
docker compose up --build
```

If those ports are already in use, choose alternatives without editing Compose:

```bash
BACKEND_PORT=8019 FRONTEND_PORT=5189 docker compose up --build
```

Then open http://localhost:5173 for the overview and http://localhost:8000/health/live and http://localhost:8000/health/ready for backend health.
This has been verified from a clean checkout (`docker compose down -v` followed by `docker compose up --build`) with no Azure OpenAI variables set.
The repeatable clean-environment reviewer smoke uses its own Compose project, ports, and disposable volume:

```bash
./scripts/smoke-clean-environment.sh
```

It verifies database readiness, migrations and an empty-volume seed, idempotent seeding, restart persistence, health semantics, operation without Azure configuration, schema mismatch reporting, and a safely contained migration failure.

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

The Playwright journeys verify the connected statement preview, the 375px layout, accessible validation errors, stale-version refresh, the complete manual classification and confirmation fallback without Azure, a saved scenario remaining tied to its original basis after correction, and the zero-income, reported-shortfall, uncovered-protected-cost, and Azure-unavailable presets.
Install Chromium and its operating-system dependencies once, then use the isolated command for repeatable runs:

```bash
cd frontend
npx playwright install --with-deps chromium
npm run test:e2e
```

The isolated command uses a dedicated `cfha-e2e` Compose project on ports `15173` and `18000`, builds fresh images, starts a fresh database volume, waits for readiness, disables Azure OpenAI, runs Chromium serially, and removes that project and volume afterward.
It does not reuse or change the ordinary development stack.
Override its names or ports when needed without editing Compose:

```bash
E2E_COMPOSE_PROJECT_NAME=cfha-e2e-review \
E2E_FRONTEND_PORT=15174 \
E2E_BACKEND_PORT=18001 \
npm run test:e2e
```

To regenerate the OpenAPI document and TypeScript client after a backend API change, and fail if the committed artifacts are stale:

```bash
./scripts/check-generated-client.sh
```

GitHub Actions runs that generated-contract check and the isolated Playwright suite for pull requests and pushes to `main`.

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
8. **Done, and exercised against a live Azure resource.** With Azure configured, add an unknown outgoing to receive a bounded optional classification proposal. The category and treatment stay empty until the customer explicitly chooses the suggestion. With Azure unavailable or disabled, the same entry follows the manual flow.
9. **Done.** Preview, review the summary, tick that you have checked the information, and confirm. The record is written once even if you double-click, and the screen explains that corrections create a new snapshot rather than editing this one.
10. **Done.** Open **History** to see every confirmed record, one row per statement period with exact amounts, and a deterministic explanation of what moved between the two most recent periods. The first confirmed statement is shown as a starting point rather than a trend.
11. **Done.** Correct a confirmed record from History. The correction becomes the record in effect for that period, the original stays readable at its own values with the reason given, and a correction can itself be corrected.
12. **Done.** Open **Explore a repayment** to compare a hypothetical repayment against your confirmed statement. Both an extra repayment and a change to a selected existing commitment are supported, the arithmetic is shown, and nothing is changed or recommended.
13. **Done.** Choose **Save scenario** to retain the comparison separately from statement history. Correct its basis statement, return to the repayment explorer, and see that its original values remain unchanged beneath a superseded-basis notice.
14. **Done.** Choose any of the nine fictional presets on the overview, review the reset warning, and confirm before the active demo view changes.
15. **Done.** Load zero income, reported shortfall, or protected outgoings not covered to see exact deterministic results and support routes that do not depend on Azure.
16. **Done.** Load Azure unavailable, then open **Update my information** to complete the unknown outgoing through manual classification with no AI suggestion or authority.
17. **Done.** Choose **Explain this more simply** on the overview. The deterministic explanation stays visible and usable throughout, wording that fails validation is replaced by deterministic copy, and accepted wording is rendered as plain text rather than markup.

Run and test commands are documented above only once they have been exercised from a clean checkout.

## Documentation

- [Canonical product requirements](./docs/research/PRD.md)
- [Complete coding-agent ingestion context](./docs/research/coding-agent-ingestion.md)
- [Domain language](./CONTEXT.md)
- [Decisions and scope](./DECISIONS.md)
- [Archived source documents](./docs/archive/)

## Configuration

Copy `.env.example` to `.env` to override the safe Docker Compose defaults.
The deterministic product will run without Azure OpenAI values.
The demo preset reset endpoint is available only when `DEMO_MODE=true`; set it to `false` in any non-demo environment.
To enable AI features, provide the Azure resource endpoint, authentication settings, and deployment names described in [.env.example](./.env.example).

Never commit a real Azure OpenAI key.

## Scope

The committed scope covers every Must requirement and the regulated-context, edge-case, and vulnerable-customer considerations in the brief.
Public deployment is optional after the local Docker workflow is complete.
The first gated stretch item is a tested migration adding `currency` and `country_code`.

Production authentication, Open Banking, document verification, repayment recommendations, investment advice, autonomous agents, licensed Standard Financial Statement thresholds, and production compliance claims are explicit non-goals.

## Submission reminders

Before submission, update the time-spent section in `DECISIONS.md`, export the complete AI prompt history, verify every documented command from a clean checkout, and add screenshots or a short demonstration recording.
