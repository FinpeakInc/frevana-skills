---
name: skill-from-materials
description: Create a usable agent skill from user-provided notes, API documentation, examples, or an existing workflow. Use when someone wants to turn source material into a reusable SKILL.md and any necessary scripts or references.
---

# Skill from Materials

Turn source material into a skill that another agent can discover and execute. Work in the output location the user chooses; if none is specified, use the current project's skill directory when it has one, otherwise use the agent's default skills directory.

## Start with the material

Accept rough notes, files, links, API schemas, existing commands, or a working example. Read the supplied material before designing the skill. [references/intake.md](references/intake.md) has a short form the user can fill in, but never require them to complete it when their material already answers the questions.

Identify:

- the user request that should trigger this skill, and nearby requests that should use something else;
- whether data comes from a Frevana official endpoint or a directly integrated third-party service;
- the required inputs, optional inputs, defaults, and values that must never be guessed;
- the actual tool, API, command, or manual workflow that performs the work;
- authentication, permissions, cost, external writes, and retry behavior;
- the output the agent should return, including any raw-data preservation requirement.

Separate verified facts from assumptions. If an API contract, permission, or other critical input is missing, inspect an authoritative source when available. Ask only for information that cannot be inferred or verified. Do not invent endpoints, parameters, response fields, credentials, or success claims. Keep secrets out of generated files and examples.

## Route by data provider

For a data skill, establish the provider before writing commands or authentication instructions:

| Provider | Credential contract | Contract source |
| --- | --- | --- |
| Frevana official | Read `FREVANA_TOKEN` from the environment. Do not embed, print, or persist its value. | The relevant Frevana API or existing repository script and its current request/response contract. |
| Direct third-party integration | Use that service's documented authentication method and a service-specific credential name. Do not silently substitute `FREVANA_TOKEN`. | The third party's authoritative API or CLI documentation and any supplied working example. |

For either provider, document the actual base URL or CLI, required permissions, rate limits, pricing, and response format when they affect execution. If the material does not identify the provider or its authentication contract, resolve that gap before claiming the generated skill is executable. Keep provider-specific setup and error handling inside the resulting skill; do not mix credentials or imply that Frevana credentials authorize a third-party API.

## Choose the smallest useful shape

Create a directory named with lowercase letters, digits, and hyphens. The only required file is `SKILL.md` with YAML frontmatter containing `name` and a concise English `description` that explains when to use it. The body should tell a future agent how to complete the task, not merely describe the subject.

Add resources only when they improve execution:

| Resource | Add when |
| --- | --- |
| `agents/openai.yaml` | The target agent uses this interface metadata, or the user requests a display name or default prompt. |
| `scripts/` | A deterministic command, validation, API call, or repeated transformation should be executable rather than re-created by the agent. |
| `references/` | Detailed schemas, mode-specific steps, or lengthy source facts would obscure the main workflow. Link each reference from `SKILL.md` at the point of use. |
| `assets/` | The workflow needs files copied or adapted into its output. |
| `tests/` | There is meaningful behavior or a fragile contract to verify, especially in a new script. |

Do not add placeholder files or copy a whole source manual. A prompt-only or judgment-based skill can be a single file. An API skill is usable only when its invocation path and required contract are concrete; if you add a script, make the documented commands match its real flags and behavior.

## Write the execution contract

Put these in `SKILL.md` when they apply:

1. Purpose and trigger boundary. Keep the frontmatter description specific enough to avoid unrelated activation.
2. Required inputs, optional inputs, defaults, validation rules, and how missing inputs are handled.
3. Prerequisites and provider-specific secret handling. Frevana official data skills use `FREVANA_TOKEN`; direct third-party skills follow that provider's documented authentication contract. Name environment variables or credential setup without embedding values.
4. A runnable workflow and commands using paths relative to the skill directory. Prefer a bundled script over an ad hoc API call when one exists.
5. Output and failure behavior: where results go, what is returned unchanged, how errors are surfaced, and what confirms success.
6. Real constraints for writes, billing, and retries. For a billable or non-idempotent trigger, define how an uncertain result is reconciled before any retry.

Write rules only when the material supports them or they prevent a concrete failure. Preserve the user's specified scope and authorization. Avoid making a broad safety policy or a fixed process out of one example. Keep the entrypoint short; move detailed contracts to linked references.

## Verify before calling it usable

1. Check frontmatter, folder name, relative links, and that no scaffold placeholders remain. If a local skill validator is available, run it.
2. Run each new script's help or offline path. Test meaningful input validation and output behavior with fixtures or mocks where appropriate.
3. Compare documented commands, defaults, fields, and output against the implemented files and source material.
4. Run a live acceptance check only when the required credentials, authorization, and cost tolerance are present. Keep an untested external integration labeled as unverified.
5. Try one realistic request against the skill instructions: can another agent select it, gather inputs, execute it, and recognize success or failure without guessing?

Return the generated skill's path, what material it used, what was verified, and any specific missing evidence that prevents live use. Do not claim a skill works end to end from frontmatter validation alone.
