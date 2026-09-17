# Lab 0 — Git Workflow on the Financial Intelligence System

> **Goal:** learn the exact git workflow you will use all semester — **GitHub Flow**
> (branch → commit → Pull Request → review → merge) — by making a real change to *this* repo.
> **Time:** ~60–75 min · **Prereqs:** git installed, a GitHub account · **You produce:** one merged PR + a tag.

By the end you can: clone, branch, stage, commit with good messages, push, open and merge a
Pull Request, resolve a merge conflict, tag a release, and undo mistakes safely.

---

## 0. Setup (once per machine)

```bash
git --version                      # 2.30+ recommended
git config --global user.name  "Your Name"
git config --global user.email "you@northeastern.edu"
git config --global init.defaultBranch main
git config --global pull.rebase false      # merge when pulling (simple default)
```

Verify:

```bash
git config --global --list | grep -E 'user\.|init\.|pull\.'
```

> Windows tip: run these in **Git Bash** (ships with Git for Windows). Line endings are handled
> by our [`.gitattributes`](../../.gitattributes), so you don't need `core.autocrlf`.

---

## 1. Get the repo

**On GitHub:** click **Fork** on the course repo (or use the team repo you were given), then:

```bash
git clone <your-fork-or-team-url> financial-intelligence-system
cd financial-intelligence-system
git remote -v                      # origin = your fork/team repo
```

If you forked, also track the upstream course repo so you can pull updates:

```bash
git remote add upstream <course-repo-url>
git remote -v
```

Sanity check that the skeleton is healthy:

```bash
make setup   # or: pip install -r requirements-dev.txt
make test    # the repo-structure + smoke tests should pass
```

---

## 2. The mental model (30 seconds)

Git has four places your work moves through:

```
 working tree  ──git add──►  staging area  ──git commit──►  local repo  ──git push──►  remote (origin)
   (your edits)               (next commit)                  (history)                 (GitHub)
```

- `git status` — what's changed and where it is.
- `git diff` — unstaged changes; `git diff --staged` — what's about to be committed.
- A **commit** is a snapshot + message. A **branch** is a movable pointer to a commit.

---

## 3. The core loop, once

Look around first:

```bash
git status
git log --oneline --graph --decorate -5
```

---

## 4. `.gitignore` — never commit secrets or data

This repo already ignores `.env`, keys, the `data/` lake, and model artifacts
(see [`.gitignore`](../../.gitignore)). Prove it:

```bash
cp .env.example .env               # your local config
echo "SECRET=do-not-commit" >> .env
git status                         # .env should NOT appear as untracked
```

If a secret ever *does* get committed: tell the team and **rotate the secret** — deleting the
file is not enough because git keeps history. See [`SECURITY.md`](../../SECURITY.md).

**Rule:** no secrets, API keys, real financial data, or PII — ever.

---

## 5. Branch (GitHub Flow)

`main` is always releasable, so we never commit to it directly. Start every task from fresh `main`:

```bash
git switch main
git pull                           # (or: git pull upstream main)
git switch -c docs/lab0-<your-handle>   # e.g. docs/lab0-agangurde
```

Branch naming: `<type>/<release>-<topic>` — `feat/r1-credit-model`, `fix/retriever-timeout`,
`docs/lab0-agangurde`. Types: `feat fix docs refactor test chore perf security`
(see [`CONTRIBUTING.md`](../../CONTRIBUTING.md)).

---

## 6. Make a real change, then stage + commit

Add yourself to the contributors list. Open
[`docs/labs/exercise/CONTRIBUTORS.md`](exercise/CONTRIBUTORS.md) and add **one line** just
above the `<!-- END:contributors -->` marker, e.g.:

```
- Aisha Gangurde (@agangurde) - team-alpha - joined 2026-09-15
```

Review exactly what you changed, then stage and commit:

```bash
git status
git diff                                   # read your own change before committing
git add docs/labs/exercise/CONTRIBUTORS.md
git diff --staged                          # what the commit will contain
git commit -m "docs(lab0): add <your name> to contributors"
```

Good commits are small and imperative. `git add -p` lets you stage change-by-change when a file
has more than one logical edit.

---

## 7. Push and open a Pull Request

```bash
git push -u origin docs/lab0-<your-handle>
```

On GitHub, click **Compare & pull request**. Then:

1. Base = `main`, compare = your branch.
2. Fill the [PR template](../../.github/pull_request_template.md) — including the **AI
   Engineering Log** section (required by the syllabus for every submission).
3. Request a reviewer (a teammate or the TA).
4. Watch **CI** run (`ruff` + `pytest` + eval gate). It must be green.

**Review etiquette:** respond to each comment; push follow-up commits to the *same* branch (the
PR updates automatically). When approved, **Squash and merge**, then delete the branch on GitHub.

---

## 8. Sync your local `main`

After the merge, bring your machine up to date and clean up:

```bash
git switch main
git pull
git branch -d docs/lab0-<your-handle>      # delete the merged local branch
git fetch --prune                          # drop stale remote-tracking branches
```

---

## 9. Resolve a merge conflict (the part everyone fears)

Conflicts happen when two branches change **the same lines**. Let's create one on purpose, safely.

```bash
# Branch A edits the marker line
git switch main && git pull
git switch -c lab0-conflict-a
# edit CONTRIBUTORS.md: add "- Alice (@alice) ..." above END marker
git commit -am "docs(lab0): add Alice"

# Branch B edits the SAME spot, from main
git switch main
git switch -c lab0-conflict-b
# edit CONTRIBUTORS.md: add "- Bob (@bob) ..." on the same line region
git commit -am "docs(lab0): add Bob"

# Merge A into B -> conflict
git merge lab0-conflict-a
```

Git marks the clash:

```
<<<<<<< HEAD
- Bob (@bob) - team-beta - joined 2026-09-15
=======
- Alice (@alice) - team-alpha - joined 2026-09-15
>>>>>>> lab0-conflict-a
```

Fix it by editing the file so **both** lines are kept and the `<<<<`, `====`, `>>>>` markers are
gone. Then:

```bash
git add docs/labs/exercise/CONTRIBUTORS.md
git commit                                 # completes the merge
git status                                 # clean
```

Bail out any time with `git merge --abort`. Tools: `git mergetool`, or resolve in VS Code.
Clean up the practice branches:

```bash
git switch main
git branch -D lab0-conflict-a lab0-conflict-b
```

---

## 10. Tag a release (R1 → R6)

We tag `main` when a release is accepted. Annotated tags carry a message and author:

```bash
git switch main && git pull
git tag -a v1.0-R1 -m "R1: Data + Predict"
git push origin v1.0-R1
git tag                                    # list tags
git show v1.0-R1                           # inspect
```

Map: `v1.0-R1 … v1.0-R6` track the six releases in [`docs/releases/`](../releases).

---

## 11. Undo & recover (safety net)

| You want to… | Command | Notes |
|---|---|---|
| Discard unstaged edits to a file | `git restore <file>` | irreversible for that edit |
| Unstage (keep the edit) | `git restore --staged <file>` | |
| Fix the **last** commit message | `git commit --amend` | only before pushing |
| Add a forgotten file to last commit | `git add <f> && git commit --amend --no-edit` | before pushing |
| Undo a pushed commit **safely** | `git revert <sha>` | makes a new inverse commit |
| Move branch back, keep edits | `git reset --soft <sha>` | history rewrite — local only |
| Stash work-in-progress | `git stash` / `git stash pop` | switch branches cleanly |
| "I lost a commit!" | `git reflog` | find the sha, then `git switch -c rescue <sha>` |

**Golden rule:** rewrite history (`amend`, `reset`, force-push) only on branches **nobody else
has pulled**. On shared branches, prefer `git revert`.

---

## 12. Team rules (branch protection)

On the team repo, protect `main` (Settings → Branches):

- Require a Pull Request + **1 approval** before merge.
- Require status checks (CI) to pass.
- Disallow direct pushes and force-pushes to `main`.

This is what makes "`main` is always releasable" true in practice, and it mirrors the R6 release
discipline (blocking eval gate before anything ships).

---

## 13. Graded exercise (your deliverable)

Produce, on the team repo:

1. A branch `docs/lab0-<handle>` that adds you to `CONTRIBUTORS.md`.
2. A Pull Request with the template filled, **including the AI Engineering Log**, CI green.
3. One teammate's review + your merge (squash).
4. Screenshot the merged PR and the `git log --oneline --graph -5` after syncing `main`.
5. **Bonus:** create and push a lightweight tag `lab0-done-<handle>`.

Submit the PR link + screenshot in your engineering log
([`docs/engineering-log/engineering_log_week01.md`](../engineering-log/engineering_log_week01.md)).

---

## 14. Troubleshooting

- **"Author identity unknown"** → set `user.name` / `user.email` (Step 0).
- **Push rejected (non-fast-forward)** → someone pushed first: `git pull` then push again.
- **Accidentally on `main`** → `git switch -c feat/whatever` *moves* your uncommitted edits to a new branch.
- **Committed to `main` locally** → `git switch -c feat/x` then `git switch main && git reset --hard origin/main`.
- **Wrong file staged** → `git restore --staged <file>`.
- **Huge/binary file blocked** → it belongs in the data lake or object store, not git.

---

## 15. Cheat sheet

```bash
# start work
git switch main && git pull
git switch -c feat/r2-hybrid-retrieval

# edit → review → commit
git status
git add -p
git commit -m "feat(rag): add hybrid retrieval toggle"

# share
git push -u origin feat/r2-hybrid-retrieval     # then open a PR

# sync & clean
git switch main && git pull
git branch -d feat/r2-hybrid-retrieval
git fetch --prune

# inspect
git log --oneline --graph --decorate --all
git diff  |  git diff --staged  |  git show <sha>

# undo
git restore <f>            # discard edit
git restore --staged <f>   # unstage
git revert <sha>           # undo a pushed commit
git reflog                 # find lost commits
```

### Conventional commit types
`feat` · `fix` · `docs` · `refactor` · `test` · `chore` · `perf` · `security`

### Glossary
**working tree** your files · **staging/index** the next commit · **HEAD** current commit ·
**origin** your remote · **upstream** the course remote · **fast-forward** a merge with no
divergence · **detached HEAD** you're on a commit, not a branch (make a branch to keep work).
