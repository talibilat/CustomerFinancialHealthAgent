# Superseded TypeScript-only stack research

> Status: Superseded by [FastAPI and TypeScript stack research](./fastapi-typescript-stack.md).
>
> This note records an earlier option considered during discovery.
> Do not use its Next.js architecture or public OpenAI integration as the implementation plan.

## Recommendation

Use a single Next.js application with the App Router, React, TypeScript, PostgreSQL, Prisma ORM, Zod, the official OpenAI JavaScript SDK, Vitest, Testcontainers, and Playwright.
Use semantic HTML and Tailwind CSS for the responsive UI, adding a chart library only for the historical trend.
Commit the package lockfile and use current stable dependency releases rather than copying version numbers from this note.

This is a modular monolith, not a framework-shaped monolith.
Next.js should own delivery concerns such as pages, Route Handlers, forms, and rendering, while ordinary TypeScript modules own affordability, classifications, snapshots, and application workflows.
Next.js supports server-rendered data access, interactive Client Components, and HTTP Route Handlers in one application, which removes the coordination cost of separate frontend and API deployments ([App Router](https://nextjs.org/docs/app), [Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components), [Route Handlers](https://nextjs.org/docs/app/getting-started/route-handlers)).

## Suggested boundaries

```text
src/
  app/                         Next.js pages, layouts, actions, route handlers
  modules/
    affordability/
      domain/                  pure entities, value objects, policies, calculation
      application/             use cases and repository/service ports
      infrastructure/          Prisma repositories
    expense-classification/
      domain/                  taxonomy, confidence, confirmation rules
      application/             deterministic-first classification workflow
      infrastructure/          OpenAI adapter and customer-preference repository
    guidance/
      application/             grounded explanation workflow and fallback
      infrastructure/          OpenAI adapter
  shared/
    db/                        Prisma client and transaction boundary
    validation/                boundary schemas
```

Route Handlers and Server Actions should validate input, establish the acting customer, invoke one application use case, and translate the result.
They should not contain financial rules or direct multi-step database workflows.
Server Components should call the application layer directly rather than fetching the application's own Route Handlers, because the Next.js guidance says that doing so adds an HTTP round trip and can fail at build time for prerendered components ([Backend for Frontend guide](https://nextjs.org/docs/app/guides/backend-for-frontend)).

The domain layer should have no imports from Next.js, Prisma, OpenAI, or React.
Its money calculations should use integer pennies or a dedicated decimal representation, never binary floating-point arithmetic.
The application layer should depend on small ports such as `AssessmentRepository`, `ExpenseClassifier`, `GuidanceGenerator`, and `Clock`.
This makes backend rules fast to unit test and makes the LLM and persistence replaceable without introducing a second service.

## Persistence and migrations

Use PostgreSQL in local development and tests so the demonstrated behavior matches the intended database.
Use Prisma Client behind repository adapters and use Prisma Migrate for checked-in SQL migration history.
Prisma provides generated type-safe database access, and Prisma Migrate generates customizable SQL files that can be committed and applied in development or deployment ([Prisma ORM overview](https://www.prisma.io/docs/orm), [Prisma Migrate overview](https://www.prisma.io/docs/orm/prisma-migrate)).
Prisma also supports interactive transactions, which fit saving an immutable assessment, its expense classifications, and calculation outputs atomically ([transactions](https://www.prisma.io/docs/orm/prisma-client/queries/transactions)).

The initial schema should include `customer_id` ownership on every customer-scoped aggregate even while authentication remains a gated enhancement.
Immutable snapshots should persist normalized inputs, confirmed classifications, deterministic outputs, calculation-policy version, and timestamps.
Drafts should be separate mutable records or ephemeral client state, not updates to historical snapshots.

Use Docker Compose for the developer PostgreSQL service.
Use Testcontainers for repository integration tests so each test run can start a real isolated PostgreSQL instance and connect through its generated URI ([Testcontainers PostgreSQL module](https://node.testcontainers.org/modules/postgresql/)).

## LLM integration

Use the official OpenAI JavaScript SDK through an infrastructure adapter.
Call the Responses API with `responses.parse`, a Zod schema, and Structured Outputs for both classification suggestions and optional plain-language guidance.
OpenAI documents that Structured Outputs adhere to the supplied schema, that the JavaScript SDK can derive the format from Zod, and that refusals are programmatically distinguishable ([Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs)).

The LLM must return a small closed object, for example a proposed display category, confidence, reason, and whether clarification is required.
Application code must still enforce allowed category identifiers, customer confirmation, timeouts, errors, refusals, and a deterministic fallback.
The model must never calculate affordability or write an immutable snapshot directly.
Persist confirmed customer-specific preferences separately from the global prompt.
Record prompt version, schema version, provider, and model identifier for auditability, but minimize financial data sent to the provider and do not store raw prompts merely for convenience.

An API key must be optional for reviewers.
Without one, known classifications, customer preferences, and deterministic explanation templates should keep the complete core journey working.

## Test strategy

Use Vitest for pure domain tests and application-service tests.
Vitest supports TypeScript, mocking, DOM environments, and coverage, but most backend tests should run in the Node environment and replace ports with explicit fakes rather than broad module mocks ([Vitest features](https://vitest.dev/guide/features), [mocking guidance](https://vitest.dev/guide/mocking)).

Use Vitest plus Testcontainers for integration tests that apply the real migrations and exercise Prisma repository behavior against PostgreSQL.
Prioritize snapshot immutability, transaction rollback, ownership filters, customer preference reuse, and persistence of calculation versions.

Use Playwright for a small number of end-to-end journeys through the actual browser and running application.
Its configuration can launch the local web server, and its isolated fixtures support repeatable test state ([web server configuration](https://playwright.dev/docs/test-webserver), [fixtures](https://playwright.dev/docs/test-fixtures)).
Cover the seeded dashboard, editing and classifying an expense, correcting an ambiguous suggestion, previewing a proposed repayment, saving a snapshot, and seeing history update.
Ordinary E2E tests should inject a deterministic classifier adapter rather than call a live paid model.
Keep one separately invoked AI contract smoke test if an API key is present.

## Realistic alternatives

| Choice | Strengths | Costs | Verdict |
| --- | --- | --- | --- |
| Next.js plus Prisma | One runtime and deployment, generated database client, mature migration workflow, clear transaction support, and enough delivery primitives for UI and API | Requires discipline to keep domain rules out of `app/` and Prisma types out of the domain | Recommended for the 20-plus-hour take-home |
| Next.js plus Drizzle | Database schema remains TypeScript, queries stay close to SQL, and migrations can be generated as SQL ([overview](https://orm.drizzle.team/docs/overview), [migrations](https://orm.drizzle.team/docs/migrations), [transactions](https://orm.drizzle.team/docs/transactions)) | More SQL and mapping work, and more migration-workflow choices to settle during a short build | Good runner-up if demonstrating explicit SQL matters more than delivery speed |
| React/Vite plus Fastify plus Prisma | Makes the HTTP API boundary highly visible, offers schema-driven route typing, and supports fast in-process HTTP tests through `inject` ([TypeScript support](https://fastify.dev/docs/latest/Reference/TypeScript/), [testing](https://fastify.dev/docs/latest/Guides/Testing/)) | Adds a second application process, cross-origin/API-client wiring, duplicated build configuration, and more deployment work | Strong for an API-first exercise, but unnecessary here |

NestJS, a monorepo, queues, event buses, and microservices should be left out.
They do not strengthen this vertical slice enough to justify the additional concepts and setup.

## Future authentication

Keep identity behind an `ActorContext` or `CurrentCustomer` application port and require a `customerId` in repository methods from the beginning.
That allows the seeded demo identity to be replaced later by a supported authentication library without changing the domain model.
Next.js recommends using an authentication library rather than hand-building secure session management, centralizing secure authorization near the data-access layer, and treating Server Actions and Route Handlers as public-facing endpoints ([authentication guide](https://nextjs.org/docs/app/guides/authentication)).

## Bottom line

The strongest submission is one deployable Next.js application whose visible framework layer is thin and whose backend rules are ordinary, independently tested TypeScript.
Prisma and PostgreSQL provide credible persistence and migrations, strict OpenAI structured outputs provide a bounded AI feature, and Vitest, Testcontainers, and Playwright prove the system at the domain, database, and customer-journey levels.
