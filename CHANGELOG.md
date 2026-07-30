# Changelog

## 3.0.0 — 2026-07-30

### Added
- **System Timeline** — persistent history of installs/removals/updates, startup/security/Homebrew/Docker/Python/AI/network changes, and management actions.
- **Projects** — development project discovery (Python/Node/Docker/Git/Streamlit/SQLite/Postgres/Cursor/VS Code) with grouped inventory.
- **Knowledge Engine** — local purpose/developer/docs/startup/ports/dependency metadata for common software.
- **Relationship Graph** — expanded relations (LaunchAgent/Daemon/Login Item, projects, AI server→model) with table and tree views.
- **Cleanup Advisor** — recommendations with reason, estimated reclaim, confidence, and risk (unused apps, old downloads, duplicates, orphans, and more).
- **Storage Explorer** — drill-down buckets with optional treemap visualization.
- **Startup Analyzer** — Low/Medium/High startup impact scoring.
- **Natural Language Search** — local rule-based inventory queries.
- **Assistant** — grounded answers from snapshot + timeline only.
- **Crash History** — DiagnosticReports grouped by application.
- **Permissions Explorer** — TCC-backed privacy permissions when readable.
- **Update Awareness** — Homebrew/Node/Docker/Python/LM Studio update signals without auto-install.
- **UI polish** — command palette, favorites/pins/notes, folder shortcuts, recent activity, badges.

### Changed
- Schema version bumped to 3 with additive migrations (`timeline_events`, `user_annotations`, inventory project/startup/knowledge fields).
- Collectors orchestration now includes projects, crashes, permissions, knowledge enrichment, and startup scoring.

### Safety
- Backward compatible with MacScope 2.x databases.
- Destructive actions remain gated by Settings acknowledgement.
- Assistant never invents facts beyond local inventory/timeline.

## 2.0.0 — 2026-07-29

Full local inventory suite with Homebrew/Python/Node/Docker/AI collectors, reports, relationships, cleanup review, and guarded actions.

## 1.0.0 — 2026-07-29

Initial Version 1 release.
