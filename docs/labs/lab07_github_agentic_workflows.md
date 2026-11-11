# Lab 7 — GitHub Agentic Workflows: AI helpers that review your code

> **Goal:** put AI agents to work on this repository, *safely*. You will run two of them. The
> first explains every pull request in plain English. The second reviews frontend and backend
> pull requests against a written rulebook, and closes the linked task only when the merged code
> follows the rules. Then you will try to trick the reviewer, and explain why the trick failed.
> **Time:** ~120 min · **Prereqs:** [Lab 0](lab00_git_workflow.md), [Lab 1](lab01_fastapi_yfinance.md), a GitHub account with Copilot
> (free with the [Student Developer Pack](https://education.github.com/pack)), your own fork of this repo
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

- *"What does this pull request actually change, and how do I test it?"*
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

**Give the agent a model.** The default engine is GitHub Copilot, which authenticates with a
*fine-grained personal access token* that may only make Copilot requests:

1. Go to github.com → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
2. Set the expiry to the end of the semester. Under **Account permissions**, set **Copilot Requests** to *Read-only*. Grant nothing else.
3. Store it as a secret in your fork, pasting it when prompted:

```bash
gh aw secrets set COPILOT_GITHUB_TOKEN
```

```bash
gh aw secrets bootstrap --non-interactive
```

The second command should report no missing secrets. **Never** paste the token into a file, an
issue, or a chat. If you leak it, revoke it on the same settings page.

> Copilot is not the only engine. `engine: claude` (with an `ANTHROPIC_API_KEY` secret) or
> `engine: codex` (with `OPENAI_API_KEY`) work the same way. Change one line and recompile.

---

## 3. Example 1: the pull request explainer

Open [`.github/workflows/fis-pr-summary.md`](../../.github/workflows/fis-pr-summary.md). When a pull
request is opened, it posts **one** comment: what changed, why it matters, how to test it. It
judges nothing and changes nothing. That makes it the right first example.

### 3.1 Anatomy

The file has two parts. **The frontmatter** (between the `---` lines) is the *contract*. The
compiler and GitHub enforce it, not the model:

```yaml
on:                       # WHEN it runs
  pull_request:
    types: [opened, reopened]
permissions:              # what the AGENT's token can READ (write is rejected at compile time)
  contents: read
  pull-requests: read
tools:
  github:
    mode: gh-proxy        # the agent uses the `gh` CLI, proxied, with the read-only token
    toolsets: [context, repos, pull_requests]
  bash: [cat, grep, find, head, wc, ls, "git diff", "git log"]   # read-only shell commands only
network:
  allowed: []             # no internet
timeout-minutes: 10       # hard stop on the agent step
max-ai-credits: 80        # hard stop on spend (1 AIC = $0.01). The default is 1000
safe-outputs:             # the ONLY writes this workflow can ever make
  staged: true            #   preview mode: show, do not do
  add-comment:
    max: 1
```

**The body** (after the second `---`) is the *prompt*, in plain Markdown. Notice three habits you
will see in every good workflow:

- it says exactly **what to read** (`gh pr view`, `gh pr diff`);
- it says exactly **what to output** (three sections, under 150 words);
- it says **when to do nothing**: call `noop` for an empty PR. A run that correctly does nothing
  is a success, and `noop` records why.

It also says the PR text is **data, not instructions**. Keep that line in mind for §8.

### 3.2 Compile: Markdown in, lock file out

```bash
gh aw compile
```

```text
✓ Compiled 2 workflows: 2 succeeded, 0 warnings
```

Open `fis-pr-summary.lock.yml` and skim it. It is ~2,200 lines of ordinary Actions YAML. Look for:

- `jobs:` → `pre_activation`, `activation`, `agent`, `detection`, `safe_outputs`, `conclusion`;
- every `uses:` pinned to a **40-character commit SHA**, not a tag (supply-chain hygiene);
- the `--allow-tool shell(...)` list: the commands the agent may run.

The compiler is also a **security linter**, and it is strict by default. See for yourself: in
`fis-pr-summary.md`, change `pull-requests: read` to `pull-requests: write` and run
`gh aw compile fis-pr-summary`:

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

Rule: **edit the `.md`, never the `.lock.yml`.** The prompt body is read from the `.md` at run
time, so a body-only edit takes effect on the next run. A **frontmatter** edit needs `gh aw
compile`, because the lock file stores a hash of the frontmatter and the run fails fast if they
differ. `gh aw compile --watch` recompiles on every save.

### 3.3 Run it: preview first, then live

Pull-request workflows run from the **PR's own branch**, so you can try this one before merging anything:

```bash
git switch main
git switch -c lab7/explainer-test
```

Make any small change in `services/backend/app/market.py`, for example a clearer comment, then:

```bash
git commit -am "docs: clarify the quote endpoint comment"
git push -u origin lab7/explainer-test
gh pr create --fill
```

```bash
gh run watch
```

The run takes 3–5 minutes. (You will also see a `fis-code-review` run, because the PR touches
`services/backend/`. Ignore it until §5; it will complain that no task is linked.) Open the
`fis-pr-summary` run on the Actions tab and scroll to the **summary**. Because of
`staged: true`, the `safe_outputs` job *previewed* the comment **without posting it**. This is how
you test a new workflow on a real repository without spamming it.

Now go live: delete the `staged: true` line (and its comment) from `fis-pr-summary.md`, run
`gh aw compile fis-pr-summary`, commit both files on the same branch, push, then close and reopen
the PR (`gh pr close --comment "retry"` and `gh pr reopen`). This time the comment appears on the PR.
Close the PR without merging when you are done.

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
git switch -c lab7/dividends
git commit -am "feat: dividends endpoint"
git push -u origin lab7/dividends
gh pr create --title "Add dividends endpoint" --body "Adds GET /market/dividends/{ticker}.

Task: #<T>"
```

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

> **Order matters.** Merge mode reads `mergedAt` with `gh pr view`. A PR closed without merging
> gets `noop` ("Closed without merge"), and the task is untouched.

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

Record in your PR: the AI credits and duration of one explainer run and one reviewer run. The
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
- **Run fails at "Validate COPILOT_GITHUB_TOKEN secret"** → the secret is missing or misnamed
  in *this* repository (forks do not inherit secrets). Run `gh aw secrets bootstrap`.
- **Agent step fails with 401/403 from Copilot** → the token lacks *Copilot Requests* permission,
  has expired, or your Copilot plan is inactive. Regenerate it.
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
- **The lock file is out of date** → you edited the frontmatter and did not recompile. Run `gh aw compile`, then commit both files.
- **The run succeeded but nothing happened** → look in the run summary for `noop` and its reason, or for
  `staged` mode. `gh aw audit <run-id>` shows rejected safe outputs.

---

## 11. Cheat sheet

```yaml
---
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
gh aw secrets set COPILOT_GITHUB_TOKEN  # store the engine token
```

### Glossary

**agentic workflow** a Markdown-defined Action whose main step is an AI agent · **lock file** the
compiled `.lock.yml` that GitHub actually runs · **engine** the agent CLI (Copilot, Claude, Codex) ·
**safe output** a pre-declared, validated write (comment, review, label, close…) applied by a separate job ·
**staged** safe outputs previewed, not applied · **`noop`** an explicit "nothing to do" result ·
**rulebook** `.github/review-rules.md`, the human-written rules the reviewer applies ·
**task** an issue labelled `task`, linked from a PR by `Task: #N` · **AWF** Agent Workflow Firewall ·
**AIC** AI Credit, $0.01 of model usage · **prompt injection** instructions hidden in data the agent reads.
