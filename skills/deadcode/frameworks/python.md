# Python

## LENSES

`<pkg>` = `[project].name` in `pyproject.toml` or top package under `src/`. All lenses output schema: `[{file, line, name, kind, lens, safety}]`.

### L1 — vulture (safety: 3)

```
vulture <pkg> --min-confidence 60 --exclude '*/tests/*' \
  | awk -F: 'BEGIN{print "["} NR>1{print ","} {
      gsub(/^[ \t]+|[ \t]+$/, "", $3);
      printf "{\"file\":\"%s\",\"line\":%s,\"raw\":\"%s\"}", $1, $2, $3
    } END{print "]"}' \
  | jq '[.[] | {file, line, name: (.raw | capture("'\''(?<n>[^'\'']+)'\''") .n // "?"), kind: (.raw | capture("unused (?<k>\\w+)") .k // "unused"), lens: "vulture", safety: 3}]'
```

### L1b — deadcode (safety: 3, used as cross-check)

```
deadcode <pkg> --no-color | jq -R 'split(":") | {file: .[0], line: (.[1] | tonumber), name: .[2], kind: "unused", lens: "deadcode", safety: 3}' | jq -s '.'
```

UNION with L1; if a finding appears in both, raise safety to 2.

### L2 — orphan files (safety: 1)

```
for f in $(rg --files <pkg> -tpy); do
  mod=$(echo "$f" | sed 's|/|.|g; s|.py$||')
  base=$(basename "$f" .py)
  if ! rg -q "from ${mod%.*} import ${base}\|import ${mod}\|import ${base}" --type py; then
    echo "{\"file\":\"$f\",\"line\":1,\"name\":\"$base\",\"kind\":\"file\",\"lens\":\"orphan\",\"safety\":1}"
  fi
done | jq -s '.'
```

Skip `__init__.py`, `setup.py`, `manage.py`, files matching `tests/**`.

### L3 — unreachable code (safety: 1)

```
mypy <pkg> --warn-unreachable --no-error-summary 2>/dev/null \
  | rg ':\d+: error: (Statement is unreachable|.*never.*)' \
  | awk -F: '{printf "{\"file\":\"%s\",\"line\":%s,\"name\":\"unreachable\",\"kind\":\"branch\",\"lens\":\"unreachable\",\"safety\":1}\n", $1, $2}' \
  | jq -s '.'
```

mypy が configured されてなければスキップ。

## TEST_CMD

`pytest` if `[tool.pytest.ini_options]` in `pyproject.toml`, else `python -m unittest discover`.
Typecheck: `pyright` or `mypy` if configured.

## FRAMEWORK_HOOKS (skip — treated as live)

### Decorators

- `@app.route` / `@app.get` / `@app.post` / `@app.put` / `@app.delete` / `@app.patch` / `@app.websocket` (FastAPI / Flask)
- `@router.<verb>` (FastAPI APIRouter)
- `@click.command` / `@click.group` / `@<group>.command`
- `@app.command` / `@app.callback` (Typer)
- `@celery.task` / `@shared_task`
- `@pytest.fixture` / `@pytest.mark.<x>`
- `@property` / `@<x>.setter` / `@<x>.getter` / `@<x>.deleter`
- `@cached_property` / `@functools.lru_cache` / `@functools.cache`
- `@dataclass` / `@dataclasses.dataclass` field declarations
- `@app.exception_handler` (FastAPI)
- `@receiver` (Django signals)

### Dunder methods

`__init__` `__new__` `__del__` `__repr__` `__str__` `__eq__` `__hash__` `__lt__` `__le__` `__gt__` `__ge__` `__ne__` `__call__` `__enter__` `__exit__` `__iter__` `__next__` `__len__` `__getitem__` `__setitem__` `__delitem__` `__contains__` `__getattr__` `__setattr__` `__delattr__` `__getattribute__` `__add__` `__sub__` `__mul__` `__div__` `__truediv__` `__floordiv__` `__mod__` `__pow__` `__bool__` `__bytes__` `__format__` `__reduce__` `__copy__` `__deepcopy__` `__post_init__`

### Class-inheritance-required methods

- `pydantic.BaseModel`: `Config` inner class, `model_config`, `@field_validator` / `@model_validator`
- Django: `Meta` inner class, `save()` / `clean()` / `get_absolute_url()`
- `unittest.TestCase`: `setUp` / `tearDown` / `setUpClass` / `tearDownClass` / `test_*`
- pytest: `setup_method` / `teardown_method` / `test_*` functions
- ABC: `@abstractmethod` (subclasses override)

### File-name conventions

- `tests/**/*.py`: all `test_*` functions and `Test*` classes — always keep
- `conftest.py` fixtures — always keep
- `__init__.py`: `from .X import Y` re-exports — always keep
- `setup.py` / `manage.py` / `wsgi.py` / `asgi.py` top-level definitions — entrypoint

### Types & schemas

- `dataclass` / `pydantic.BaseModel` / `TypedDict` / `NamedTuple` / `attrs.define` field declarations
- `Enum` / `IntEnum` / `StrEnum` members
- `Protocol` class method declarations

### __all__ export

Names listed in `__all__ = [...]` are public — skip.

## ENTRYPOINTS

| framework | entry pattern |
|-----------|--------------|
| FastAPI | `main.py` `app.py` with `app = FastAPI()`, `@app.<verb>` |
| Django | `manage.py`, `urls.py` `path()` / `re_path()` args, all `views.py` |
| Flask | `app.py` with `app = Flask(__name__)`, `@app.route` |
| Click/Typer CLI | `__main__.py`, `entry_points` / `[project.scripts]` |
| Celery | `celery.py`, `@celery.task` |
| pytest | `tests/**/*.py` all `test_*` |
| Lambda | `handler.py` `lambda_handler(event, context)` |
