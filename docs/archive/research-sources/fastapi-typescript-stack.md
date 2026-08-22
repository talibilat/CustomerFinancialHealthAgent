# FastAPI and TypeScript stack for the take-home

## Recommendation

Use a small three-service system managed by Docker Compose:

```text
React + TypeScript frontend
          |
          v
FastAPI application
          |
          v
PostgreSQL
```

Use FastAPI, Pydantic v2, `pydantic-settings`, SQLAlchemy 2.0, Psycopg 3, Alembic, and the official OpenAI Python SDK configured for Azure OpenAI in the backend.
Use React, TypeScript, Vite, TanStack Query, and a generated OpenAPI client in the frontend.
Use pytest for Python unit and integration tests, Vitest with React Testing Library for focused component tests, and Playwright for the customer journeys.
Use `uv` and a committed `uv.lock` for Python dependencies, and commit the frontend package lockfile.
Pin current stable dependencies through those lockfiles instead of copying exact versions from this research note.

This is a strong fit for a 20-plus-hour take-home because the API boundary and backend design are visible without adding microservices, a message broker, or two server-side web frameworks.

## Why Vite rather than Next.js

The application already has a dedicated FastAPI backend, so Next.js would add a second server runtime and invite uncertainty about which backend owns validation, data access, and business workflows.
Vite officially provides a `react-ts` template and is a focused build tool for the browser application ([Vite guide](https://vite.dev/guide/)).
React Router can be used in its simple declarative mode, whose installation guide starts from a Vite React template ([React Router installation](https://reactrouter.com/start/declarative/installation)).

Use TanStack Query only for remote server state such as the customer statement, history, classification suggestions, and mutations.
Its documented purpose is fetching, caching, synchronizing, and updating server state, so it avoids hand-written loading, refetch, and stale-state logic without becoming a general application store ([TanStack Query overview](https://tanstack.com/query/latest/docs/framework/react/overview)).
Keep draft form state local to the feature instead of introducing Redux.

FastAPI produces an OpenAPI 3.1 document from the declared request and response models.
Its official guide shows generating a TypeScript SDK with Hey API so frontend methods, request payloads, and response payloads remain aligned with the backend ([FastAPI client generation](https://fastapi.tiangolo.com/advanced/generate-clients/)).
Commit the generation command and check in the generated client so a reviewer does not need the backend running merely to build the frontend.
Add a CI check that regenerates the client and fails on a diff.

## Backend module design

Keep FastAPI as an HTTP adapter rather than the place where business rules live.
FastAPI supports splitting larger applications across `APIRouter` modules, while retaining a single application and OpenAPI document ([FastAPI bigger applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)).

A suitable layout is:

```text
backend/
  app/
    api/
      routers/                    HTTP parsing, status codes, response schemas
      dependencies.py            current customer and database session wiring
    modules/
      financial_health/
        domain.py                pure values, policies, calculations, warnings
        application.py           assess and save use cases
        ports.py                 repository and clock protocols
      expense_classification/
        domain.py                taxonomy, confidence, confirmation rules
        application.py           deterministic-first classification workflow
        ports.py                 model and preference protocols
      guidance/
        application.py           grounded explanation and fallback workflow
        ports.py                 text-generation protocol
    infrastructure/
      database/
        models.py                SQLAlchemy persistence models
        repositories.py          port implementations
        session.py               engine, session factory, transaction boundary
      openai/
        classifier.py            OpenAI structured-output adapter
        guidance.py              OpenAI structured-output adapter
    config.py                    validated settings
    main.py                      application composition only
  tests/
    unit/
    integration/
```

The domain modules should not import FastAPI, SQLAlchemy, OpenAI, or frontend concepts.
Use Python `Decimal` for money calculations and PostgreSQL fixed-precision numeric columns, not binary floating-point values.
Pydantic should validate HTTP and provider boundaries, while domain constructors and policies preserve business invariants inside the application.

Prefer a few deep interfaces, such as `AssessmentRepository`, `ExpenseSuggestionProvider`, `CustomerPreferenceRepository`, and `GuidanceGenerator`.
Do not create a repository or service class for every table and rule.
The application use case should own the transaction and coordinate domain behavior, while the repository adapter handles persistence mechanics.

## Validation and configuration

Use Pydantic v2 models for API request and response schemas, including closed enums and constrained decimal values.
Use `pydantic-settings` for database URLs, allowed origins, AI timeouts, model identifiers, and optional credentials.
`BaseSettings` loads typed values from environment variables and supports explicit overrides in tests ([Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)).

Keep all Azure OpenAI configuration optional.
The deterministic classifier and deterministic explanation templates must support the complete core journey when no endpoint, deployment, or credential is present.
Reject impossible values at both the API boundary and, where appropriate, with database constraints.

## Database, transactions, and migrations

Use PostgreSQL with SQLAlchemy 2.0 and Psycopg 3.
For this take-home, use the synchronous SQLAlchemy session API and normal `def` FastAPI route handlers for database-backed workflows.
FastAPI's official concurrency guidance says normal `def` is appropriate for blocking libraries and may be mixed with `async def` where needed ([FastAPI concurrency guidance](https://fastapi.tiangolo.com/async/)).
This removes `AsyncSession` lifecycle complexity without weakening the domain or transaction design.

Use one session per request or use case, and wrap every multi-record save in an explicit transaction.
SQLAlchemy documents `Session.begin()` and `sessionmaker.begin()` as context managers that commit on success and roll back when an exception is raised ([SQLAlchemy session basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#framing-out-a-begin-commit-rollback-block)).
Saving a confirmed draft, its expenses, classifications, calculation output, policy version, and audit metadata should be atomic.

Use Alembic and commit every migration.
Alembic is SQLAlchemy's migration tool, supports upgrades and downgrades, and documents autogeneration as a normal workflow ([Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)).
Always inspect autogenerated migrations before committing them.

Use database constraints for non-negative monetary amounts, valid ownership relationships, uniqueness rules for preference matches, and foreign keys.
Do not update immutable assessment snapshots after creation.
Store calculation-policy version, confirmed category and treatment, classifier source, prompt/schema version where AI was used, and timestamps needed to reproduce the result.

## Azure OpenAI integration

Use the official OpenAI Python SDK against Azure OpenAI's GA v1 base URL and the Responses API through a narrow infrastructure adapter.
Pass the configured Azure deployment name in the SDK's `model` field and do not add a dated API-version setting.
Define Pydantic output models for classification suggestions and personalized explanations.
OpenAI Structured Outputs constrain responses to a supplied JSON Schema, support Pydantic in the Python SDK, and expose refusals programmatically ([OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)).
The exact Azure endpoint, authentication, stateless request, timeout, retry, and environment contract is recorded in [Azure OpenAI integration research](./azure-openai-integration.md).

Schema adherence is not business correctness.
After parsing, application code must still enforce the permitted category IDs, confidence values, clarification rules, maximum text lengths, and customer-confirmation requirement.
The model must never calculate balances, choose the final financial-health status, mutate a saved snapshot, or override deterministic support warnings.

Pass the minimum structured facts required for each call and set `store=False`.
Use a 10-second timeout and one retry, handle refusal and provider failure, and return deterministic fallback copy.
Record the provider, deployment identifier, prompt version, schema version, latency, Azure request ID, and success or fallback status without retaining prompts, financial facts, or model output in logs.

No queue is needed for the initial product.
Classification and optional explanation are user-requested results, so they can be ordinary request-response calls with visible pending states.
FastAPI `BackgroundTasks` run only after the response and are intended for work the client does not need to await; heavier distributed work would require additional infrastructure ([FastAPI background tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)).
Add a real job queue only if future conversational or batch features create a concrete durability or throughput requirement.

## Test strategy

### Backend unit tests

Use pytest for the pure domain and application modules.
FastAPI's test guidance uses pytest directly and provides an HTTPX-based `TestClient` for API tests ([FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)).

Prioritize exact arithmetic, boundary cases, incomplete-information warnings, immutable-snapshot rules, preference precedence, and the invariant that unconfirmed AI output cannot affect an assessment.
Use table-driven parametrized tests for named scenarios.
Hypothesis is a useful optional addition for invariants such as “increasing an expense cannot increase reported headroom,” because it generates many inputs and shrinks failures to simpler examples ([Hypothesis quickstart](https://hypothesis.readthedocs.io/en/latest/quickstart.html)).

Application-service tests should use explicit in-memory fakes for repositories, the model provider, and the clock.
Do not mock internal domain functions merely to increase line coverage.

### Backend integration and API tests

Run repository and API integration tests against real PostgreSQL, not SQLite, because constraints, decimal behavior, migrations, and transaction semantics are part of the backend claim.
Testcontainers for Python can start a temporary PostgreSQL container and provides connection details to the test process ([Testcontainers Python guide](https://testcontainers.com/guides/getting-started-with-testcontainers-for-python/)).
Apply Alembic migrations before the suite and reset test data between cases.

Cover transaction rollback, snapshot immutability, ownership filtering, preference reuse, OpenAPI validation, and persistence of calculation and prompt versions.
Replace the OpenAI adapter with a deterministic fake in ordinary integration tests.
Keep one separately invoked live-provider contract smoke test, skipped unless an API key is available.

### Frontend and end-to-end tests

Use Vitest with React Testing Library for a small number of behavior-focused component tests, especially ambiguous-classification confirmation, validation errors, loading states, and deterministic fallback copy.
Vitest is powered by Vite and supports the same project configuration ([Vitest guide](https://vitest.dev/guide/)).
React Testing Library encourages tests that resemble how the UI is used rather than implementation-detail assertions ([React Testing Library introduction](https://testing-library.com/docs/react-testing-library/intro/)).

Use Playwright for the highest-value browser journeys against the actual frontend, API, and PostgreSQL services.
Its web-first assertions retry until the expected browser state is reached, which reduces timing-based flakiness ([Playwright assertions](https://playwright.dev/docs/test-assertions)).

The core E2E journey should:

1. Open the seeded customer's financial-health statement.
2. Add a known expense and see deterministic classification.
3. Add an ambiguous expense and confirm or correct the suggestion.
4. Preview the updated deterministic assessment.
5. Save an immutable snapshot.
6. Observe the updated history and explanation.

Add one E2E test for provider failure to prove the core journey still works with deterministic fallback behavior.

## Docker Compose topology

Use separate `frontend`, `backend`, and `db` containers under one Compose project.
One primary process per container keeps logs, health checks, restarts, and failure boundaries clear while still giving the reviewer one command.

The database service should have a `pg_isready` health check.
The backend should depend on the database with `condition: service_healthy`, because Compose otherwise waits only for a container to run, not for PostgreSQL to become ready ([Docker Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/)).
Run `alembic upgrade head` as an explicit one-shot migration service or documented setup command before starting the API.
Do not run competing migration processes in every API replica.

Use development Dockerfiles for the reviewer workflow and multi-stage production builds if time permits.
Keep the frontend and backend independently buildable outside Docker as well.
Use a checked-in `.env.example`, never commit real credentials, and avoid baking secrets into images.
Docker explicitly advises using secrets rather than environment variables for sensitive production information ([Docker Compose environment guidance](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/)).

## Scope control for the weekend

Build this in descending value order:

1. Pure financial-health domain and exhaustive unit tests.
2. PostgreSQL schema, Alembic migration, repositories, and transaction tests.
3. Thin FastAPI endpoints and generated TypeScript client.
4. Seeded React journey with a polished explanation and history.
5. Deterministic-first classification and customer preference correction.
6. Structured OpenAI classification and explanation with timeout and fallback.
7. Playwright E2E coverage and Docker Compose one-command startup.
8. Authentication, deployment, and live AI contract tests only after the core is complete.

Do not add Celery, Redis, Kafka, microservices, GraphQL, Kubernetes, or a generic agent framework.
The AI behavior requires two narrow structured-generation adapters, not an autonomous agent runtime.

## Bottom line

The strongest revised architecture is a Vite React frontend and a FastAPI modular monolith backed by PostgreSQL, with the complete system run by Docker Compose.
SQLAlchemy and Alembic make persistence and transaction design inspectable, generated OpenAPI types protect the frontend-backend seam, and strict OpenAI structured outputs keep AI outside the deterministic financial decision.
The design demonstrates backend engineering through deep domain modules, real database tests, explicit transactions, immutable snapshots, and graceful AI failure rather than through infrastructure volume.
