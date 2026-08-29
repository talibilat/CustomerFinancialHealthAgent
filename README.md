# Customer Financial Health

A customer-facing financial-health feature for the Ophelos engineering take-home.

The product turns existing income and outgoing records into an explainable monthly position, optional financial-resilience view, repayment scenarios, and immutable history.
Financial results are deterministic and auditable.
Azure OpenAI is limited to unconfirmed outgoing-classification suggestions and optional personalized explanations.

![Fictional customer overview showing exact monthly headroom](./docs/assets/overview.png)

![Zero-income demonstration showing exact shortfall and deterministic support](./docs/assets/zero-income.png)

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
Optional personalized explanations are implemented, validated against approved deterministic facts, and replaceable by deterministic copy whenever Azure is unavailable or its output is rejected.

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

GitHub Actions runs frontend lint, component tests, the production build, backend tests against PostgreSQL, the generated-contract check, the isolated Playwright suite, and the clean-environment smoke for pull requests and pushes to `main`.

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

## Architecture

The browser application is React and TypeScript built with Vite. The backend is FastAPI over PostgreSQL. They are separate processes so the API boundary, its schemas, and its transaction handling are visible rather than hidden inside one framework.

**Financial rules live in pure Python domain modules** under `backend/src/customer_financial_health_api/domain/`. They import no FastAPI, no SQLAlchemy, and no provider SDK, so every arithmetic rule is testable without a database or a network. FastAPI is an adapter: it parses, authorizes, calls one domain or repository operation, and translates the result.

**The application owns its transaction boundaries.** Confirming a statement writes the snapshot, its line items, the settled classifications, and the policy versions inside one transaction that either commits together or rolls back together. Concurrency is handled with explicit row locks rather than hope: the editable statement is locked while its version is checked, and the snapshot being corrected is locked while its successor is checked. Both are covered by tests that fail when the lock is removed.

**Confirmed snapshots are immutable.** Nothing updates one after commit. A correction writes a new snapshot linked to the one it supersedes, and a unique constraint on that link means a supersession chain cannot fork even if application code were wrong.

**The TypeScript client is generated** from FastAPI's OpenAPI document and committed. CI regenerates it and fails on a diff, because mocked component tests cannot catch a drifted contract - that happened once during this build and only `tsc -b` caught it.

**Provider adapters are bounded.** Azure OpenAI is consulted only after customer preferences and deterministic rules have failed to settle an entry. Its output is validated before a customer sees it, and every failure path resolves to the same state as having no provider at all.

## How the numbers are calculated

Backend financial calculation and storage use Python `Decimal` and fixed-precision PostgreSQL `NUMERIC(12,2)`.
The frontend keeps monetary values as decimal strings for display, comparison, and sign handling rather than converting them to JavaScript `Number`.

**Frequency normalization** converts a reported amount to an average month using one versioned policy, `normalization-policy-v1`:

```text
weekly       amount * 52 / 12        fortnightly  amount * 26 / 12
four-weekly  amount * 13 / 12        quarterly    amount * 4 / 12
monthly      amount                  annual       amount / 12
```

Each line is quantized to two places with `ROUND_HALF_UP` at that boundary, and the original amount and frequency are always retained beside the normalized value. Four-weekly is deliberately 13 payments a year, not 12.

**Worked example, from the seeded customer** (verified in the running application):

```text
income     Wages                  2450.00 monthly      -> 2450.00
outgoing   Rent                    950.00 monthly      ->  950.00
outgoing   Food and housekeeping   120.00 weekly       ->  520.00
outgoing   Mobile and broadband     45.00 four-weekly  ->   48.75
                                          outgoings    -> 1518.75

monthly headroom = 2450.00 - 1518.75 = 931.25
```

**Resilience is kept separate from cash flow.** `savings above reserve = max(0, savings - reserve)` and `reserve gap = max(0, reserve - savings)`. The seeded customer reports £300.00 savings against a £1,000.00 reserve, giving a £700.00 reserve gap and a below-reserve result, while monthly headroom stays £931.25. Savings never become income and never offset a shortfall.

**Repayment scenarios** compare against an unchanged basis snapshot under `scenario-policy-v1`. Additional mode subtracts the proposal once; change-existing mode frees the selected commitment and adds the replacement once. The result is only ever `not_enough_reported_headroom`, `may_leave_limited_room`, or `appears_manageable_from_the_information_provided`.

Boundaries are explicit and inclusive, verified against the £931.25 basis:

| Proposal | Buffer | Headroom after | Result |
|---|---|---|---|
| 931.25 | 0.00 | 0.00 | appears manageable, plus a limitation that nothing is left |
| 931.26 | - | -0.01 | not enough reported headroom |
| 731.25 | 200.00 | 200.00 | appears manageable (meeting the buffer counts as meeting it) |
| 731.26 | 200.00 | 199.99 | may leave limited room, shortfall 0.01 |
| 100.00 | none | 831.25 | may leave limited room because no protected monthly buffer was provided |

Without a customer-supplied buffer the result stays qualified rather than inventing a threshold to judge against.

**Change explanations reconcile exactly.** Income moves headroom with it and an outgoing moves it against, so the signed component changes always sum to the change in monthly headroom. Offsetting changes stay individually visible while summing to zero. A first snapshot is reported as a baseline, not a trend.

**Policy versions are stored with each snapshot** and read back from storage. Historical results are never recalculated with today's rules.

## Security and privacy

**The data is fictional.** One seeded demonstration customer, no real people, no bank credentials, no account numbers.

**Customer-scoped ownership is enforced, while production identity is deferred.**
The demonstration supplies one fixed fictional customer context instead of authenticating a real person.
Within that context, every customer-owned record carries `customer_id`, and every read and write applies the customer scope.
A request for another customer's statement, snapshot, correction, or saved scenario returns a response byte-identical to one for an identifier that never existed, so ownership cannot be discovered by trying identifiers.
Tests compare whole responses rather than status codes because differing wording would itself leak.

**Data sent to Azure OpenAI is minimal.** Classification receives an outgoing description and the approved category and treatment identifiers. It never receives amounts, the financial statement, or any identifier. Requests are stateless (`store=false`), with a ten-second timeout and one retry.

**Provider output is untrusted.** Structured output guarantees a shape, not trustworthiness. Every response is checked against a closed key set and the category and treatment allow-lists, and its reason must contain no markup, no link, no figure, and no claim of authority. Anything failing becomes no suggestion, which is the same state as having no provider configured.

**Logs deliberately omit almost everything.** An unexpected failure records a correlation identifier, the operation, and the exception type - never the exception message and never a traceback, either of which can carry a connection string, a credential, or a reported amount. This makes production diagnosis harder from logs alone, and it is the only version that cannot leak.

**Browser draft retention is deliberately limited.**
An unfinished editable statement is copied to `sessionStorage` so an accidental refresh in the same browser tab does not discard the customer's work.
The draft is removed after a successful update or confirmation, when the customer chooses to reload the latest saved version, and automatically when the tab session ends.
Production authentication and sign-out would need to clear this state explicitly, namespace it to the authenticated customer, and apply an agreed retention policy.
Only fictional data is used in this demonstration.

**Known limitations, stated plainly.**
This is not production-ready and makes no compliance claim.
There is no production authentication or real customer session, no encryption policy beyond the local PostgreSQL defaults, no retention or deletion service, no rate limiting, and no monitoring.
Customer-scoped object ownership checks are implemented and tested, but they do not replace authentication.
Multi-currency, Open Banking, and dated cash-flow forecasting are out of scope.
The `.env` file is for local use only and must never carry a real key into source control.

## Documentation

- [Canonical product requirements](./docs/research/PRD.md)
- [Complete coding-agent ingestion context](./docs/research/coding-agent-ingestion.md)
- [Domain language](./CONTEXT.md)
- [Decisions and scope](./DECISIONS.md)
- [AI-assisted project history](./AI_PROMPT_HISTORY.md)
- [Submission and interview preparation](./SUBMISSION_AND_INTERVIEW_PREPARATION.md)
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

The take-home demonstrates longitudinal behavior with fictional persisted statement periods, as permitted by the clarification that sample history was acceptable.
The current customer UI does not create or select arbitrary new statement periods.
A production journey would add authenticated period creation and selection while retaining the immutable correction model shown here.

## Submission reminders

Every command documented above has been rerun and passed against the final repository state: the backend suite, the frontend component suite, the clean-environment Docker smoke, the Playwright journeys, and the separately gated live Azure classification check.

The following remain outstanding and can only be done by the candidate. They are listed here because they are not done, not as a checklist that has been completed:

- Confirm whether the reviewer requires raw Codex exports in addition to the curated [AI-assisted project history](./AI_PROMPT_HISTORY.md).
- Confirm the repository is public or shared with the reviewers, and send the submission at least 24 hours before the interview.

No public deployment has been made, so no public URL is claimed.
