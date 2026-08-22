# Testing strategy

Tests protect customer-visible behavior through the confirmed module and system seams.
They do not test private helpers or reproduce implementation calculations inside assertions.

## Confirmed seams

### Financial-health module

The public interface accepts a confirmed financial statement or repayment scenario and returns deterministic amounts, result codes, warnings, support codes, and change explanations.
Tests exercise this interface with independent worked examples and property-based invariants.

### Expense-classification module

The public interface accepts an expense description and customer context and returns either a deterministic match, an unconfirmed provider suggestion, or a request for customer input.
Tests cover rule precedence, customer preferences, ambiguity, confirmation, correction, adversarial descriptions, and provider fallback.

### Guidance module

The public interface accepts approved deterministic facts and returns either a validated personalized explanation or deterministic fallback copy.
Tests never permit generated wording to alter facts, result states, or support routes.

### Assessment persistence module

The public interface confirms drafts, saves corrections, lists history, and saves repayment scenarios.
PostgreSQL integration tests verify atomicity, idempotency, ownership, immutability, supersession, decimal precision, concurrency, and policy-version persistence through that interface.

### HTTP interface

FastAPI contract tests verify closed request schemas, workflow responses, authorization context, version conflicts, idempotency, safe errors, and health behavior.

### Customer interface

Component and Playwright tests verify the accessible behavior customers use: reviewing a result, classifying an expense, confirming a snapshot, correcting a snapshot, exploring a repayment, reading history, and completing the journey without Azure OpenAI.

## Test order

Development follows one vertical red-green cycle at a time.
The first tracer bullet is a worked monthly-position example through the financial-health module.
The next cycles add one boundary or capability at the same seam before moving outward to persistence, HTTP, and browser behavior.

## Priority

P0 cases in [the edge-case catalogue](./research/edge-cases.md) must be automated where the catalogue identifies a test level.
P1 cases are automated after the complete core journey or documented with a targeted manual check.
P2 cases remain explicit future concerns.

## Provider tests

Ordinary tests use a fake Azure OpenAI adapter with fixtures for success, refusal, invalid schema, timeout, rate limiting, content filtering, and ungrounded output.
A live Azure contract test is separately enabled and never runs in the ordinary deterministic suite.
