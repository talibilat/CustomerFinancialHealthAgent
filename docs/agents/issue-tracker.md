# Issue tracker: GitHub

Issues and specifications for this repository live in GitHub Issues.
Use the `gh` CLI for issue operations and infer the repository from the configured Git remote.

## Repository

`talibilat/CustomerFinancialHealthAgent`

## Conventions

- Create issues with `gh issue create`.
- Read issues and their comments with `gh issue view <number> --comments`.
- List issues with `gh issue list`, requesting structured JSON when filtering is required.
- Comment with `gh issue comment <number>`.
- Apply or remove labels with `gh issue edit <number>`.
- Close issues with `gh issue close <number>`.
- Use a temporary Markdown file when passing a long issue body to the CLI.
- Do not place credentials, customer financial information, or other sensitive data in issue bodies.

## Pull requests as a triage surface

Pull requests are not a request or triage surface for this repository.

## Publishing

When a skill says to publish a specification or ticket to the issue tracker, create a GitHub issue in this repository.

When a skill says to fetch a ticket, read the GitHub issue and its comments.
