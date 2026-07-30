# Developer Guide

This guide covers local development for MacScope.

## Environment setup

Requirements:

- macOS (development and runtime target)
- Python 3.12+ (3.13 supported)
- Xcode Command Line Tools recommended for some system CLIs
- Optional: Homebrew, Docker Desktop, Node, depending on collectors you want to exercise live

Clone and install:

```bash
git clone https://github.com/pcfixindude/MacScope.git
cd MacScope
chmod +x MacScope.command scripts/*.sh
./scripts/install.sh
```

## Virtual environments

The installer creates `.venv` in the repository root.

```bash
source .venv/bin/activate
python -V
pip list
```

Update dependencies:

```bash
./scripts/update_dependencies.sh
```

Do not commit `.venv/` or machine-local databases.

## Running locally

Double-click style:

```bash
./MacScope.command
```

Terminal style:

```bash
source .venv/bin/activate
python -m streamlit run app.py
```

Headless smoke:

```bash
python -m streamlit run app.py --server.headless true --server.port 8599
```

## Testing

```bash
source .venv/bin/activate
python -m compileall -q -x '.venv|.venv312|dist' .
pytest -q
```

Or:

```bash
./scripts/run_tests.sh
```

Guidelines:

- Prefer temp directories and fixtures
- Stub external CLIs when possible
- Keep tests offline and deterministic

## Debugging

- Launcher logs: `~/Library/Application Support/MacScope/logs/`
- App log: `.../logs/macscope.log`
- Diagnostics page inside the app surfaces collector warnings
- For DB inspection, open `~/Library/Application Support/MacScope/database/macscope.db` with a local SQLite browser (never commit it)

Reset local runtime data (destructive to MacScope’s own data, not your Mac apps):

```bash
./scripts/reset_local_data.sh
```

## Adding collectors

1. Create `macscope/collectors/<name>.py` implementing the existing collector base/pattern.
2. Return inventory items with stable categories/fields.
3. Register the collector in the orchestration path (`collector.py` / collectors package init).
4. It will appear in the plugin registry via `macscope.plugins.bootstrap_builtin_plugins`.
5. Fail soft on missing tools/permissions (plugin failures are isolated).
6. Add tests with fixtures; do not require the developer’s full disk.
7. Update architecture/user docs if the collector is user-visible.

Collectors must be read-only.

## Adding 4.0 pages

Prefer `macscope/ui/v4_pages.py` for new platform pages (Workspaces, Explorer, Automation, etc.), then wire the label into `PAGES` and the `elif` dispatch in `app.py`.

## Adding pages

1. Prefer extending `macscope/ui/` modules over bloating `app.py`.
2. Wire navigation in `app.py` using the existing page list pattern.
3. Reuse inventory views/action panels when displaying items.
4. Keep destructive controls settings-gated.
5. Document the page in the user guide if it is user-facing.

## Creating migrations

1. Add/adjust SQLAlchemy models in `models.py`.
2. Teach `database.py` to create new tables and add missing columns safely.
3. Bump `SCHEMA_VERSION` in `config.py`.
4. Keep upgrades additive and backward compatible whenever possible.
5. Add a schema/migration test.

Never delete user timeline/annotations/snapshot history without an explicit, documented migration plan.

## Writing tests

- Place tests under `tests/`
- Follow names like `test_macscope_v3.py` for feature-family coverage
- Cover search grounding, action guards, stable IDs, and migrations for risky areas
- Use `conftest.py` fixtures for temporary DB sessions

## Building releases

```bash
./scripts/build_release.sh
```

Produces `dist/MacScope-<VERSION>.zip`.

Follow [RELEASE_CHECKLIST.md](../../RELEASE_CHECKLIST.md) for tagging and GitHub Release upload. CI validates the ZIP creation path but does **not** publish releases automatically.

## Related docs

- [Architecture](../architecture/ARCHITECTURE.md)
- [Style Guide](../../STYLE_GUIDE.md)
- [Contributing](../../CONTRIBUTING.md)
- [Roadmap](../../ROADMAP.md)
