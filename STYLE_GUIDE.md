# MacScope Style Guide

Conventions for keeping MacScope readable, safe, and consistent.

## Naming conventions

| Kind | Convention | Examples |
| --- | --- | --- |
| Modules | `snake_case` | `startup_analyzer.py` |
| Packages | short nouns | `macscope/collectors/` |
| Classes | `PascalCase` | `TimelineEvent`, `ApplicationsCollector` |
| Functions / methods | `snake_case` | `record_action_timeline` |
| Constants | `UPPER_SNAKE` | `SCHEMA_VERSION`, `PROTECTED_PROCESS_NAMES` |
| Streamlit page labels | Title Case strings | `"Cleanup Advisor"` |
| Stable IDs | deterministic hashes/keys | via `macscope.stable_id` |
| DB tables | plural `snake_case` | `timeline_events` |
| DB columns | `snake_case` | `project_key`, `startup_impact` |

Prefer existing vocabulary: *collector*, *snapshot*, *inventory item*, *action*, *relationship*, *timeline event*.

## Database conventions

- Schema changes are **additive** unless a major migration is explicitly planned
- Bump `SCHEMA_VERSION` in `config.py` when the on-disk schema changes
- Implement migrations in `database.py` (create tables / add columns safely)
- Do not drop user data during upgrades
- Keep runtime DB under Application Support, never in git
- Models live in `models.py` and stay aligned with collectors/snapshots

## Collector conventions

- One collector family per module under `macscope/collectors/`
- Collectors return inventory items; they do not mutate the system
- Register collectors through the existing orchestration in `collector.py`
- Fail soft: log warnings, return partial results, never crash the whole scan
- Avoid duplicate collection of the same source data
- Keep scans bounded; do not recursively walk the entire disk on every refresh
- Tag categories consistently with existing pages (`Applications`, `Python`, …)

## UI conventions

- Pages live under `macscope/ui/`; keep `app.py` as navigation/orchestration
- Reuse inventory tables/actions panels instead of inventing parallel grids
- Destructive controls remain disabled until Settings acknowledgement
- Prefer clear empty states over placeholder noise
- Do not redesign the information architecture casually
- Screenshots for docs go in `docs/images/` or `docs/screenshots/`

## Safety conventions

- Protect critical processes and Apple system paths
- Prefer Trash + backups over permanent deletion
- Require preview + confirmation for destructive actions
- Never store admin passwords
- Never invent Assistant facts; answer only from local inventory/timeline
- Unknown ≠ malicious
- Update Awareness detects only; it must not auto-install

## Testing conventions

- Tests live in `tests/`
- Use fixtures/temp dirs; do not depend on the developer’s real Applications folder
- Cover migrations, stable IDs, search rules, assistant grounding, and action guards
- Name tests `test_<behavior>`
- Keep tests fast and offline

## Documentation standards

- User-facing docs: clear steps, safety callouts, no jargon without explanation
- Developer docs: point to modules and extension points
- Keep links relative within the repo when possible
- Update `CHANGELOG.md` for user-visible changes
- Do not document speculative features as shipped

## Python style notes

- Match surrounding file style (imports, typing, logging)
- Avoid broad `except:` — catch specific exceptions and log
- Do not add network calls to core inventory paths
- Keep dependencies justified in `requirements.txt` / `requirements-dev.txt`
