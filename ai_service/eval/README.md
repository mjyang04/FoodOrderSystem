# fos_ai eval harness

Labelled regression suite for the AI service. Four suites, 130 total cases:

| Suite | Cases | Gates |
|-------|-------|-------|
| search | 50 | Hit@5 >= 0.80, MRR >= 0.60, nDCG@5 >= 0.65 |
| recommend | 30 | pass_rate == 1.0 |
| parse | 30 | restaurant_match == 1.0, confidence_pass_rate >= 0.9 |
| chat | 20 | tool_plan_match >= 0.80, text_contains_rate >= 0.80 |

## Layout

```
ai_service/eval/
  conftest.py              # shared pytest fixtures + deterministic 21-item menu
  data/                    # labelled cases (json)
  metrics/
    retrieval.py           # hit_at_k, reciprocal_rank, ndcg_at_k, mean
    generation.py          # exact_match, field_f1
    judge.py               # llm_as_judge (stubbed in CI)
  runners/                 # callable runners returning RunResult
  reports/                 # generated markdown; gitignored except .gitkeep
  test_*_quality.py        # pytest wrappers — run with `-m eval`
```

The CLI entry point lives inside the service package at
`fos_ai.eval.run` and bridges `sys.path` so the tests and the CLI share a
single source of truth for runners.

## Running

From `ai_service/`:

```bash
# pytest (all suites)
uv run pytest eval/ -m eval -s

# CLI (writes markdown report)
uv run python -m fos_ai.eval.run --suite all
uv run python -m fos_ai.eval.run --suite search --out /tmp/search.md
```

Both paths apply the same gates; the CLI exits 1 on any gate failure.

## Labels <-> schema

`eval/conftest.py::_EVAL_MENU_ITEMS` pins 21 food ids from
`src/db/schema.sql` seed data. Every case file references ids from this
set; touch the menu constant and every label must still resolve.

## No real LLM in CI

Parse suite uses per-case stubbed tool_call payloads. Chat suite uses a
scripted LLM that returns hard-coded assistant blocks. The judge metric
(`llm_as_judge`) is unit-tested with a stub; its real-LLM path is opt-in
via `EVAL_USE_REAL_LLM=1` and not exercised by the CI workflow.
