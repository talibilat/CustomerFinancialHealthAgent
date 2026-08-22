# Customer Financial Health design

## Product promise

The product helps a customer understand their reported monthly position, financial resilience, repayment scenarios, and direction over time.
It provides qualified information rather than a financial-health score, repayment recommendation, or claim of long-term affordability.

## Experience

The overview leads with the customer's current monthly position, resilience, change since the previous snapshot, warnings, and next actions.
The update flow lets the customer review imported income and outgoings, confirm classifications, add optional resilience information, preview changes, and confirm a new snapshot.
The repayment explorer compares a changed existing repayment or an additional hypothetical repayment without changing the confirmed statement.
The history view shows income, outgoings, monthly headroom, optional resilience, snapshot lineage, and a deterministic account of what changed.

## Calculation model

All money uses decimal arithmetic.
Original amounts and frequencies are retained while weekly, fortnightly, four-weekly, monthly, quarterly, and annual amounts are normalized to an average month using a versioned policy.

```text
monthly headroom = normalized monthly income - normalized monthly outgoings

savings above protected reserve =
  max(0, accessible savings - protected reserve)

scenario headroom =
  monthly headroom - added repayment
```

When a scenario changes an existing repayment, only the selected repayment is replaced in the preview.
Accessible savings never become monthly income, and protected funds are never silently made available for repayment.

## Results

The current-position result reports the exact monthly surplus, zero balance, or shortfall.
The resilience result reports whether optional accessible savings cover the customer-selected protected reserve.
The scenario result is `not enough reported headroom`, `may leave limited room`, or `appears manageable from the information provided`.
Every result exposes the source totals, formula, limitations, warnings, and support routes that produced it.

## Information levels

Existing monthly income, regular outgoings, and existing repayments are sufficient for an immediate core result.
Accessible savings, current-account balance, protected reserve, and arrears add an optional resilience view.
Irregular costs, expected changes, savings contributions, and future goals add an optional looking-ahead view.
Missing optional information produces a clear limitation rather than blocking the core experience.

## Classification

Customer-facing categories map to four affordability treatments: `PRIORITY_ESSENTIAL`, `EXISTING_CREDIT_COMMITMENT`, `FLEXIBLE_LIVING_COST`, and `PROTECTED_FUTURE_PROVISION`.
Classification checks a customer preference first, then deterministic rules, then Azure OpenAI for an unconfirmed suggestion.
Unknown or ambiguous entries require customer confirmation before they can enter a confirmed snapshot.
A customer correction creates an isolated customer preference and never rewrites a global prompt at runtime.

## AI behavior

Azure OpenAI performs two optional one-shot operations: expense-classification suggestion and personalized explanation.
The adapters use strict Pydantic outputs, minimal structured inputs, `store=False`, a short timeout, one retry, and deterministic fallbacks.
The model cannot calculate money, select a result, choose support, mutate a snapshot, recommend a repayment, or access the database.
The complete customer journey works without Azure configuration.

## History and corrections

Every confirmed snapshot is immutable and stores original entries, normalized values, confirmed classifications, calculated outputs, warning codes, policy version, and confirmation time.
A correction creates a new snapshot linked to the earlier one.
Charts use the latest non-superseded confirmed snapshot for each financial period while the detailed history preserves every version.
Repayment scenarios are temporary by default and may be saved separately from financial history.

## Customer care

The interface uses calm, plain, non-judgmental language and never relies on color or AI prose alone.
Zero income, a reported shortfall, or uncovered essential costs trigger deterministic review, human-support, and independent debt-advice routes.
The external support route uses the official MoneyHelper Debt Advice Locator.

## Architecture

The browser application uses React, TypeScript, Vite, React Router, and TanStack Query.
The generated TypeScript client follows FastAPI's OpenAPI document.
The backend uses FastAPI, Pydantic v2, pure Python domain modules, PostgreSQL, SQLAlchemy 2.0, Psycopg 3, and Alembic.
Docker Compose manages separate frontend, backend, database, and migration processes.

FastAPI is an HTTP adapter rather than the owner of business rules.
The financial-health, expense-classification, guidance, and assessment-persistence modules expose the confirmed seams recorded in [TESTING.md](./TESTING.md).

## Scope

Production authentication, Open Banking, document verification, repayment recommendations, investment advice, autonomous agents, a conversational coach, licensed SFS thresholds, and production compliance claims are outside the committed scope.
Public deployment is optional after the local Docker product is complete.
The first gated stretch feature is a tested `currency` and `country_code` schema migration, followed by secure time-limited sharing and PDF export only if time remains.

## Evidence

The regulatory and affordability basis is recorded in [UK affordability research](./research/uk-affordability-methodology.md).
The selected application stack is recorded in [FastAPI and TypeScript stack research](./research/fastapi-typescript-stack.md).
The Azure contract is recorded in [Azure OpenAI integration research](./research/azure-openai-integration.md).
The prioritized risk catalogue is recorded in [the edge-case catalogue](./research/edge-cases.md).
