# Product Requirements Document: Customer Financial Health

## Document status

This PRD is the canonical product specification for the Ophelos Customer Financial Health take-home.
It consolidates the supplied brief, team clarifications, accepted product decisions, repository documentation, primary-source research, architecture decisions, testing strategy, edge cases, and submission requirements.

## Product summary

Customers already record income and regular outgoings in Ophelos.
The product must turn those numbers into a useful, explainable view of the customer's reported financial position.
It must help the customer understand their current monthly position, explore whether repayment options appear realistic, and track whether their position is improving or deteriorating.

The product is a responsive web application with a React and TypeScript frontend, a FastAPI backend, PostgreSQL persistence, and optional bounded Azure OpenAI features.
All financial calculations, result states, warnings, support routes, and historical changes are deterministic.

## Problem statement

Recording financial data without interpretation does not help customers understand what the numbers mean.
Customers currently receive no reflection of their financial position, no clear view of whether repayment options leave enough room, and no history showing what changed.
Many customers may be financially vulnerable, worried, or in arrears, so the product must communicate without blame, false certainty, pressure, or unnecessary complexity.

## Product goals

1. Calculate and display a meaningful, transparent view of reported monthly financial position.
2. Separate recurring monthly cash flow from financial resilience.
3. Let customers explore repayment scenarios without recommending or changing a repayment.
4. Preserve confirmed historical results and explain changes over time.
5. Handle zero income, shortfalls, incomplete information, ambiguous outgoings, and provider failure safely.
6. Demonstrate regulated-context thinking through explainability, data minimization, auditability, customer control, and deterministic support routes.
7. Demonstrate practical AI engineering without placing an LLM in the financial decision path.
8. Provide a polished, accessible, reviewer-friendly end-to-end vertical slice.

## Non-goals

The committed product does not provide production authentication, real customer accounts, Open Banking, bank-statement ingestion, payslip verification, document verification, automated agreement changes, repayment recommendations, personalized investment advice, asset-sale recommendations, a complete Standard Financial Statement, licensed SFS thresholds, a universal financial-health score, autonomous agents, or a conversational financial coach.
It does not claim production readiness, regulatory compliance, or that a non-negative monthly balance proves long-term affordability.
It does not include production monitoring, queues, Redis, Kafka, microservices, GraphQL, Kubernetes, or multi-region infrastructure.

## Target customer

The target customer is a person using Ophelos who has reported income, outgoings, and existing repayment commitments.
The customer may be in debt, have limited financial resilience, experience income volatility, or have characteristics of vulnerability.
The interface must assume that financial information can be stressful and that the customer may need clear explanations, correction paths, and human support.

## Product principles

- Lead with exact amounts and the most important answer.
- Use calm, qualified, non-judgmental language.
- Show the arithmetic and source information behind every result.
- Treat flexible living costs as real costs rather than automatically disposable money.
- Protect customer-defined monthly buffers and emergency reserves.
- Keep recurring cash flow separate from savings and resilience.
- Allow correction before confirmation.
- Preserve confirmed history rather than silently recalculating or overwriting it.
- Keep AI optional, bounded, reviewable, and replaceable.
- Keep the complete core journey functional without Azure OpenAI.
- Show deterministic support routes when the reported position indicates difficulty.
- Use fictional data only in the take-home demonstration.

## Canonical domain language

### Financial statement

The customer's current editable collection of reported income, outgoings, existing repayment commitments, and optional resilience information for one statement period.

### Statement period

The calendar month that a financial statement describes, regardless of when the customer confirms it.

### Income entry

A customer-reported receipt with an amount and frequency that contributes to monthly income.

### Outgoing

A customer-reported living cost, bill, provision, or repayment with an amount and frequency that contributes to monthly outgoings.

### Existing repayment commitment

A recurring debt payment already included in the financial statement.

### Known arrears

An amount the customer reports as overdue, kept distinct from a recurring outgoing or an agreed repayment commitment.

### Confirmed snapshot

An immutable historical record of a financial statement and the results calculated when the customer confirmed it.

### Effective snapshot

The confirmed snapshot that currently represents a statement period because it has not been superseded by a correction.

### Correction

A new confirmed snapshot that supersedes an earlier snapshot without altering or deleting the earlier record.

### Monthly headroom

The amount remaining after normalized monthly outgoings are subtracted from normalized monthly income.
The term disposable income must not be used because monthly headroom is not automatically available for repayment.

### Protected monthly buffer

The amount the customer wants to keep available each month for unexpected or changing costs.
It is customer-defined and is not presented as an FCA threshold.

### Accessible savings

Money the customer reports as readily available.
It contributes to the resilience view and never becomes recurring monthly income.

### Protected reserve

The portion of accessible savings the customer wants to preserve for emergencies or future needs.

### Repayment scenario

A what-if comparison that changes one existing repayment or adds a hypothetical repayment without modifying its basis snapshot.

### Basis snapshot

The confirmed snapshot whose reported values a repayment scenario compares against.

### Display category

A customer-friendly outgoing label such as Housing, Food and housekeeping, or Leisure and hobbies.

### Outgoing treatment

One of four deterministic ways an outgoing participates in explanations: protected outgoing, existing credit commitment, flexible living cost, or protected future provision.

### Protected outgoing

An essential living cost or priority commitment that is protected before exploring an unsecured repayment.

### Existing credit commitment

An existing repayment commitment shown separately from other outgoings when explaining the customer's position.

### Flexible living cost

A genuine reported living cost whose amount may vary, without implying that it is unnecessary or available for repayment.

### Protected future provision

A recurring amount the customer has chosen to set aside for known irregular costs, contingency, or a future need.

## Domain boundary examples

### Overdue rent and an agreed arrears payment

Current rent is a protected outgoing.
Overdue rent is known arrears and is not silently added to monthly outgoings.
If the customer has agreed a recurring payment toward those arrears, that payment is a separate existing repayment commitment.

### Savings alongside a monthly shortfall

Accessible savings may improve the resilience result, but they do not change monthly income or erase a monthly shortfall.
The protected reserve remains unavailable to repayment exploration unless the customer explicitly changes it.

### Two confirmations for the same month

If the customer corrects a confirmed January statement in February, both confirmed snapshots retain the January statement period.
The correction becomes January's effective snapshot, while the original remains in the audit history.

### Ambiguous merchant description

An outgoing described as Apple does not become Food and housekeeping merely because a model is confident.
It remains a classification suggestion until the customer confirms what the purchase represented and accepts or corrects both its display category and outgoing treatment.

### A variable but necessary cost

A transport outgoing may have a variable amount while still being protected because the customer needs it for work, disability, or caring responsibilities.
Flexible describes the treatment of a reported amount, not whether the cost is frivolous or automatically reducible.

## Primary customer journey

### Overview

The overview shows the current monthly position, resilience summary, change since the previous snapshot, important warnings, deterministic explanation, and clear next actions.
The primary actions are Review how this was calculated, Update my information, Explore a repayment option, View history, and optionally Explain this more simply.

### Update my information

The update flow begins with the income and regular outgoings already collected by Ophelos.
The customer may add or edit entries, confirm outgoing classifications, add optional resilience and looking-ahead information, preview the changed result, review a confirmation checklist, and save a new snapshot.

### Explore a repayment option

The customer chooses whether to change one existing repayment or add a hypothetical repayment.
The product compares the scenario with the latest effective snapshot and the protected monthly buffer.
The scenario is temporary by default and may be saved separately.
It never changes its basis snapshot or recommends a repayment amount.

### History

The history view shows income, outgoings, monthly headroom, optional resilience, previous results, snapshot lineage, and a deterministic explanation of the main changes.
The monthly chart uses the effective snapshot for each statement period.
The complete history retains every snapshot and correction.

## Information model

### Core information

- Net income amount and frequency.
- Regular outgoing amount and frequency.
- Existing debt-repayment amount and frequency.
- Display category and outgoing treatment.
- Statement period.

Core information is sufficient for an immediate monthly-position result.

### Optional resilience information

- Current-account balance.
- Accessible savings.
- Protected emergency reserve.
- Known arrears.

### Optional looking-ahead information

- Annual or irregular costs.
- Expected income changes.
- Expected expenditure changes.
- Monthly savings or contingency contribution.
- Future financial goals.

Missing optional information produces a clear limitation and does not block the core result.

## Money and frequency rules

All backend monetary calculations use Python `Decimal`.
Database monetary values use fixed-precision PostgreSQL numeric columns.
Negative income, outgoing, repayment, savings, and reserve values are rejected, while an overdraft is represented explicitly as a negative account balance or debt.
The application preserves original amounts and frequencies alongside normalized monthly values.

Supported frequencies are weekly, fortnightly, four-weekly, monthly, quarterly, and annual.
Weekly values use `amount * 52 / 12`.
Fortnightly values use `amount * 26 / 12`.
Four-weekly values use `amount * 13 / 12`.
Quarterly values use `amount * 4 / 12`.
Annual values use `amount / 12`.
The normalization and rounding policy is versioned.
The initial product supports GBP and displays values using the `en-GB` locale.
Multi-currency conversion and exchange-rate risk are future scope.

## Calculation requirements

### Monthly position

```text
monthly headroom = normalized monthly income - normalized monthly outgoings
```

The result reports the exact positive amount, zero balance, or shortfall.
It does not classify a customer as healthy or unhealthy.

### Financial resilience

```text
savings above protected reserve =
  max(0, accessible savings - protected reserve)
```

The application separately reports any reserve gap.
A monthly deficit remains a deficit even when accessible savings can cover it temporarily.

### Repayment scenario

For an additional payment:

```text
scenario headroom = monthly headroom - added repayment
```

For a changed existing payment, the selected existing amount is removed once and the scenario amount is added once.
Switching scenario mode recalculates from the original confirmed snapshot and clears incompatible fields.

## Result requirements

The current-position result reports whether income exceeds, equals, or falls below reported outgoings and shows the exact amount.
The resilience result reports whether optional accessible savings are below, equal to, or above the protected reserve.
The scenario result uses `not enough reported headroom`, `may leave limited room`, or `appears manageable from the information provided`.

The application must not call a positive balance proof of sustainability.
Every result must include the source totals, formula, information limitations, warning codes, and applicable support routes.

## Outgoing taxonomy

Customer-facing categories include Housing, Council tax and priority bills, Utilities, Food and housekeeping, Transport, Health and care, Children and dependants, Communications, Insurance, Existing debt repayments, Leisure and hobbies, Savings and future provisions, and Other.

Each category maps to one of:

```text
PROTECTED_OUTGOING
EXISTING_CREDIT_COMMITMENT
FLEXIBLE_LIVING_COST
PROTECTED_FUTURE_PROVISION
```

`PROTECTED_OUTGOING` covers both essential living costs and priority commitments without claiming that every essential cost is a legally defined priority debt.
`FLEXIBLE_LIVING_COST` remains a genuine reported cost and is never treated automatically as spare repayment money.
The customer may correct the default treatment where their circumstances differ.
Transport, communications, or another normally flexible category may be essential because of work, disability, caring, or another individual circumstance.

## Outgoing-classification workflow

1. Check a customer-specific confirmed preference.
2. Check normalized deterministic rules and synonyms.
3. Request an Azure OpenAI suggestion only when the description remains unknown or ambiguous.
4. Present the suggestion, confidence, reason, and clarification requirement.
5. Require customer confirmation before the classification can enter a confirmed snapshot.
6. Store the confirmed classification and its source.
7. Create a customer-specific preference when the customer corrects a suggestion.

Known entries such as rent and groceries must not call Azure OpenAI.
Ambiguous entries such as Apple, Amazon, and Transfer must require confirmation or clarification regardless of model confidence.
Global prompt changes occur only through reviewed, versioned, offline evaluation.

## Personalized explanation workflow

The deterministic explanation is always available.
The customer explicitly requests optional personalized wording.
The guidance adapter receives only approved amounts, result codes, warning codes, and deterministic changes.
The response is tied to the snapshot and stores deployment, prompt version, schema version, request outcome, and creation time.
The application rejects wording that adds unsupported numbers, causation, advice, category instructions, repayment recommendations, changed statuses, links, HTML, or judgmental language.

## Azure OpenAI requirements

Use the official OpenAI Python SDK against Azure OpenAI's GA v1 endpoint.
Build the SDK base URL by appending `/openai/v1/` to the configured Azure resource endpoint.
Pass the Azure deployment name in the SDK `model` field.
Do not configure a dated Azure API version for this v1 design.
Use the Responses API and Pydantic Structured Outputs.
Set `store=False` and do not use stateful response chaining.
Use a 10-second timeout and one retry.

The portable demo supports API-key authentication.
Production should prefer Microsoft Entra ID with least-privilege deployment access.
The application supports separate classification and guidance deployment variables and permits both to contain the same deployment name.

Azure failure, timeout, 401, 403, 429, 5xx, refusal, content filtering, incomplete response, schema failure, and ungrounded output must produce deterministic fallback behavior.
Azure availability does not affect application readiness because AI is optional.

## Azure environment contract

```dotenv
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE-NAME.openai.azure.com
AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT=your-classification-deployment
AZURE_OPENAI_GUIDANCE_DEPLOYMENT=your-guidance-deployment
AZURE_OPENAI_AUTH_MODE=api_key
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_TIMEOUT_SECONDS=10
AZURE_OPENAI_MAX_RETRIES=1
AZURE_OPENAI_STORE=false
AZURE_CLIENT_ID=
```

Optional service-principal variables are `AZURE_TENANT_ID` and `AZURE_CLIENT_SECRET`.
Secrets must never appear in `.env.example`, source control, images, logs, prompts, or client-side bundles.

## Customer confirmation

Before confirmation, the customer reviews income, regular costs, existing repayments, known irregular costs, expected changes, and unresolved classifications.
The customer confirms that they have checked the information and believe it reflects their current circumstances.
The product records the confirmation time, missing optional sections, confirmed classifications, warnings, and calculation-policy version.
The confirmation is not represented as independent verification.

## Snapshot and correction requirements

Confirmed snapshots are immutable.
Each snapshot stores original entries, original frequencies, normalized values, confirmed categories, outgoing treatments, calculated outputs, warnings, policy version, statement period, and confirmation time.
A correction creates a new snapshot with a `supersedes_snapshot_id` relationship and a correction reason.
The original snapshot remains visible in the audit history and is excluded from the current monthly chart selection.
Corrections may themselves be corrected while preserving one valid current successor chain.

## Scenario persistence

Repayment scenarios are temporary by default.
The customer may explicitly save a scenario with its basis snapshot, mode, selected repayment, amount, protected buffer, result, and creation time.
A scenario based on a later-superseded snapshot remains tied to its original basis and is clearly marked.

## History and change explanation

The first snapshot establishes a baseline and does not fabricate a trend.
History is ordered by statement period and confirmation time rather than database insertion order.
The deterministic change explanation identifies the main increases and decreases and ensures their signed sum matches the total headroom change.
The application never infers a cause such as a job change unless that fact was explicitly supplied.
Historical outputs are displayed using their stored calculation-policy and taxonomy versions rather than recalculated silently.

## Support and vulnerable-customer requirements

Zero income, uncovered essential costs, and reported shortfalls trigger deterministic support panels.
The customer can review their information, contact an Ophelos support placeholder, or open the official MoneyHelper Debt Advice Locator.
The AI cannot decide whether support appears.

The interface must not use blame, urgency manipulation, celebration, pressure to pay, or phrases such as failed affordability assessment.
Result meaning must be conveyed with text, amounts, and icons rather than color alone.
The interface must remain usable with a keyboard, screen reader, 200 percent zoom, reduced motion, high contrast, narrow mobile viewports, long values, and long text.
Charts must have an equivalent text summary or table.
Dynamic save, classification, preview, and AI states must be announced through appropriate accessible status messages.

## Architecture requirements

### Frontend

- React and TypeScript.
- Vite.
- React Router.
- TanStack Query for remote server state.
- Local feature state for editing the financial statement.
- Generated TypeScript client from FastAPI OpenAPI.
- Vitest and React Testing Library.
- Playwright for end-to-end journeys.

### Backend

- FastAPI as the HTTP adapter.
- Pydantic v2 request, response, settings, and provider schemas.
- Pure Python domain modules without imports from FastAPI, SQLAlchemy, Azure OpenAI, or frontend code.
- Synchronous SQLAlchemy sessions with normal FastAPI `def` handlers for database workflows.
- Explicit application-owned transactions.
- `uv` and a committed Python lockfile.

### Persistence

- PostgreSQL.
- SQLAlchemy 2.0.
- Psycopg 3.
- Alembic migrations.
- Fixed-precision numeric money columns.
- Foreign keys, non-negative amount constraints, ownership constraints, uniqueness rules, and version checks.

### Runtime

- Separate frontend, backend, database, and one-shot migration containers.
- Docker Compose with PostgreSQL readiness checks and dependency conditions.
- Idempotent seed and reset behavior.
- Independent frontend and backend local build capability.

## Module seams

### Financial-health module

The interface accepts an editable financial statement, effective snapshot, or repayment scenario and returns deterministic amounts, result codes, warnings, support codes, and change explanations.

### Outgoing-classification module

The interface accepts an outgoing description and customer context and returns a deterministic match, an unconfirmed provider suggestion, or a request for customer input.

### Guidance module

The interface accepts approved deterministic facts and returns a validated personalized explanation or deterministic fallback copy.

### Statement-history module

The interface confirms financial statements, saves corrections, lists history, and saves repayment scenarios.

## HTTP requirements

The backend exposes workflow-focused REST endpoints rather than generic table CRUD.
Required workflows include current position, history, financial-statement retrieval and update, classification suggestion and confirmation, position preview, statement confirmation, correction, repayment-scenario preview and save, and personalized guidance.

Confirming a statement atomically validates the financial statement, checks classifications, calculates results, stores the snapshot and line items, records policy versions, applies supersession when relevant, and commits one transaction.
Mutation requests use idempotency keys and financial-statement versions so retries and double-clicks cannot duplicate history.
Closed schemas reject unknown enums, authority-bearing fields, calculated fields, malformed JSON, and mass-assignment attempts.

## Identity and authorization

Production authentication is deferred.
Every customer-owned aggregate still contains `customer_id`, and every repository read and write requires customer context.
The local demo uses one fictional customer and does not expose arbitrary customer identifiers as authority.
Cross-customer identifiers must return a consistent non-enumerating response and disclose no metadata.
The demo reset endpoint is enabled only in explicit demo mode.

## Logging and health

Customer errors preserve the unconfirmed financial statement, explain whether a save changed anything, and include a correlation ID where useful.
Structured operational logs may include operation name, safe error category, latency, policy version, deployment identifier, prompt version, schema version, fallback status, and Azure request ID.
Logs must omit financial line items, raw prompts, AI output, API keys, database URLs, authorization tokens, and hidden model reasoning.

`/health/live` reports process liveness.
`/health/ready` verifies PostgreSQL connectivity and compatible migrations.
Azure OpenAI availability is reported as an optional capability and does not make the application unready.

## Testing requirements

Development uses vertical red-green TDD cycles through confirmed public interfaces.
Expected values come from independent worked examples rather than reimplementing the calculation inside tests.
Internal domain functions are not mocked.
External providers, clocks, and selected infrastructure seams use explicit fakes, while repository integration tests use real PostgreSQL.

### Domain tests

Cover zero income, zero outgoings, exact zero headroom, one-penny shortfalls, repayment boundaries, protected-buffer boundaries, invalid values, large values, decimal precision, frequency normalization, and monotonicity invariants.

### Classification and guidance tests

Cover preference precedence, deterministic rules, ambiguity, confirmation, correction learning, prompt injection, invalid categories, extra fields, malformed output, refusal, filtering, timeout, rate limiting, unsupported claims, and deterministic fallback.

### PostgreSQL integration tests

Cover migrations, atomic confirmation, rollback, immutability, supersession, ownership, concurrency, idempotency, stale versions, decimal precision, preference uniqueness, policy-version persistence, and safe database-error translation.

### API tests

Cover closed schemas, malformed requests, wrong content type, unknown resources, non-enumerating authorization, stale versions, conflicting idempotency keys, pagination, safe internal errors, liveness, readiness, and optional AI capability reporting.

### Frontend tests

Cover classification confirmation, error summaries, focus management, input preservation, loading, provider fallback, protected-buffer comparison, accessible statuses, chart alternatives, long content, keyboard operation, and responsive layout.

### End-to-end tests

Cover the normal seeded journey, known classification, ambiguous classification, snapshot confirmation, history update, repayment exploration, saved scenario, correction, zero income, reported shortfall, essentials not covered, and complete operation without Azure OpenAI.

### Docker smoke test

Cover a fresh clone, absent Azure variables, database readiness, migrations, idempotent seed, restart, persistent data, schema mismatch, frontend-before-backend startup, and health checks.

## Core invariants

1. A higher outgoing cannot improve monthly headroom when other inputs are unchanged.
2. A higher income cannot reduce monthly headroom when other inputs are unchanged.
3. Accessible savings never become recurring monthly income.
4. A protected reserve is never silently treated as repayment money.
5. Unconfirmed AI output never enters a confirmed snapshot.
6. AI output never changes arithmetic, results, warnings, or support routes.
7. A repayment scenario never mutates its basis snapshot.
8. A correction never destroys or edits the original snapshot.
9. Historical snapshots retain the inputs, outputs, and policy version shown at confirmation.
10. Failed saves leave no partial snapshot, line items, confirmations, or supersession links.
11. Every customer-scoped operation enforces customer identity.
12. The core journey works without Azure OpenAI.
13. Results never rely on color, chart shape, or AI prose alone.
14. A non-negative balance is never called definitive proof of long-term affordability.

## Demo data requirements

The default fictional customer has six months of realistic history with both improving and worsening periods.
Selectable presets cover zero income, reported shortfall, essential costs not covered, a mixed cash-flow and savings picture, a repayment near the protected buffer, ambiguous Apple classification, improving history, correction, and Azure OpenAI unavailable.
Loading a preset clearly warns that fictional demo data will be reset.

## Regulatory and research basis

FCA CONC 7 is the closest benchmark for sustainable repayment arrangements in arrears and collections.
FCA CONC 5.2A and CONC 8.5 provide supporting principles for individualized information, accuracy, verification, and sustainability without being represented as direct compliance claims for the prototype.
Priority debts and essential living expenses must be protected before unsecured debt repayment.
No universal FCA affordability percentage is used.
Standard Financial Statement categories may inform structure, but licensed current guideline values are not copied, invented, or claimed as implemented.
Consumer Duty principles inform clear, fair, understandable communication and support for vulnerable customers.
MoneyHelper provides the external free debt-advice route.

## Privacy requirements

Use fictional customers and avoid direct identifiers, bank credentials, account numbers, and unnecessary free text.
Send Azure OpenAI only the minimum facts required for each bounded call.
Use stateless Azure requests and explicit local retention controls.
Provide a demo deletion and reset workflow.
Document production requirements for lawful basis, customer notice, consent where applicable, authorization, encryption, retention, deletion, subject access, processor contracts, regional deployment, and a privacy impact assessment.

## Delivery and deployment

The required delivery is a reliable local Docker Compose workflow.
A public deployment is optional only after the core product, tests, accessibility, and documentation are complete.
Any public demo uses fictional data, server-side Azure calls, protected secrets, explicit demo wording, controlled reset behavior, and disabled unsafe operations.

## Stretch order

1. Add `currency` and `country_code` through an explicit tested schema migration while retaining GBP-only behavior.
2. Add secure statement sharing through a time-limited link if core quality remains complete.
3. Add branded PDF export last.

Every attempted stretch feature requires meaningful automated tests.

## Implementation order

1. Build the pure financial-health module through red-green TDD.
2. Add all P0 money, frequency, buffer, savings, and scenario boundaries.
3. Add PostgreSQL schema, Alembic migrations, repositories, atomic confirmation, and integration tests.
4. Add thin FastAPI workflow endpoints and generate the TypeScript client.
5. Build the seeded React overview, update, repayment, and history journeys.
6. Add deterministic classification and customer preferences.
7. Add Azure classification and explanation adapters with fallbacks.
8. Add Playwright journeys and Docker Compose clean-start verification.
9. Polish accessibility, content, documentation, and screenshots.
10. Attempt gated deployment and stretch work only after the core is complete.

## Acceptance criteria

- The customer receives a clear monthly-position result from existing income and outgoing data.
- The customer may add optional resilience and future information without making it mandatory.
- The customer can inspect the calculation and limitations behind every result.
- The customer can explore both changed and additional repayment scenarios without receiving a recommendation.
- The customer can confirm a snapshot, view history, and correct a snapshot without losing the original.
- History explains exactly which reported amounts changed.
- Known outgoings classify deterministically and ambiguous outgoings require confirmation.
- Azure OpenAI explanations are optional, grounded, validated, and replaceable by deterministic copy.
- Zero income, shortfalls, uncovered essentials, and AI failure have deliberate safe experiences.
- The application starts and completes its core journey without Azure credentials.
- PostgreSQL transactions prevent partial or duplicate financial history.
- The highest-risk domain, provider, database, API, accessibility, and browser cases are automated.
- Docker Compose provides a verified reviewer workflow.
- The README, decisions, prompt history, time spent, screenshots, and test commands are ready before submission.

## Submission requirements

The final submission includes the GitHub repository, verified README run instructions, complete AI prompt history, `DECISIONS.md`, actual time spent, architecture and calculation explanations, research references, test commands, known limitations, security and privacy notes, screenshots or a short demonstration, and an optional public URL.
The repository must be public or shared with the reviewers and sent at least 24 hours before the interview.

## Documentation architecture

The active `docs/research/` folder contains only this canonical PRD and `coding-agent-ingestion.md`.
The ingestion document contains the canonical glossary, the full PRD, and every detail from the Markdown sources that existed in `docs/` before consolidation.
The original source documents are preserved under `docs/archive/` for provenance and rejected-option history.
The root README points reviewers to the active documents, while `CLAUDE.md` directs coding agents to ingest the consolidated context before implementation.
The root `CONTEXT.md` remains the concise canonical glossary, `DECISIONS.md` remains the submission-facing decision summary, and `.env.example` remains the executable configuration contract.

## Current repository state

Discovery, primary-source research, domain language, architecture decisions, design, test seams, Azure configuration, edge-case prioritization, and submission planning are complete.
The connected React, FastAPI, PostgreSQL, Azure-adapter, migration, and Docker Compose implementation is complete for the committed take-home scope.
Automated coverage includes domain, provider, persistence, API, component, accessibility, connected browser, generated-client, and clean-environment checks.
The repository includes reviewer run commands, an edited three-chat AI history, a reconstructed and clearly qualified time record, interview preparation, and screenshots of the connected journey.
Production authentication, arbitrary customer statement-period creation, a public deployment, and the listed stretch features remain outside the committed take-home scope.
