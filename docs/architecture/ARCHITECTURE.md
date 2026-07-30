# MacScope Architecture

MacScope is a local Streamlit application that inventories a macOS system, stores snapshots in SQLite, and offers guarded management actions. This document describes the major subsystems as of version **4.0**.

MacScope 4.0 extends 3.x into an understanding platform: every subsystem aims to answer what something is, why it is present, what depends on it, what changed, whether removal is safe to consider, which project uses it, and what happens if it is disabled.

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
    timeline.py          # Persistent system timeline (+ export/views)
    projects.py          # Project intelligence / grouping / pinning
    workspaces.py        # Workspace manager (start/stop/health)
    recommendations.py   # Scored recommendation engine
    usage.py             # Usage history samples
    explorer.py          # Unified system explorer graphs
    knowledge.py         # Local software knowledge + pack
    data/knowledge_pack.json
    relationships.py     # Component relationship graph
    cleanup.py           # Cleanup review heuristics
    search.py            # Local natural-language search rules
    assistant.py         # Grounded Q&A with evidence/confidence
    analytics.py         # Chart-ready analytics frames
    automation.py        # Local automation rules
    plugins.py           # Collector plugin registry
    cache.py             # Lightweight TTL cache
    storage_explorer.py  # Storage buckets / treemap data
    startup_analyzer.py  # Startup impact scoring
    updates.py           # Update detection (no install)
    annotations.py       # Favorites, pins, notes, saved searches
    reports.py           # Report generation + redaction
    backup.py            # Plist / action backups
    settings.py          # User settings
    ui/v4_pages.py       # 4.0 page renderers
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

`macscope/settings.py` stores user preferences (including destructive-action acknowledgement) in local JSON under Application Support. Settings gate unsafe UI affordances. V4 adds custom project roots, pinned projects, usage/automation toggles, and collector cache timing.

## Workspaces

`macscope/workspaces.py` persists workspaces and members in SQLite. Start/stop/restart operate only on assigned members (applications, projects, URLs, terminal commands, brew services, docker containers, AI servers, scripts). Unrelated software is never targeted.

## Usage & automation

`macscope/usage.py` records per-snapshot usage samples. `macscope/automation.py` evaluates local rules (weekly snapshots, monthly reports, startup/port/download/storage notifications) without cloud services.

## Plugins & performance

`macscope/plugins.py` wraps collectors as plugins with isolated failures and manifests. `macscope/cache.py` provides TTL caching and invalidation after snapshot collection.

## Action system

`actions.py` implements guarded operations (stop process, unload LaunchAgent, Homebrew service control, Trash app, Docker lifecycle, environment removal, etc.). Shared rules:

- Protection checks (`protection.py`)
- Preview + confirmation
- Backup/restore where applicable (`macscope/backup.py`)
- Action history recording
- Timeline hooks for management events

Elevation for system-level launch items remains instruction-oriented; MacScope does not store passwords.
