# MacScope Architecture

MacScope is a local Streamlit application that inventories a macOS system, stores snapshots in SQLite, and offers guarded management actions. This document describes the major subsystems as of version 3.0.

## Application layout

```text
MacScope/
  app.py                 # Streamlit navigation and page routing
  collector.py           # Collector orchestration + enrichment pipeline
  snapshot.py            # Persist / load inventory snapshots
  compare.py             # Snapshot diff helpers
  actions.py             # Guarded management actions + history
  models.py              # SQLAlchemy models
  database.py            # Engine, sessions, migrations
  identifier.py          # Classification / knowledge enrichment hooks
  inventory.py           # Inventory row helpers
  protection.py          # Critical process / path protection
  config.py              # Paths, version, schema version, defaults
  macscope/
    collectors/          # Read-only inventory collectors
    ui/                  # Streamlit pages and chrome
    timeline.py          # Persistent system timeline
    projects.py          # Project discovery / grouping
    knowledge.py         # Local software knowledge
    relationships.py     # Component relationship graph
    cleanup.py           # Cleanup review + advisor
    search.py            # Local natural-language search rules
    assistant.py         # Grounded Q&A over local facts
    storage_explorer.py  # Storage buckets / treemap data
    startup_analyzer.py  # Startup impact scoring
    updates.py           # Update detection (no install)
    annotations.py       # Favorites, pins, notes
    reports.py           # Report generation + redaction
    backup.py            # Plist / action backups
    settings.py          # User settings
  tests/                 # Pytest suite
  scripts/               # Install, test, release helpers
```

Runtime data is **not** stored in the repository. It lives under:

```text
~/Library/Application Support/MacScope/
```

## Collectors

Collectors are read-only modules that gather one inventory family (applications, processes, launch items, Homebrew, Python, Node, Docker, AI models, storage, network, crashes, permissions, etc.).

Orchestration (`collector.py`) typically:

1. Runs registered collectors
2. Discovers development projects
3. Enriches items with knowledge metadata and startup impact
4. Builds relationships
5. Returns a result object consumed by snapshot persistence and the UI

Collectors must fail soft and avoid mutating the system.

## Database

- Engine/session setup and additive migrations: `database.py`
- ORM models: `models.py`
- Schema version: `config.SCHEMA_VERSION`
- Primary entities include snapshots, inventory items, relationships, action history, timeline events, and user annotations

Migrations are additive for backward compatibility with prior MacScope databases.

## Relationships

`macscope/relationships.py` links inventory entities, for example:

- Application → Process
- Application → LaunchAgent / LaunchDaemon / Login Item
- Project → Virtual Environment / Database / Docker Container
- AI Server → Model
- Homebrew → Service

The UI presents both table and tree views with filtering.

## Timeline

`macscope/timeline.py` records persistent events for inventory deltas and management actions (installs/removals/updates, startup/security/Homebrew/Docker/Python/AI/network changes, and action history hooks). Timeline data supports the System Timeline page and grounded Assistant answers about recent changes.

## Assistant

`macscope/assistant.py` answers questions using **only** local snapshot inventory and timeline facts. It must not invent processes, sizes, or safety conclusions that are not supported by collected data.

## Cleanup engine

`macscope/cleanup.py` powers Cleanup Review and Cleanup Advisor:

- Heuristics for unused apps, caches, downloads, environments, Docker objects, orphans, broken startup items, etc.
- Recommendations include reason, estimated reclaim, confidence, risk, and recommended action
- Actual deletion remains gated by Settings and action confirmations

## Snapshots

`snapshot.py` persists a point-in-time inventory. Comparison (`compare.py`) diffs snapshots for UI and timeline generation. Snapshots enable historical analysis without rescanning constantly.

## Projects

`macscope/projects.py` discovers development workspaces from configured roots using common indicators (Python, Node, Docker, Git, Streamlit, SQLite/Postgres, Cursor, VS Code). Inventory items can be grouped by `project_key` for the Projects page.

## Knowledge engine

`macscope/knowledge.py` provides an offline catalog of common software metadata: purpose, developer, documentation link, general removal safety, typical startup behavior, common ports, and dependencies. Enrichment attaches knowledge keys to inventory items without requiring internet access.

## Reports

`macscope/reports.py` exports HTML/CSV/JSON/Markdown reports with optional redaction. Files are written under Application Support `reports/`.

## Settings

`macscope/settings.py` stores user preferences (including destructive-action acknowledgement) in local JSON under Application Support. Settings gate unsafe UI affordances.

## Action system

`actions.py` implements guarded operations (stop process, unload LaunchAgent, Homebrew service control, Trash app, Docker lifecycle, environment removal, etc.). Shared rules:

- Protection checks (`protection.py`)
- Preview + confirmation
- Backup/restore where applicable (`macscope/backup.py`)
- Action history recording
- Timeline hooks for management events

Elevation for system-level launch items remains instruction-oriented; MacScope does not store passwords.
