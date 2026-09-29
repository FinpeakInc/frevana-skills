# Source material intake

Users can provide a document, URL, working command, repository path, or free-form explanation instead of filling out this form. Extract what is already known and ask only for essential gaps.

## Short request people can copy

```text
Create a reusable skill from the material below.

What it should do:
When I would ask an AI to use it:
Data provider (Frevana official or third-party service, if applicable):
Source material (paste text or give file/link paths):
Preferred output location (optional):
```

## Details that help with executable workflows

```text
Tool, CLI, API, or website to use:
Provider name and official documentation:
Required inputs and where they come from:
Optional inputs and defaults:
Known working request or command:
Example success response or output:
Authentication method and credential environment variable (names only; do not paste secrets):
Read-only or writes external state? Any cost per call?:
Retry and idempotency behavior, if known:
Failure examples or limits:
Target agent or skill format, if specific:
```

Do not ask for every field by default. A user may have only a goal and a source document. The authoring agent should research or inspect the available source and identify the few blocking unknowns.

For Frevana official data, default the credential name to `FREVANA_TOKEN`. For a direct third-party integration, derive authentication and the credential name from that provider's contract; never assume that `FREVANA_TOKEN` works there. If the source is ambiguous, ask which provider should supply the data before generating executable commands.

## Patterns distilled from this repository

| Pattern | Evidence to extract | Resulting skill behavior |
| --- | --- | --- |
| Single API lookup | Endpoint, required query, allowed options, raw response, auth | Validate inputs, call a concrete command, preserve raw API output when required. |
| Asynchronous paid task | Create/status/result endpoints, task states, billing state, idempotency key | Split or combine phases as needed; retain task ID; avoid a fresh paid trigger after an uncertain response. |
| File upload or publication | Local file rules, metadata, pre-signed upload, publish step | Keep the user's file intact, protect credentials, verify each step, return identifiers needed for updates. |
| External content management | Object identity, existing state, write method, verification read | Resolve the exact target, keep unrelated fields, preview or verify writes as the workflow requires. |
| Model or media generation | Model ID, accepted parameters, provider-specific defaults, job lifecycle | Use only supported parameters and report whether an output was actually produced. |

These are examples of decisions to make, not mandatory sections or universal API contracts. Derive exact values from the supplied source. In this repository, representative implementations include `amazon-search`, `tiktok-posts-discover-by-keyword`, `frevana-s3`, `wordpress-content`, and `gpt-6`.

## Completion check

A generated skill is ready for handoff when its trigger is distinct, required information is obtainable, commands are runnable where needed, outputs and failure states are explicit, and validation evidence matches the claim of usability. If live access was unavailable, say exactly which part remains unverified.
