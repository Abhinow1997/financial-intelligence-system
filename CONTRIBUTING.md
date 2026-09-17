# Contributing

We use **GitHub Flow**: `main` is always releasable, and every change lands through a
short-lived branch and a reviewed Pull Request. New to this? Do the lab first:
[`docs/labs/lab00_git_workflow.md`](docs/labs/lab00_git_workflow.md).

## The loop

```bash
git switch main && git pull            # start from latest main
git switch -c feat/r2-hybrid-retrieval # branch (see naming below)
# ...make a small, focused change...
git add -p                             # stage in reviewable chunks
git commit -m "feat(rag): add hybrid retrieval toggle"
git push -u origin feat/r2-hybrid-retrieval
# open a Pull Request, fill the template, get 1 review, squash-merge
```

## Branch naming

`<type>/<release>-<short-topic>` — e.g. `feat/r1-credit-model`, `fix/retriever-timeout`,
`docs/r4-eval-plan`, `chore/pin-deps`.

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `security`.

## Commit messages (Conventional Commits)

```
<type>(<scope>): <imperative summary>

<why + what, wrapped at ~72 cols>
```

- **scope** is usually the service/area: `rag`, `agents`, `model`, `gateway`, `evals`, `platform`.
- Keep the summary under ~50 chars, imperative ("add", not "added").
- One logical change per commit. If you say "and" a lot, split it.

Examples:
- `feat(agents): add per-run cost budget to agent_runtime`
- `fix(gateway): return 429 instead of 500 on rate limit`
- `test(model): add threshold-sweep regression case`

## Pull Requests

- Keep them small — easier to review, safer to revert.
- Fill the [PR template](.github/pull_request_template.md), including the **AI Engineering Log**.
- CI must be green: `ruff` (lint), `pytest` (tests), and the eval gate.
- At least one approving review before merge. Prefer **squash merge** to keep `main` linear.
- Delete the branch after merge.

## Releases

Tag on `main` when a release is accepted:

```bash
git tag -a v1.0-R1 -m "R1: Data + Predict"
git push origin v1.0-R1
```

Use the [release checklist issue template](.github/ISSUE_TEMPLATE/release_checklist.md).

## Local checks before you push

```bash
make format   # black + ruff --fix
make lint     # ruff check
make test     # pytest
```

(Optional but recommended: `pre-commit install` — see [`.pre-commit-config.yaml`](.pre-commit-config.yaml).)

## Never commit

Secrets, API keys, tokens, real financial data, or PII. If you think you committed a secret,
tell the team immediately — rotating the secret is required; deleting the file is not enough
(git keeps history). See [`SECURITY.md`](SECURITY.md).
