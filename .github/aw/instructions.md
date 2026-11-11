# Repository overlay for the agentic-workflows agent (FIS)

The `agentic-workflows` Copilot agent (`.github/agents/agentic-workflows.md`) loads this file
after its own guidance. Rules here win when they conflict with upstream defaults.

This repository is the **Financial Intelligence System (FIS)** course monorepo. Its agentic
workflows are teaching material for Lab 7 (`docs/labs/lab07_github_agentic_workflows.md`).
Follow these conventions in every workflow you create or change:

1. **Name:** `fis-<purpose>.md`, or the student's own name for exercise workflows.
2. **Read-only agent:** never give the agent job a `write` permission. Every write goes through `safe-outputs:` with an explicit `max`.
3. **No internet by default:** use `network.allowed: []` unless the workflow truly needs a domain. If it does, list exact domains, never `defaults` alone.
4. **Narrow shell for untrusted input:** any workflow that reads issue, PR or comment text gets a `bash:` allowlist of read-only commands (`cat`, `grep`, `find`, `head`, `ls`, `wc`), never `["*"]`.
5. **Cost cap:** always set `timeout-minutes` and `max-ai-credits`. 100–200 is plenty for these workflows.
6. **Deterministic first:** fetch or compute data in `steps:` and save it under `/tmp/gh-aw/`. Let the agent do only the judgment.
7. **Always `noop`:** every prompt must say when to call `noop` instead of writing.
8. **Compile pinned:** `gh aw compile` must finish with 0 errors and 0 warnings. Commit both the `.md` and the `.lock.yml`.

Repository facts the agent can rely on:

- The CI workflow is named `CI`, with jobs `lint-and-test` (ruff, pytest) and `eval-gate`.
- Code-review rules live in `.github/review-rules.md` (IDs B*, F*, G*). Workflows that review code read
  that file instead of hard-coding rules in their prompt. Never edit the rulebook from a workflow.
- A task is an issue labelled `task`. A PR links to it with `Task: #N` (not `Closes #N`). Only
  `fis-code-review` closes tasks, and only through `close-issue` with `required-labels: [task]`.
