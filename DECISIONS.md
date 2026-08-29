# Decisions

## What we chose to build

We chose a responsive web application that turns existing income and outgoing records into an explainable monthly position, an optional resilience view, repayment scenarios, and immutable historical tracking.
The main customer journey is a complete vertical slice across React, FastAPI, PostgreSQL, deterministic domain logic, Azure OpenAI adapters, and Docker Compose.

## Why financial decisions are deterministic

Financial arithmetic, result states, warnings, support routes, and snapshot changes are deterministic and versioned.
The FCA does not provide a universal affordability percentage for this situation, so the product shows individualized cash flow, protects essential costs and customer-defined reserves, and qualifies every conclusion.
The product does not call a positive balance proof of long-term affordability.

## How AI is used

Azure OpenAI suggests classifications for unknown outgoings and optionally rewrites approved facts into customer-friendly language.
Known descriptions use deterministic rules, and every new model suggestion requires customer confirmation.
AI cannot calculate money, change a result, choose support, modify history, recommend a repayment, or operate autonomously.
The core journey works when Azure OpenAI is absent or unavailable.

## Why the architecture is split

The frontend uses React and TypeScript while the backend uses FastAPI and pure Python domain modules.
This makes backend workflow and persistence design visible without distributing the product into microservices.
PostgreSQL and immutable versioned snapshots make transaction, concurrency, audit, and history behavior testable.

## What we left out

We intentionally left out production authentication, real customer data, Open Banking, document verification, automatic agreement changes, repayment recommendations, personalized investment advice, a complete Standard Financial Statement, licensed SFS thresholds, a universal score, autonomous agents, and a conversational financial coach.
These omissions keep the submission focused on the problem in the brief and avoid implying capabilities the available data cannot support.

## What we would do next

After all Must and Should requirements are polished and tested, the first stretch item is a tested migration adding `currency` and `country_code`.
Secure time-limited statement sharing follows if time remains.
PDF export is last because it adds less evidence than customer safety, accessibility, domain correctness, and persistence.
Production work would also require authentication, authorization, retention, deletion, encryption, a privacy review, operational monitoring, and confirmation of the exact regulated role and applicable rules.

## Time spent

Time was not tracked contemporaneously during the AI-assisted build, so the project record uses a reconstructed range rather than false precision.
The range was reconstructed from the three Codex chats, commit clusters, pull-request sequencing, and the candidate's preparation record.

- Product research and design: approximately 4 to 5 hours.
- Implementation and AI orchestration: approximately 8 to 11 hours.
- Testing, debugging, review, and integration: approximately 4 to 5 hours.
- Documentation and submission preparation: approximately 2 to 3 hours.
- Interview preparation: approximately 3 to 4 hours.
- Total: approximately 21 to 28 hours.

The 3 to 4 hours of interview preparation are separate from the reconstructed project-build range and are not presented as the implementation total.

## AI prompt history

The project was developed across three Codex chats covering design, domain refinement, and implementation.
[AI_PROMPT_HISTORY.md](./AI_PROMPT_HISTORY.md) provides an edited summary of the substantive prompts, GPT responses, candidate decisions, corrections, and final outcomes.
It identifies all three source task IDs and explains what was removed for clarity or security.
The complete source chats remain available in Codex and can be shared separately if a raw export is required.
