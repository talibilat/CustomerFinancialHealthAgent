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

Implementation time has not yet been recorded in the repository.
The candidate must add the actual design, research, implementation, testing, and documentation time before submission rather than estimate it after the fact.

## AI prompt history

This Codex task is the source prompt history for the design and implementation work.
The candidate must export or share the complete task before submission and must remove any credentials or unrelated sensitive information from the exported artifact.
