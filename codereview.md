# Code Review — Part Number Parser API

**Reviewed:** 2026-03-24
**Scope:** Full codebase (`src/`, config files, Docker setup)
**Reviewer:** Claude Code

---

## Overall Assessment

The project demonstrates solid architectural thinking. Hexagonal (Ports & Adapters) layering is applied consistently, the DI wiring is clean, and the async concurrency model is appropriate. The main concerns are a critical security leak, several deployment bugs that would prevent the service from starting in Docker, and a pattern of minor but pervasive quality issues (typos, inconsistencies, unused code).

**Score: 6.5 / 10** — the architecture deserves higher, but the security and deployment issues drag it down significantly.

---

## Critical Issues

### 1. Hardcoded credentials in source code
**File:** `src/parser_api/infrastructure/web/octopart/octopart_parser.py:35–39`

```python
self._proxy = {
    "server": "http://165.254.99.179:50100",
    "username": "ponomarevoleza",
    "password": "YMmVBe9ww3",
}
```

Proxy credentials are hard-coded. Worse, `OctopartParserProvider.__init__` accepts a `proxy: dict | None = None` parameter — which is completely ignored. The constructor discards the injected value and always uses the literal. This means:
- Rotating the proxy requires a code change and redeploy.
- Credentials are visible in git history.
- The `PROXY_SERVER` / `PROXY_USERNAME` / `PROXY_PASSWORD` env vars in `Settings` have no effect for Octopart.

**Required fix:** Use the passed-in `proxy` parameter. Rotate the exposed credentials immediately.

---

### 2. Docker app service never receives its environment variables
**File:** `docker-compose.yml:1–16`

The `app` service only sets `PYTHONUNBUFFERED=1`. It has no `env_file:` directive and no entries for `MONGO_HOST`, `MONGO_ROOT_USER`, `MONGO_ROOT_PASSWORD`, `PROXY_SERVER`, etc. Pydantic Settings will read from a `.env` file in the working directory, but `.env` is (correctly) excluded from the Docker image by `.dockerignore`.

Result: `docker compose up -d --build` starts a container that immediately crashes because required settings cannot be loaded.

**Required fix:** Add `env_file: .env` to the `app` service in `docker-compose.yml`.

---

### 3. Dockerfile CMD is missing the `api` subcommand
**File:** `Dockerfile:32`

```dockerfile
CMD ["uv", "run", "src/cli.py", "--workers", "1"]
```

The CLI is built with Typer and exposes an `api` subcommand. Without it, Typer will print help and exit with a non-zero code. The correct invocation (from `CLAUDE.md`) is:

```bash
uv run src/cli.py api --host 0.0.0.0 --port 8000 --workers 1
```

**Required fix:** Add `api` to the CMD array.

---

## Major Issues

### 4. `OctopartParserProvider` ignores injected proxy, headless, and user_data_dir for browser launch
**File:** `src/parser_api/infrastructure/web/octopart/octopart_parser.py:25–40`

The constructor signature receives `user_data_dir`, `headless`, and `proxy`, stores `user_data_dir` and `headless` properly, but replaces `proxy` entirely. This makes the `HEADLESS` setting from `.env` effective for all other parsers but not for Octopart — a silent discrepancy.

---

### 5. `ParseQuerryInteractor` receives `config: Settings` and silently drops it
**File:** `src/parser_api/application/command/parsing/parse_querry.py:14–20`

```python
def __init__(
    self,
    result_writer: IResultWriter,
    registry: ParserRegistry,
    config: Settings,
) -> None:
    self._result_writer = result_writer
    self._registry = registry
    # config is never stored or used
```

The injected `Settings` object is discarded. If it was intended to carry `MIN_DELAY`/`MAX_DELAY` into `parser.parse()`, that wiring was never completed. This is a silent dead parameter.

---

### 6. `asyncio.gather` without `return_exceptions=True`
**File:** `src/parser_api/application/command/parsing/parse_querry.py:33–35`

```python
results = await asyncio.gather(
    *[parser.parse(querry.part_number) for parser in parsers]
)
```

Parsers are intended to return `[]` on error, but if any parser raises an unhandled exception (e.g., `RuntimeError("Parser is not started.")`), `gather` will propagate it and all other parsers' results are lost. `return_exceptions=True` with explicit type filtering would be more resilient.

---

### 7. Parser auto-discovery is fragile and type-unsafe
**File:** `src/parser_api/composition/ioc/infrastructure.py:40–48`

```python
for cls in IParserProvider.__subclasses__():
    parsers.append(
        cls(
            user_data_dir="./data",  # type: ignore
            proxy=configuration.proxy,  # type: ignore
            headless=configuration.HEADLESS,  # type: ignore
        )
    )
```

- `__subclasses__()` only returns direct subclasses. If any parser subclasses another parser, it will be missed.
- The `# type: ignore` comments suppress the type checker because `IParserProvider.__init__` does not define these parameters — there is no enforced constructor contract.
- `user_data_dir="./data"` is hardcoded in the DI provider, not in `Settings`. All parsers share the same session directory, which can cause browser profile conflicts.
- The log message on failure is in Russian (`"Ошибка создания парсера"`) while the entire rest of the codebase is in English.

---

### 8. `get_by_part_number` returns `None` instead of `[]` for "not found"
**File:** `src/parser_api/infrastructure/mongodb/repositories/results/reader.py:32–51`

The method signature is `-> list[ResultDocument] | None` and returns `None` when no documents match. Every caller must null-check. The idiomatic and consistent return for "no results" is an empty list `[]`. Returning `None` for absence conflates "not found" with "error", and `get_by_id` already uses `None` to mean "not found" for a single document — the semantics are different for a collection.

---

## Moderate Issues

### 9. Pervasive spelling errors in identifiers

These typos appear across the entire codebase in class names, file names, and import paths:

| Wrong | Correct | Locations |
|---|---|---|
| `Querry` / `querry` | `Query` / `query` | `parse_querry.py`, `ParseQuerryInteractor`, `__call__(self, querry: ...)` |
| `Responce` | `Response` | `responce.py`, `ResponceDTO`, `ResponceSchema` |
| `exeptions` | `exceptions` | 4 files: `infrastructure/exeptions.py`, `mongodb/exeptions.py`, `web/exeptions.py`, `presentation/.../exeptions.py` |

These aren't cosmetic — they are the actual module and class names used in imports throughout the project, making the codebase harder to navigate and increasing cognitive overhead.

---

### 10. `HEADLESS` defaults to `False` — will fail in Docker
**File:** `src/parser_api/composition/configuration/config.py:16`

```python
HEADLESS: bool = False
```

If `HEADLESS` is not set in `.env`, Camoufox will try to open a GUI browser window inside the container. Docker containers have no display by default, so browser launch will fail with an X11 error. The safe default for production/Docker should be `True`.

---

### 11. `TargetClosedError` imported from a private Playwright module
**File:** `src/parser_api/presentation/http/exeption_handler.py:5`

```python
from playwright._impl._errors import TargetClosedError
```

`_impl` is a private, internal Playwright package. It is not part of the public API and may change or disappear in any Playwright version bump. Use the public API instead: `from playwright.async_api import Error` or catch it generically.

---

### 12. Typo in user-visible error string: `"ALLERT"`
**File:** `src/parser_api/presentation/http/exeption_handler.py:57, 62`

```python
create_exception_handler(status.HTTP_500_INTERNAL_SERVER_ERROR, "ALLERT")
```

"ALLERT" should be "ALERT" — or better, a meaningful message describing what failed.

---

### 13. `PostProcessingDTO.date_` is `date`; `ResultDocument.date_` is `datetime`
**File:** `src/parser_api/application/dto/parsing/process.py` vs `src/parser_api/infrastructure/mongodb/documents/results.py`

The application DTO uses `date` (day precision) and the MongoDB document uses `datetime` (full timestamp). These are different types representing nominally the same concept. The conversion is silent and happens via the `ResultDocument` default factory — but the DTO `date_` is never mapped to the document `date_`. Both fields default independently to "now", making the DTO field effectively unused in the persistence path.

---

### 14. `ResultDocument` has two redundant "created at" timestamps
**File:** `src/parser_api/infrastructure/mongodb/documents/results.py`

Both `date_` and `created_at` default to `datetime.now()`. One of them is a leftover.

---

### 15. `cursor.to_list()` called without a length limit
**File:** `src/parser_api/infrastructure/mongodb/repositories/results/reader.py:36`

```python
docs = await cursor.to_list()
```

For a popular part number with thousands of stored results, this will load all documents into memory at once. At minimum, a limit should be applied; ideally, pagination should be implemented.

---

### 16. `min_delay` / `max_delay` parameters defined on the interface but unused through it
**File:** `src/parser_api/application/port/parser/parser.py`

`IParserProvider.parse()` declares `min_delay` and `max_delay` parameters. However, the interactor calls `parser.parse(querry.part_number)` without passing these — so they are always the per-parser defaults. The `Settings.MIN_DELAY` / `Settings.MAX_DELAY` config values are never wired up.

---

### 17. `app` service in docker-compose has no `depends_on` health check condition
**File:** `docker-compose.yml:7`

```yaml
depends_on:
  - mongo
```

`depends_on` with a bare service name only waits for the container to start, not for MongoDB to be ready. The `mongo` service has a correctly configured `healthcheck`, but it is not used here. The correct form is:

```yaml
depends_on:
  mongo:
    condition: service_healthy
```

Without this, the app may attempt to connect to MongoDB before it is ready.

---

## Minor Issues

### 18. Mouser parser accesses `tds` by index without bounds checking
**File:** `src/parser_api/infrastructure/web/mouser/mouser_parser.py`

The parser accesses `tds[0]`, `tds[1]`, etc. on table row cells. If a row has fewer cells than expected (malformed HTML, layout change), this will raise `IndexError`. An early length check would make this more robust.

---

### 19. `pyproject.toml` project description is a placeholder
**File:** `pyproject.toml:4`

```toml
description = "Add your description here"
```

---

### 20. No tests
There are no tests in the repository. The `pyproject.toml` includes a `tests` path in the Pyright config, but no `tests/` directory exists. This makes refactoring risky and prevents CI validation of parser behaviour.

---

### 21. `mongo_url` and `proxy` are `cached_property` on a Pydantic `BaseSettings` model
**File:** `src/parser_api/composition/configuration/config.py:26–36`

`cached_property` does not work correctly on Pydantic v2 model instances because Pydantic freezes `__dict__`. This can cause silent failures or unexpected behavior depending on the Pydantic version. Use `@property` or a `model_validator`.

---

### 22. `--no-cache` on `uv sync` discards dependency caching
**File:** `Dockerfile:22`

```dockerfile
RUN uv sync --frozen --no-cache
```

`--no-cache` prevents uv from caching downloaded packages. This forces a full download on every build, significantly slowing down rebuilds. Remove `--no-cache` and instead use Docker layer caching via the `COPY pyproject.toml uv.lock*` step (already present), which is the standard pattern.

---

## Strengths

1. **Architecture:** Hexagonal layering is applied correctly and consistently. Presentation, application, and infrastructure layers have clear boundaries and do not bleed into each other.

2. **Dependency Injection:** Dishka is used well. Parser and database lifecycle is managed via async context managers in the DI providers, not ad-hoc. Adding a new parser requires only implementing the interface and registering it.

3. **Concurrency model:** `asyncio.gather` for parallel parsing is the right tool. HTML parsing is offloaded to `asyncio.to_thread` to avoid blocking the event loop.

4. **Camoufox / anti-detection:** Using Camoufox with GeoIP, persistent contexts, and a CAPTCHA solver for Octopart shows genuine investment in making the scrapers reliable.

5. **LCSC parser quality:** The LCSC parser is notably thorough — it expands "More" dropdowns, handles both main and supplier tables, parses lead time ranges, and distinguishes flash-sale vs. standard stock.

6. **Configuration:** Pydantic Settings with `.env` loading is the right pattern. All secrets are meant to come from environment, not code (except for issue #1).

7. **Linting & formatting pipeline:** Ruff + Pyright + pre-commit is a good, fast toolchain with sensible rule selections.

---

## Summary Table

| # | Severity | File | Issue |
|---|---|---|---|
| 1 | **Critical** | `octopart_parser.py:35` | Hardcoded proxy credentials in source |
| 2 | **Critical** | `docker-compose.yml` | App service never receives env vars |
| 3 | **Critical** | `Dockerfile:32` | CMD missing `api` subcommand |
| 4 | **Major** | `octopart_parser.py:29` | Injected `proxy` param silently ignored |
| 5 | **Major** | `parse_querry.py:14` | `config: Settings` received but dropped |
| 6 | **Major** | `parse_querry.py:33` | `gather` without `return_exceptions=True` |
| 7 | **Major** | `infrastructure.py:40` | Fragile parser auto-discovery, hardcoded `user_data_dir` |
| 8 | **Major** | `reader.py:40` | `get_by_part_number` returns `None` for "not found" |
| 9 | **Moderate** | codebase-wide | `Querry`, `Responce`, `exeptions` spelling errors |
| 10 | **Moderate** | `config.py:16` | `HEADLESS=False` default breaks Docker |
| 11 | **Moderate** | `exeption_handler.py:5` | Import from `playwright._impl` private module |
| 12 | **Moderate** | `exeption_handler.py:57` | Typo `"ALLERT"` in error message |
| 13 | **Moderate** | `process.py` / `results.py` | `date_` is `date` in DTO, `datetime` in document |
| 14 | **Moderate** | `results.py` | Duplicate `date_` and `created_at` timestamps |
| 15 | **Moderate** | `reader.py:36` | `to_list()` without limit — unbounded memory |
| 16 | **Moderate** | `parse_querry.py` / `parser.py` | `MIN_DELAY`/`MAX_DELAY` config never wired through |
| 17 | **Moderate** | `docker-compose.yml:7` | `depends_on` doesn't use healthcheck condition |
| 18 | **Minor** | `mouser_parser.py` | `tds[n]` access without length check |
| 19 | **Minor** | `pyproject.toml:4` | Placeholder description |
| 20 | **Minor** | — | No tests |
| 21 | **Minor** | `config.py:26` | `cached_property` incompatible with Pydantic v2 |
| 22 | **Minor** | `Dockerfile:22` | `--no-cache` on `uv sync` slows every rebuild |
