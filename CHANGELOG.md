# Changelog

All notable changes to MacScope are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Repository documentation, contribution guidelines, security policy, and GitHub project templates
- Continuous Integration and release-validation workflows (no automatic publishing)

## [3.0.0] — 2026-07-30

### Added

- **System Timeline** — persistent history of installs/removals/updates, startup/security/Homebrew/Docker/Python/AI/network changes, and management actions
- **Projects** — development project discovery (Python/Node/Docker/Git/Streamlit/SQLite/Postgres/Cursor/VS Code) with grouped inventory
- **Knowledge Engine** — local purpose/developer/docs/startup/ports/dependency metadata for common software
- **Relationship Graph** — expanded relations (LaunchAgent/Daemon/Login Item, projects, AI server→model) with table and tree views
- **Cleanup Advisor** — recommendations with reason, estimated reclaim, confidence, and risk
- **Storage Explorer** — drill-down buckets with optional treemap visualization
- **Startup Analyzer** — Low/Medium/High startup impact scoring
- **Natural Language Search** — local rule-based inventory queries
- **Assistant** — grounded answers from snapshot + timeline only
- **Crash History** — DiagnosticReports grouped by application
- **Permissions Explorer** — TCC-backed privacy permissions when readable
- **Update Awareness** — Homebrew/Node/Docker/Python/LM Studio update signals without auto-install
- **UI polish** — command palette, favorites/pins/notes, folder shortcuts, recent activity, badges

### Changed

- Schema version bumped to 3 with additive migrations (`timeline_events`, `user_annotations`, inventory project/startup/knowledge fields)
- Collector orchestration includes projects, crashes, permissions, knowledge enrichment, and startup scoring

### Security

- Backward compatible with MacScope 2.x databases
- Destructive actions remain gated by Settings acknowledgement
- Assistant never invents facts beyond local inventory/timeline

## [2.0.0] — 2026-07-29

### Added

- Expanded inventory suite: Homebrew formulas/casks/services, Python, Node, Docker, and local AI software/models
- Storage and security summaries
- Initial relationships engine between components
- Cleanup Review with preview/selection flows
- HTML/CSV/JSON/Markdown reports with redaction options
- Action history with restore for backed-up plists
- Diagnostics and Settings pages
- Runtime data under `~/Library/Application Support/MacScope/`
- Stable identifiers, catalog metadata, backup helpers, and release packaging scripts

### Changed

- Schema version 2 with additive migrations from 1.x
- Richer applications/processes/network collectors

### Security

- Destructive actions disabled until Settings acknowledgement
- Prefer Trash; plist backups before disable/move
- System elevation remains instruction-first (no password storage)

## [1.0.0] — 2026-07-29

### Added

- Initial MacScope release as a local Streamlit macOS inventory application
- Collectors for applications, processes, launch items, login/background items, Homebrew, network, and system facts
- SQLite snapshots and comparison
- Guarded actions with protection rules for critical processes and system paths
- Two-level Streamlit UI, tests, launcher (`MacScope.command`), and basic documentation

## Version lineage summary

| Line | Focus |
| --- | --- |
| **1.x** | Local inventory foundation, snapshots, guarded actions |
| **2.0** | Full inventory suite (dev/AI/runtime ecosystems), reports, cleanup review |
| **3.0** | Administration suite: timeline, projects, advisor, assistant, storage/startup intelligence |

[Unreleased]: https://github.com/pcfixindude/MacScope/compare/v3.0.0...HEAD
[3.0.0]: https://github.com/pcfixindude/MacScope/releases/tag/v3.0.0
[2.0.0]: https://github.com/pcfixindude/MacScope/releases/tag/v2.0.0
[1.0.0]: https://github.com/pcfixindude/MacScope/releases/tag/v1.0.0
