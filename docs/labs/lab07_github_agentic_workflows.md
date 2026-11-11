# Lab 7 — GitHub Agentic Workflows: AI helpers that review your code

> **Goal:** put AI agents to work on this repository, *safely*. You will run two of them. The
> first checks that every pull request follows `CONTRIBUTING.md`. The second reviews frontend and backend
> pull requests against a written rulebook, and closes the linked task only when the merged code
> follows the rules. Then you will try to trick the reviewer, and explain why the trick failed.
> **Time:** ~120 min · **Prereqs:** [Lab 0](lab00_git_workflow.md), [Lab 1](lab01_fastapi_yfinance.md), your own fork of this repo,
> and an [Anthropic API](https://console.anthropic.com) account with a few dollars of credit (each run costs about $0.01)
> **You produce:** one merged PR that adds a rule to the rulebook, a task issue closed by the reviewer, and your red-team findings.

By the end you can: explain how an agentic workflow differs from a normal Action; read and
compile one; choose its trigger, tools and network policy; limit what it can write with **safe
outputs**; preview with **staged mode**; read a run's logs and cost; and name the structural
control that stops a given prompt-injection attack.

The concepts page with the architecture diagram is [`gh-aw-lab/README.md`](../../gh-aw-lab/README.md). Keep it open.

---

## 0. Why agentic workflows (and when not to use them)

Our CI already runs `ruff`, `pytest` and the eval gate. Those are **deterministic**: same input,
same answer, and a script decides pass or fail. Some questions a script cannot answer:

- *"Does this pull request follow our contribution process: branch name, title, filled-in template?"*
- *"Does this new endpoint follow the conventions from Lab 1: a typed response model, `TickerParam`, `latency_ms`, a test?"*
- *"Task #12 says 'add a dividends endpoint'. Is it really done, or just merged?"*

Each one needs **judgment** plus **context from the repository**, which is exactly what a coding
agent is good at. [GitHub Agentic Workflows](https://github.github.com/gh-aw/) (gh-aw) run one on
GitHub Actions, triggered by the same events as normal CI.

The catch: an agent that reads text written by other people, and can act on your repository, is
an obvious attack surface. Most of gh-aw is about **containing** the agent, and so is most of this lab.

**Use plain Actions** when a script can decide. **Use an agentic workflow** when a human would
otherwise have to read something and decide.

---

## 1. How a run works

Read the diagram in [`gh-aw-lab/README.md`](../../gh-aw-lab/README.md#how-a-run-works). It boils down to five ideas:

1. You write `.github/workflows/<name>.md`. `gh aw compile` generates `<name>.lock.yml`. **GitHub
   runs the lock file**, so you always commit both files.
2. The **agent job has a read-only token**. It cannot push, label, comment, approve or close anything.
3. When the agent wants to write, it calls a **safe output** tool (`add_comment`, `close_issue`, …).
   That only *records* the request.
4. A separate **`safe_outputs` job**, which holds the write token, carries out the requests, but only
   the kinds you declared, up to the `max` you set, within the limits you wrote (allowed labels,
   required labels, allowed review types).
5. The agent runs inside the **Agent Workflow Firewall**: a container whose network goes through an
   allowlisting proxy. `network: { allowed: [] }` means no internet at all.

You can see points 2 and 4 in any lock file:

```bash
grep -n "pull-requests: write\|pull-requests: read" .github/workflows/fis-code-review.lock.yml
```

`pull-requests: read` appears under `agent:`. `pull-requests: write` appears only under
`safe_outputs:` and `conclusion:` (the job that posts the final status).

---

## 2. Setup

Work in **your fork**. Forks start with Actions and Issues switched off:

1. On GitHub, open your fork. On the **Actions** tab, click *I understand my workflows, go ahead and enable them*.
2. Under **Settings → General → Features**, tick **Issues**.

Install the CLI and the extension:

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File gh-aw-lab\scripts\setup-windows.ps1
```

```bash
# macOS / Linux / WSL
bash gh-aw-lab/scripts/setup.sh
```

Both scripts check for `gh` (the Windows one installs it with winget), then make sure you are
signed in. The first time, they stop and ask you to run this yourself:

```bash
gh auth login --scopes repo,workflow
```

Run the script again. It installs the `gh aw` extension (pinned to v1.2.2) and checks the repository.

**Give the agent a model.** This lab's helpers run on **Claude Code** with **Claude Haiku 5.5**
(`claude-haiku-5-5`), Anthropic's cheapest current model: $0.10 per million input tokens and $0.50
per million output tokens. A run of either helper costs about **1 AI credit ≈ $0.01**. It
authenticates with an Anthropic API key:

1. Go to **console.anthropic.com** and sign in. Under **Billing**, add a few dollars of credit. API
   usage is pay-as-you-go and separate from any Claude.ai subscription.
2. Under **API Keys → Create Key**, copy the key (it starts with `sk-ant-`).
3. Store it as a secret in your fork, pasting it when prompted:

```bash
gh aw secrets set ANTHROPIC_API_KEY
```

```bash
gh aw secrets bootstrap --non-interactive
```

The second command should show `✓ ANTHROPIC_API_KEY`. **Never** paste the key into a file, an issue,
or a chat. If you leak it, delete it in the Console. A Claude.ai Pro/Max login token
(`CLAUDE_CODE_OAUTH_TOKEN`) does not work here; it must be an API key.

> Claude is not the only engine. `engine: copilot` (with a `COPILOT_GITHUB_TOKEN` fine-grained token,
> on an account whose Copilot plan allows automation; Copilot Free gets a 401) or `engine: codex`
> (with `OPENAI_API_KEY`) work the same way. Change the `engine:` block and recompile.

---

## 3. Example 1: the contribution checker

Open [`.github/workflows/fis-contribution-check.md`](../../.github/workflows/fis-contribution-check.md).
On every pull request (opened, edited, pushed to, reopened) it checks the **process**: was this
change submitted the way [`CONTRIBUTING.md`](../../CONTRIBUTING.md) asks? It never judges the code.
The code reviewer in Example 2 does that.

| ID | Check | Severity |
|---|---|---|
| C1 | Branch name is `<type>/<topic>` or `<type>/<release>-<topic>`, e.g. `feat/r1-credit-model` | fail |
| C2 | PR title is a Conventional Commit, e.g. `feat(rag): add hybrid retrieval toggle` (squash-merge makes it the commit on `main`) | fail |
| C3 | Commit messages are Conventional Commits, summary of about 50 characters or less | warn |
| C4 | The PR template is filled in: What & why, How I verified, and the AI Engineering Log | fail |
| C5 | Small PR: 500 changed lines or fewer (generated `.lock.yml` files don't count) | warn |
| C6 | Nothing that must never be committed: `.env`, keys, data files | fail |

It answers with **one label**, `contribution-ready` or `needs-contribution-fixes` (a fixed PR swaps
one for the other), and **one checklist comment** saying exactly what to fix. Each new run collapses
the previous comment.

### Where it came from: reuse, then harden

You don't have to write every helper yourself. GitHub's sample library
[githubnext/agentics](https://github.com/githubnext/agentics) has a *Contribution Guidelines Checker*,
and ours started as that file. You can install the original on a scratch branch to compare (don't merge it):

```bash
gh aw add-wizard githubnext/agentics/contribution-guidelines-checker
```

Read its frontmatter the way a security reviewer would. Here is what we changed and why:

| Original | Ours | Why |
|---|---|---|
| Reads the PR with GitHub tools inside the sandbox | A `steps:` script saves `pr.json` first | In the sandbox, the `gh` proxy returns `null` for a PR's files and commits |
| Reads `CONTRIBUTING.md` from the checkout | The step fetches it **from `main`** | A PR could otherwise edit `CONTRIBUTING.md` to loosen its own checks |
| Only adds `contribution-ready`, never removes it | Two labels that replace each other | Otherwise a PR that later breaks a rule keeps a stale "ready" label |
| A new comment on every push | `hide-older-comments: true` | One current checklist, not a pile of comments |
| `network: defaults` | `network: { allowed: [] }` | Checking process needs no internet |
| Default engine | `claude-haiku-5-5` | It runs on every PR event, and its own comment suggests a small model |
| Generic checks for any repo | C1–C6, pinned to this repo's rules | Consistent, checkable verdicts |

A library workflow is a starting point, not a finished product. Never run one you haven't read.

### 3.1 Anatomy

The file has two parts. **The frontmatter** (between the `---` lines) is the *contract*. The
compiler and GitHub enforce it, not the model:

```yaml
engine:                   # WHICH AI does the work
  id: claude              #   Claude Code
  model: claude-haiku-5-5 #   the cheapest current Claude model
on:                       # WHEN it runs
  pull_request:
    types: [opened, edited, synchronize, reopened]   # "edited" = title or description changed
permissions:              # what the AGENT's token can READ (write is rejected at compile time)
  contents: read
  pull-requests: read
tools:
  github:
    mode: gh-proxy        # the agent's `gh` goes through a read-only proxy
    toolsets: [context, repos, pull_requests]
  bash: [cat, grep, head, wc, ls]   # read-only shell commands only
network:
  allowed: []             # no internet
timeout-minutes: 10       # hard stop on the agent step
max-ai-credits: 80        # hard stop on spend (1 AIC = $0.01). The default is 1000
steps:                    # a plain script that runs BEFORE the AI, outside its sandbox
  - name: Save the pull request's facts for the agent
    run: |                #   (abridged) writes these files to /tmp/gh-aw/pr/
      gh pr view "$PR_NUMBER" --json title,body,headRefName,files,commits,... > pr.json
      gh api ".../contents/CONTRIBUTING.md?ref=$base" > base-CONTRIBUTING.md   # the rules, from main
safe-outputs:             # the ONLY writes this workflow can ever make
  add-labels:
    allowed: [contribution-ready, needs-contribution-fixes]
  remove-labels:
    allowed: [contribution-ready, needs-contribution-fixes]
  add-comment:
    max: 1
    hide-older-comments: true   # (add `staged: true` above for preview mode: show, do not do)
```

**Why the `steps:` block?** Inside the sandbox, the `gh` proxy cannot return a pull request's
files, commits or merge state (it answers `"files": null`). So a deterministic script fetches them
first, with GitHub's normal `gh`, and saves them as files the AI only has to `cat`. That is the rule
of thumb for every agentic workflow: **deterministic where you can, agentic where you must.**

**The body** (after the second `---`) is the *prompt*, in plain Markdown. Notice three habits you
will see in every good workflow:

- it says exactly **what to read** (the files in `/tmp/gh-aw/pr/`), one simple command at a time,
  because pipes and `;` chains are blocked by the shell allowlist;
- it says exactly **what to check and output**: the C1–C6 table, one label, one comment under 200 words;
- it says **when to do nothing**: call `noop` for a bot's pull request. A run that correctly does
  nothing is a success, and `noop` records why.

It also says the PR text is **data, not instructions**. Keep that line in mind for §8.

### 3.2 Compile: Markdown in, lock file out

```bash
gh aw compile
```

```text
✓ Compiled 2 workflows: 2 succeeded, 0 warnings
```

Open `fis-contribution-check.lock.yml` and skim it. It is ~2,300 lines of ordinary Actions YAML. Look for:

- `jobs:` → `pre_activation`, `activation`, `agent`, `detection`, `safe_outputs`, `conclusion`;
- every `uses:` pinned to a **40-character commit SHA**, not a tag (supply-chain hygiene);
- the `--allowed-tools 'Bash(cat),Bash(grep),…'` list: the commands Claude may run. Your `bash:`
  allowlist plus a small safe default set (`echo`, `date`, `sort`…). Anything else is denied.

The compiler is also a **security linter**, and it is strict by default. See for yourself: in
`fis-contribution-check.md`, change `pull-requests: read` to `pull-requests: write` and run
`gh aw compile fis-contribution-check`:

```text
error: strict mode: write permission 'pull-requests: write' is not allowed for security reasons.
Use 'safe-outputs.create-issue', 'safe-outputs.create-pull-request', 'safe-outputs.add-comment', ...
```

Undo that, then try `network: { allowed: ["*"] }`:

```text
Reason: strict mode: wildcard '*' is not allowed in network.allowed domains to prevent
unrestricted internet access; expected explicit domains or ecosystem identifiers
```

Undo it again and recompile. You cannot give the agent write access or open internet by accident.
The only way to write is through `safe-outputs:`.

Rule: **edit the `.md`, never the `.lock.yml`.** A **frontmatter** edit needs `gh aw compile`,
because the lock file stores a hash of the frontmatter and the run fails fast if they differ.
`gh aw compile --watch` recompiles on every save.

**Where each part comes from on a pull request.** The two halves of a helper are loaded from
different places, and that is a deliberate safety feature:

| Part | Loaded from | So an edit takes effect… |
|---|---|---|
| Frontmatter (trigger, permissions, `steps:`, `safe-outputs`, `staged`) | the compiled `.lock.yml` **on the PR's branch** | in that same PR, after you recompile and push |
| Prompt body, and everything else under `.github/` (including the rulebook) | **`main`**: the run restores `.github/` from the base branch before the AI starts | only after it is merged into `main` |

So a pull request **cannot rewrite the instructions or the rules of its own review**. Look for the
step "Restore agent config folders from base branch" in any lock file. To change what a helper
*says* or *checks*, merge that change first, then test it on a new PR. (That is also why the checker
fetches `CONTRIBUTING.md` from `main`: it lives outside `.github/`, so nothing else would protect it.)

### 3.3 Run it: break the rules, fix them, then try preview mode

**Round 1: a mistake you cannot fix in place.** Open a pull request that breaks three rules on
purpose. `lab7` is not an allowed branch type (C1):

```bash
git switch main
git pull
git switch -c lab7/checker-test
```

Fix any small typo in `README.md`, then commit with a vague message (C3) and open the PR with a
vague title (C2) and no template (C4):

```bash
git commit -am "update readme"
git push -u origin lab7/checker-test
gh pr create --title "update readme" --body "quick fix"
```

Within 3–5 minutes the PR gets `needs-contribution-fixes` and one comment, `⚠️ 3 contribution
check(s) failing` (C1, C2, C4; C3 is only a warning), with a table saying how to fix each one. (The
code reviewer does not run: this PR touches nothing under `services/`.)

A **branch name cannot be fixed on an open PR**. Renaming the head branch on GitHub does not move the
PR to the new name: it **closes** it. So the fix for C1 is a correctly named branch and a new PR.
Note the old PR's number, then:

```bash
git switch -c docs/checker-test
git push -u origin docs/checker-test
gh pr close <old-number> --comment "Wrong branch name; continuing from docs/checker-test"
gh pr create --title "update readme" --body "quick fix"
```

The new PR passes C1 and still fails C2 and C4: `⚠️ 2 contribution check(s) failing`.

**Round 2: fix it in place.** Title and description *can* be fixed on the open PR. Each fix is an
`edited` event, so the checker runs again, and the previous comment is collapsed:

1. **Title (C2):** `gh pr edit --title "docs(readme): fix typo in quick start"`. The next comment says
   `⚠️ 1 contribution check(s) failing` (C4).
2. **Template (C4):** on GitHub, edit the PR description: paste [`.github/pull_request_template.md`](../../.github/pull_request_template.md)
   and fill in What & why, How I verified, and the AI Engineering Log.

The label **swaps** from `needs-contribution-fixes` to `contribution-ready` (the checker removes the
old one), and the last comment reads `✅ Follows CONTRIBUTING.md`, with the checks folded under
*Checks*. C3 still shows a warning for the commit `update readme`. Warnings don't block the label.

**Now try preview mode**, the safe way to test a change to a helper on a real repository without
spamming it. On the same branch, add one line to `fis-contribution-check.md`:

```yaml
safe-outputs:
  staged: true
  add-labels:
    ...
```

Run `gh aw compile fis-contribution-check`, commit both files, and push. `staged` lives in the lock
file, so it applies from your PR's own branch (§3.2). This time **nothing changes on the PR**: open
the run on the Actions tab and scroll to the **summary**, where the `safe_outputs` job *previewed* the
label and comment without applying them. Close the PR without merging when you are done, so `main`
stays live. Each run costs about 1 AI credit (≈ $0.01).

---

## 4. Example 2, part 1: the rulebook

Example 2 is [`fis-code-review.md`](../../.github/workflows/fis-code-review.md): a **code reviewer
and task tracker** for `services/frontend/` and `services/backend/`. Its rules do **not** live in
the prompt. They live in a rulebook that people write: [`.github/review-rules.md`](../../.github/review-rules.md).

Read it now. Every rule has an ID, is one checkable sentence, and points at code that already follows it:

| ID | In one line |
|---|---|
| B1–B5 | Backend endpoints: typed `response_model`, `TickerParam`, `latency_ms`, explicit 404/502/503, a test with a faked upstream |
| F1–F3 | Frontend: addresses from env vars, data loaded through `fetch()`, a `timeout=` on every request |
| G1–G2 | No secrets or data files; the PR names its task as `Task: #N` |

These are Lab 1's conventions, written down. Separating **rules** (data, edited by people) from
the **prompt** (fixed, edited rarely) means the team can tighten its standards without touching
the AI. You will add a rule yourself in §9.

**Tasks.** A task is an issue with the `task` label. **Issues → New issue → Task** applies it for
you. A pull request links to its task with a line in its description:

```text
Task: #12
```

Not `Closes #12`: GitHub closes the issue on merge **even if the rules fail**, and the whole point
is that the reviewer decides whether the task is done.

---

## 5. Example 2, part 2: a review on every push

Look at the reviewer's safe outputs. They are the most important lines in the file:

```yaml
safe-outputs:
  submit-pull-request-review:
    allowed-events: [COMMENT, REQUEST_CHANGES]   # never APPROVE: approving stays human
  create-pull-request-review-comment:
    max: 5                                       # comments pinned to the failing lines
  add-labels:
    allowed: ["review: passed", "review: changes-needed", "verified", "needs-follow-up"]
  close-issue:
    required-labels: [task]                      # it can only ever close a task
    state-reason: completed
```

Now watch it work. Create the task: **Issues → New issue → Task**, titled
`Add GET /market/dividends/{ticker}`. Note its number, below called `<T>`.

Make a branch and add a dividends endpoint the quick-and-dirty way. Append this to
`services/backend/app/market.py`:

```python
@router.get("/dividends/{ticker}")
def get_dividends(ticker: str):
    series = yf.Ticker(ticker).dividends
    return {"ticker": ticker, "dividends": {str(ts.date()): float(v) for ts, v in series.items()}}
```

```bash
git switch main
git switch -c feat/r3-dividends
git commit -am "feat(backend): add dividends endpoint"
git push -u origin feat/r3-dividends
gh pr create --title "feat(backend): add dividends endpoint" --body "Adds GET /market/dividends/{ticker}. Task: #<T>"
```

The branch name, title and commit follow `CONTRIBUTING.md`, so the contribution checker (§3) only
flags the missing PR template (C4). Fill it in on GitHub if you want that label green too; it does
not affect the reviewer.

This code **works**, and CI passes: ruff and pytest have nothing to object to. Within about five
minutes, the reviewer:

- submits a **Changes requested** review with a table of rules, and inline comments on the
  failing lines: **B1** (no `response_model`, returns a dict), **B2** (`str` instead of
  `TickerParam`), **B3** (no `latency_ms`), **B4** (no rate-limit or empty-result handling), **B5** (no test);
- labels the PR `review: changes-needed`;
- posts `🔄 PR #… under review: failing: B1, B2, B3, B4, B5` on task `<T>`.

That is the value: the reviewer catches what CI cannot, because it checks **your team's conventions**.

---

## 6. Example 2, part 3: merge → task completed

Fix the endpoint the Lab 1 way. Replace what you appended with:

```python
class Dividend(BaseModel):
    paid_on: datetime
    amount: float


class Dividends(BaseModel):
    ticker: str
    count: int
    dividends: list[Dividend]
    latency_ms: int


@router.get("/dividends/{ticker}", response_model=Dividends, summary="Dividend history")
def get_dividends(ticker: TickerParam) -> Dividends:
    started = time.perf_counter()
    symbol = ticker.upper()
    try:
        series = yf.Ticker(symbol).dividends
    except YFRateLimitError:
        raise _rate_limited() from None
    if series.empty:
        raise HTTPException(status_code=404, detail=f"No dividends for '{symbol}'.")
    return Dividends(
        ticker=symbol,
        count=len(series),
        dividends=[Dividend(paid_on=ts.to_pydatetime(), amount=float(v)) for ts, v in series.items()],
        latency_ms=_elapsed_ms(started),
    )
```

And add a test, `services/backend/tests/test_dividends.py`, that fakes Yahoo Finance so it never
touches the internet (rule B5):

```python
import pandas as pd
from app import market
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


class FakeTicker:
    def __init__(self, symbol):
        self.dividends = pd.Series(
            [0.24, 0.25], index=pd.to_datetime(["2025-02-10", "2025-05-12"])
        )


def test_dividends(monkeypatch):
    monkeypatch.setattr(market.yf, "Ticker", FakeTicker)
    r = client.get("/market/dividends/AAPL")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert "latency_ms" in body
```

```bash
cd services/backend && pytest -q && cd ../..
git add -A
git commit -m "fix: dividends endpoint follows review rules"
git push
```

The new run posts a **Comment** review, `✅ All review rules pass`, and swaps the label to
`review: passed`. Merge the PR (a human approval, not the bot's). The merge triggers one more
run, in **merge mode**: it re-checks the merged change, comments `✅ Completed in PR #…` on task
`<T>`, **closes the task as completed**, and labels it `verified`.

Had the merged code still broken a rule, the task would have stayed open with `needs-follow-up`
and a list of what to fix. "Merged" and "done" are no longer the same thing.

> **Order matters.** Merge mode reads `mergedAt` from `/tmp/gh-aw/pr/pr.json`, saved by the step
> before the AI runs. A PR closed without merging gets `noop` ("Closed without merge"), and the task
> is untouched. A merged PR with no `Task: #N` gets `noop` ("Merged, but no task linked").

---

## 7. Debug and measure: logs, audit, cost

Every run leaves evidence. These three commands are your observability:

```bash
gh aw logs -c 5
```

Shows the last 5 runs across workflows, with duration, tokens, AI credits and outcome.

```bash
gh aw audit <run-id>
```

Shows one run in depth: the prompt the agent actually received, its tool calls, the safe outputs
it requested and which were applied or **rejected**, and the firewall log of allowed and blocked domains.

```bash
gh aw forecast
```

Projects AI-credit spend per week from recent runs.

Record in your PR: the AI credits and duration of one contribution-checker run and one reviewer run. The
reviewer runs on **every push** to a frontend/backend PR. Estimate its monthly cost for a team that
pushes 40 times a week, and say whether the `max-ai-credits: 200` cap is ever close to binding.

---

## 8. Red-team the reviewer

Follow [`gh-aw-lab/redteam/README.md`](../../gh-aw-lab/redteam/README.md). You will open four
pull requests that try to get a task marked done dishonestly: a fake "pre-approved" note, a
request to close an unrelated issue, an instruction hidden in a code comment, and an attempt to
leak tokens. For each, use `gh aw audit` to find out:

1. Did the model **try** to comply? Quote the log.
2. What actually happened in the repository?
3. Which **structural** limit stopped it: the rulebook, `required-labels: [task]`,
   `allowed-events`, the read-only token, the firewall, or threat detection?

A model that refuses is nice, but **refusal is not the control**. The point of gh-aw is that the
attack fails even when the model complies.

---

## 9. Graded exercise (your deliverable)

Branch off `main` as `feat/lab7-<your-handle>`.

1. **Write a rule.** Add one rule to `.github/review-rules.md`, following
   [`gh-aw-lab/starter/rule-template.md`](../../gh-aw-lab/starter/rule-template.md): the next free ID,
   one checkable sentence, and a pointer to code that already follows it. Open a PR with only
   that change, get it reviewed by a teammate, and merge it.
2. **Create a task** (Issues → New issue → Task) for a small backend or frontend change that your
   rule applies to.
3. **Break your rule on purpose.** Open a PR with `Task: #<task>` whose change violates your new
   rule (and only that rule). The reviewer must flag **your rule ID**. If it does not, your rule is
   not checkable enough: rewrite it and try again.
4. **Fix it, then merge.** Push a fix, see `✅ All review rules pass`, merge, and see your task close itself as `verified`.

Open your final PR using the template, including the **AI Engineering Log**, and paste into the description:

- your rule (ID and sentence), and why it is worth enforcing;
- links to the failing review, the passing review, and the closed task;
- the AI-credit cost of each reviewer run (`gh aw logs`);
- your **red-team table** and your one-paragraph answer from §8.

**Bonus:** make the reviewer track tasks on a GitHub **Projects** board instead of closing issues.
Look at the `update-project` safe output in the gh-aw docs. It needs an extra token with Projects
access. Argue in your PR whether the extra credential is worth it.

---

## 10. Troubleshooting

- **`gh: command not found` right after installing** → open a new terminal (PATH is read at
  start-up). On Windows the binary is `C:\Program Files\GitHub CLI\gh.exe`.
- **The setup script says you are not signed in** → run `gh auth login --scopes repo,workflow`, then run the script again.
- **Every job fails within a few seconds with "account is locked due to a billing issue"** → a GitHub
  account problem, not the lab. Check github.com/settings/billing, your email, or contact GitHub Support.
- **Run fails at "Validate ANTHROPIC_API_KEY secret"** → the secret is missing or misnamed in *this*
  repository (forks do not inherit secrets). Run `gh aw secrets bootstrap`.
- **Agent step fails with an Anthropic `401 authentication_error`, or a credit/billing error** → the key is
  wrong or deleted, or the Anthropic account has no credit left. Check console.anthropic.com, then re-run
  `gh aw secrets set ANTHROPIC_API_KEY`. A Claude.ai login token (`CLAUDE_CODE_OAUTH_TOKEN`) is not supported.
- **The AI says it "could not complete the task" (`report_incomplete`)** → read its reason with
  `gh aw audit <run-id>`. If it could not see the change, check that the step "Save the pull request's
  facts for the agent" ran and printed a line count.
- **The reviewer did not run** → the PR touches nothing under `services/frontend/` or
  `services/backend/` (that is its `paths:` filter), the PR comes from someone else's fork (blocked by
  default), or the person who opened it lacks write access (see below).
- **It runs for you but not for a classmate's PR** → by default an agentic workflow only runs for people
  with **admin, maintain or write** access, and skips everyone else. `roles: all` under `on:` would open it
  to anyone, which, after §8, you should think hard about.
- **The task did not close after merging** → check the reviewer's merge-mode run: the PR description
  needs `Task: #N`, the issue needs the `task` label and must be open, and every rule must pass. The task
  comment says which rule failed.
- **The task closed the moment you merged, before the reviewer ran** → the PR said `Closes #N`, so GitHub
  closed it. Use `Task: #N`.
- **You renamed your PR's branch on GitHub and the PR closed** → that is GitHub's behaviour: renaming a
  PR's head branch closes the PR. Push a correctly named branch, open a new PR from it, and close the old one (§3.3).
- **The lock file is out of date** → you edited the frontmatter and did not recompile. Run `gh aw compile`, then commit both files.
- **You changed a helper's instructions or the rulebook in your PR, but the bot ignored it** → that is by
  design. On a pull request, everything under `.github/` is loaded from `main` (§3.2). Merge the change
  first, then open a new PR to test it.
- **The run succeeded but nothing happened** → look in the run summary for `noop` and its reason, or for
  `staged` mode. `gh aw audit <run-id>` shows rejected safe outputs.

---

## 11. Cheat sheet

```yaml
---
engine: { id: claude, model: claude-haiku-5-5 }   # needs the ANTHROPIC_API_KEY secret
on:
  pull_request:
    types: [opened, synchronize, reopened, closed]
    paths: ["services/backend/**"]      # other triggers: issues, schedule, workflow_dispatch
permissions: { contents: read, pull-requests: read, issues: read }   # read only
tools:
  github: { mode: gh-proxy, toolsets: [context, repos, pull_requests, issues] }
  bash: [cat, grep, find, head]         # narrow when the input is untrusted
network: { allowed: [] }                # or exact domains, never "*"
timeout-minutes: 10
max-ai-credits: 200
steps:                                  # deterministic prep, runs before the AI, outside the sandbox
  - run: gh pr diff "$PR_NUMBER" > /tmp/gh-aw/pr/pr.diff
    env: { GH_TOKEN: "${{ github.token }}", PR_NUMBER: "${{ github.event.pull_request.number }}" }
safe-outputs:                           # the only writes, and their limits
  staged: true                          # preview first
  add-comment: { max: 1, target: "*", hide-older-comments: true }
  submit-pull-request-review: { max: 1, allowed-events: [COMMENT, REQUEST_CHANGES] }
  create-pull-request-review-comment: { max: 5 }
  add-labels: { allowed: [a, b], max: 2 }
  close-issue: { target: "*", required-labels: [task], state-reason: completed }
---
Prompt in Markdown. Say what to read, what to output, and when to call `noop`.
```

```bash
gh aw compile [name] [--watch]          # .md -> .lock.yml (commit both)
gh aw logs -c 5                         # recent runs: tokens, AIC, outcome
gh aw audit <run-id>                    # one run: prompt, tool calls, outputs, firewall
gh aw forecast                          # projected AIC spend
gh aw add githubnext/agentics/<name>    # install a sample workflow
gh aw secrets set ANTHROPIC_API_KEY     # store the engine key
gh aw models                            # model IDs and their per-token prices
```

### Glossary

**agentic workflow** a Markdown-defined Action whose main step is an AI agent · **lock file** the
compiled `.lock.yml` that GitHub actually runs · **engine** the agent CLI that does the work (here Claude Code
running Claude Haiku 5.5; Copilot and Codex are alternatives) · **deterministic step** a plain `steps:` script
that runs before the AI, outside its sandbox ·
**safe output** a pre-declared, validated write (comment, review, label, close…) applied by a separate job ·
**staged** safe outputs previewed, not applied · **`noop`** an explicit "nothing to do" result ·
**rulebook** `.github/review-rules.md`, the human-written rules the reviewer applies ·
**task** an issue labelled `task`, linked from a PR by `Task: #N` · **AWF** Agent Workflow Firewall ·
**AIC** AI Credit, $0.01 of model usage · **prompt injection** instructions hidden in data the agent reads.
