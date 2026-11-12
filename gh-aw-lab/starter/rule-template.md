# Writing a review rule (Lab 7 graded exercise)

You will add **one** rule to [`.github/review-rules.md`](../../.github/review-rules.md). The code
reviewer reads that file on every run. You never touch the reviewer's prompt; the rulebook is the
only thing you change.

## The shape of a good rule

Copy this row into the right table (Backend, Frontend or General) and give it the next free ID:

```markdown
| **B6** | <One sentence a reviewer can check by reading the diff.> | <Where the existing code already does it right.> |
```

A good rule is:

1. **Checkable from the diff.** The reviewer sees only the lines a PR adds or changes.
2. **Binary.** Two people reading the same diff would agree on pass or fail.
3. **Anchored.** It names a real file or pattern in this repo that already follows it.
4. **Worth enforcing.** Breaking it would cause a real bug, outage, leak or confusion.

| ❌ Too vague to check | ✅ Checkable |
|---|---|
| "Endpoints should be well documented." | "Every new endpoint sets `summary=` in its route decorator, like `@router.get(..., summary=\"Latest price snapshot\")` in `market.py`." |
| "The dashboard should handle errors." | "Every new metric tile (`.metric(...)`) shows a value from a `fetch()` result that was checked for an error first, like the Market tab in `app.py`." |
| "Don't write slow code." | "A new endpoint that calls yfinance more than once per request caches the result with `functools.lru_cache` or a TTL cache." |

## Ideas, if you are stuck

- Backend: every route sets `summary=` (all current routes do); query parameters with a closed set of
  values use an `Enum`, like `Period` and `Interval`; new routers are added with `app.include_router` in `main.py`.
- Frontend: every new tab's content lives inside its `with tab_...:` block; numbers go through
  `compact()` before display; new environment variables are documented in `.env.example`.

Do not reuse an idea another student in your team already used.

## Then prove it works

Follow §10 of the [Lab 7 handout](../../docs/labs/lab07_github_agentic_workflows.md): a task issue,
a PR that **breaks** your rule (the reviewer must flag your rule ID), a fix, a merge, and the task closing itself.
