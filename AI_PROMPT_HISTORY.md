# AI-Assisted Project History

This document is an edited summary of the three Codex chats used to plan, build, test, and review this take-home project.
It captures the substantive prompts, the approach I took, the main GPT responses, and the decisions that followed.
Repetitive approvals, raw command output, transient errors, timestamps, and unrelated operational messages have been removed.
Some wording has been lightly edited for clarity.

This is not a verbatim transcript.
The complete source chats remain available in Codex under the task IDs listed below and can be shared separately if a raw export is required.

## Source chats

1. `01a02675-e6fa-7e30-bf74-ac087cad6180` - initial review, research, product design, architecture, and documentation.
2. `01a0274c-07f0-7232-9697-7f875fc3d660` - domain-language and documentation consistency review.
3. `01a02759-71d9-7da3-a22d-f429704c13a4` - ticket creation, implementation, testing, integration, and final polish.

## How I approached the work

I used GPT as a design and implementation partner rather than asking it to make an open-ended product on my behalf.
I started by supplying the original take-home brief, my clarification questions, and Ophelos's answers.
I asked GPT to challenge the scope and assumptions before implementation began.
I then selected among concrete options, revised suggestions when they did not match my intent, and asked for additional research where the product or regulatory context was uncertain.

Once the design was stable, I asked GPT to turn it into canonical documentation and a ticketed implementation plan.
The build proceeded in bounded vertical slices with tests, pull requests, and explicit dependency ordering.
I reviewed progress, merged the pull requests, asked what should come next, and requested parallel work only where issues were independent.

The short prompts such as `B`, `yes`, `continue`, and `what is next?` were responses to detailed option sets or status reports in the preceding GPT message.
They represented decisions or permission to proceed, not the whole substance of the conversation.

## Chat 1: problem framing, research, and design

### Starting context and my direction

I supplied the take-home task and the written clarifications from Ophelos.
My questions to Ophelos had focused on whether AI was expected, how much frontend and backend depth was appropriate, whether I should devise the affordability method, whether sample history was acceptable, which engineering qualities would be assessed, and what level of testing and effort was expected.

I then asked GPT to grill the proposal rather than immediately generate code.
My aim was to make the product, system design, UX, and safety choices explicit before implementation.

### GPT response summary

GPT converted the open brief into a sequence of design decisions and presented alternatives with recommendations.
The discussion covered the customer journey, the meaning of affordability, financial resilience, repayment exploration, historical tracking, the role of AI, persistence, API design, testing, Docker, accessibility, security, stretch work, and submission evidence.

GPT also researched the areas where current external guidance mattered.
This included FCA and MoneyHelper context, Azure OpenAI integration, and a broad edge-case catalogue.
It proposed a reviewer-friendly submission rather than a minimal code-only repository.

### My decisions and adjustments

I selected a deterministic monthly headroom calculation instead of an invented financial-health score or universal affordability threshold.
I kept resilience separate so savings could not disguise a recurring monthly shortfall.
I chose to let customers explore repayment scenarios without recommending a payment amount.

I chose React and TypeScript for the frontend, FastAPI and Python for the backend, PostgreSQL for persistence, and Docker Compose for the reviewer workflow.
I chose exact decimal arithmetic and immutable, versioned statement snapshots for auditable financial history.

I wanted an AI component, but I changed the proposed provider to Azure OpenAI and said that deployment configuration would be supplied through environment variables.
I accepted a narrow AI boundary: AI could suggest an unknown outgoing classification or optionally personalize approved wording, but it could not calculate money, decide a result, select support, recommend a repayment, or alter history.
I also required the complete customer journey to work when Azure was unavailable.

When GPT presented an initial edge-case set, I explicitly asked it to find more cases.
The resulting catalogue included zero income, exact-zero headroom, penny boundaries, unusual frequencies, ambiguous descriptions, prompt injection, malformed provider output, Azure failure modes, duplicate submissions, stale drafts, concurrent corrections, transaction rollback, customer isolation, accessibility, mobile layouts, database readiness, migration failure, and time-zone and currency behavior.

For scope, I chose a reliable local Docker demonstration first and made public deployment optional.
I accepted a specific non-goal list rather than allowing the submission to imply production readiness.
I placed `currency` and `country_code`, time-limited sharing, and PDF export behind completion of the core product.

### Documentation outcome

After the design was confirmed, I asked GPT to consolidate the research into material that another coding agent could ingest consistently.
GPT created a canonical PRD and a consolidated research document, archived superseded source notes, corrected links, and checked that the consolidated material still represented the sources.

I later asked for a documentation audit and guidance on the next development method.
GPT created or aligned the glossary, testing strategy, architecture decisions, environment example, submission decisions, design notes, and README.
It recommended test-driven vertical slices rather than implementing isolated layers first.

I also asked GPT to configure the repository's issue-tracking conventions and agent context.
It added the issue tracker, triage labels, and domain-document routing so later work would use the same terminology and source of truth.

## Chat 2: domain-language review

### My direction

I asked GPT to apply the domain-modeling workflow to the existing repository and reconcile the canonical glossary, PRD, ingestion document, and an earlier review.
This was a focused consistency pass rather than a new feature request.

### GPT response summary

GPT found that the reviewer-facing README and `DECISIONS.md` still used some older terms such as `expense` and `assessment` where the canonical model used more precise language.
It updated those documents and checked them against the existing product model.

The resulting vocabulary distinguished editable financial statements from immutable confirmed snapshots, corrections from overwrites, statement periods from confirmation times, and known arrears or repayment commitments from hypothetical scenarios.
Archived research retained its original wording for provenance rather than being rewritten as though it had always used the final model.

GPT concluded that no new architecture decision record was needed because this was terminology alignment, not a change to system behavior.

### Outcome

This short chat made the product easier to explain in an interview and reduced the risk that documentation and code would appear to describe different concepts.

## Chat 3: tickets, implementation, and verification

### Starting direction

I asked GPT to turn the documentation into implementation tickets.
After the initial work, my recurring prompts were to continue, take the next unblocked issue, explain what came next, and use parallel agents where two issues were genuinely independent.

I merged the proposed pull requests myself and reported back so GPT could verify the actual state of `main` before beginning dependent work.

### GPT response summary

GPT translated the specification into a dependency-ordered issue plan and implemented the product through test-driven vertical slices.
Each slice crossed the relevant domain, persistence, API, generated client, frontend, and browser boundaries instead of leaving disconnected layers.

The implementation history covered these major areas:

- The application scaffold, database migrations, health checks, and a first end-to-end tracer journey.
- Deterministic monthly position and resilience calculations using exact decimal values.
- Editable statements, classification confirmation, preview, and immutable confirmation.
- Historical snapshots, corrections, change explanations, and concurrency protection.
- Repayment exploration and saved scenarios tied to their original statement basis.
- Difficult-financial-position states and fictional demonstration presets.
- Bounded Azure classification and optional personalized explanations with deterministic fallbacks.
- Customer ownership checks, safe error handling, transaction failure behavior, logging protection, and CORS controls.
- Responsive and accessible reviewer journeys, draft recovery, startup recovery, generated-client checks, Playwright coverage, and CI.

### My use of parallel work

I explicitly asked GPT to spin up two parallel agents for independent issues.
GPT isolated the work in separate branches and worktrees, ran shared Docker and browser tests sequentially to avoid port and database interference, and reported the required merge order.

For example, saved repayment scenarios and difficulty-state demonstration presets were built independently and then verified together.
Later, optional personalized explanations and the remaining Playwright and CI work were also developed in parallel after their public test seams were confirmed.

GPT declined to start a third issue when its dependencies were not yet on `main`.
That was useful because it avoided creating avoidable conflicts across migrations, generated API files, security work, and guidance behavior.

### Corrections found during implementation

The conversation was not a straight sequence of generated code being accepted without review.
Verification found and corrected several integration problems.

One pull request had been merged into another feature branch instead of `main`.
GPT checked the commit graph, created the missing integration path, and revised the merge order.

Two independently passing branches both introduced migrations and changed generated API artifacts.
GPT tested their combined state, chained the migrations, regenerated the client, and required a specific stacked merge sequence.

The browser suite exposed ambiguous accessibility locators and a readiness race between the frontend and backend.
GPT fixed the test seams and reran the journeys from a cold Docker start.

Linux CI found a three-pixel horizontal overflow at a 375-pixel viewport that had not appeared locally on macOS.
GPT measured the offending navigation element, allowed the navigation to wrap, kept the strict assertion, and reran the full suite.

Later hardening work moved provider calls outside database transactions, added safe handling for constraint and serialization failures, and protected against persisting optional wording when its source snapshot was no longer effective.

The final reviewer-journey pass also found and fixed a broken history-correction path while adding keyboard, zoom, contrast, reduced-motion, narrow-layout, retry, and session draft coverage.

### Final reported verification

At the end of the implementation and polish work, GPT reported:

- 476 backend tests passed, with one live provider test intentionally deselected.
- 80 frontend component tests passed.
- 17 Playwright journeys passed.
- Frontend lint and the production build passed.
- Generated OpenAPI and TypeScript client checks passed.
- The relevant GitHub Actions jobs were green.

These figures describe the final reported project state in the implementation chat.
They should still be rerun against the exact submission commit before the repository is sent.

## Representative prompt-to-outcome history

| My prompt or decision | GPT response in substance | Result |
| --- | --- | --- |
| Review the brief and grill the proposal. | Converted ambiguity into explicit product, safety, architecture, data, AI, UX, and testing decisions. | The design was settled before implementation. |
| Use Azure OpenAI and put deployment configuration in `.env.example`. | Researched the current Azure interface and proposed a bounded adapter with timeout, retry, structured output, minimized input, and deterministic fallback. | Azure became optional assistance rather than a decision maker or runtime dependency. |
| Find more edge cases. | Expanded the catalogue across financial boundaries, persistence, concurrency, provider failure, security, accessibility, Docker, and time handling. | The test and demo scope included unhappy paths that matter to customers. |
| Consolidate the documents and create a PRD. | Built canonical agent-ingestion and product documents and archived superseded notes. | Later implementation used a consistent source of truth. |
| Apply domain modeling. | Reconciled statement, snapshot, correction, period, arrears, commitment, and scenario terminology. | Reviewer-facing language matched the implemented domain. |
| Create tickets from the documentation. | Produced a dependency-ordered implementation plan based on vertical slices. | Work could be reviewed and merged incrementally. |
| Spin up two parallel agents. | Used isolated worktrees for independent issues and serialized shared browser infrastructure. | Parallel work reduced elapsed time without allowing branches to overwrite each other. |
| I merged both. What is next? | Verified GitHub and the commit graph instead of assuming the merge reached `main`. | A misplaced merge and two still-open issues were corrected. |
| Continue. | Took the next unblocked security, reviewer-journey, or submission task and reran the appropriate quality gates. | The project progressed through hardening rather than only adding visible features. |

## What was deliberately omitted from this edited history

- Exact timestamps and tool runtimes.
- Repeated acknowledgements such as `yes`, `B`, and `continue` when their meaning is already captured by the surrounding decision.
- Raw shell, test, Docker, browser, and GitHub output.
- Internal reasoning traces and agent orchestration details that do not explain a product or engineering decision.
- Ambient browser context automatically inserted by the application.
- Transient setup and sandbox messages unless they changed the implementation or verification result.
- A diagnostic message concerning a credential that was exposed in local tool output.

The omission of the diagnostic detail is intentional security editing.
The resulting response was to rotate the affected credential, and no credential value is included here.

## My assessment of the AI collaboration

The most valuable use of GPT was not code volume.
It was the repeated conversion of an open-ended brief into explicit choices, testable seams, safety boundaries, and reviewer evidence.

I retained responsibility for the scope and the key product choices.
I supplied the employer's clarifications, selected the options, redirected the provider choice, requested broader edge cases, approved the final design, initiated the documentation and ticketing stages, chose when parallel work was appropriate, merged pull requests, and asked GPT to verify the resulting state.

GPT contributed research, alternatives, implementation, tests, integration checks, and critical feedback.
Where automated work exposed a defect or inconsistency, the response was to reproduce it, fix it, and rerun the relevant verification rather than conceal it or weaken the test.
