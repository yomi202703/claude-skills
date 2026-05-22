# Axis 5 — Framework-hook-aware filter

You audit a single source file with knowledge of **framework conventions that make an otherwise-unreferenced symbol still alive**. This axis prevents false positives from axes 1-2 by recognizing dispatcher patterns.

## What constitutes the failure

Flag a symbol as **safe to delete** (i.e. NOT a framework hook) only if you are confident none of these patterns apply:

| Pattern | Indicator |
|---|---|
| Django view | `urlpatterns` registration, `as_view()` use, in a `views.py` file |
| FastAPI / Flask route | `@app.route` / `@router.get` decorator visible |
| Pytest fixture | `@pytest.fixture` decorator |
| Click / Typer CLI command | `@click.command` / `@app.command` decorator |
| SQLAlchemy / Pydantic model | inherits `BaseModel`, `DeclarativeBase`, `Base` |
| Celery task | `@celery.task` or `@shared_task` decorator |
| Django signal handler | `@receiver` decorator, ends with `_handler` |
| JS/TS default export consumed by framework | `export default` in a Next.js page/api file |

## What constitutes acceptable design

If you see ANY of the indicators above on or above the symbol, do not flag and instead output evidence of the hook.

## Output

For each candidate that is **NOT** protected by a framework hook (i.e. truly safe to delete):

```json
{"file": "<path>", "line": <int>, "symbol": "<name>", "evidence": "<def line + nearest decorator check>", "severity": "high|medium|low", "why": "no recognized framework hook"}
```

For candidates that **are** protected (informational), emit with severity `low` and `why: "framework hook detected"`. The supervisor can dedup against axes 1-2.

Empty list if no relevant symbols.
