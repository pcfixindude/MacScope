# Changelog

All notable changes to MacScope are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [4.0.0] — 2026-07-30

### Added

- **Project Intelligence** — first-class projects with git branch/status/commit, README/license/requirements, package files, size, activity, custom roots, and pinning
- **Workspace Manager** — create workspaces, assign apps/projects/URLs/commands/venvs/Docker/Homebrew/ports/AI servers/scripts; start/stop/restart/status/health with graceful scoped shutdown
- **Historical Intelligence** — timeline daily/weekly/monthly views, search, filter, CSV/JSON export; broader event types (permissions, storage, project activity, environments)
- **Recommendation Engine** — scored recommendations with category, confidence, impact, benefit, risk, evidence, related items, timeline/project refs; explains WHY; never blind deletion
- **Usage History** — CPU/memory/disk/launch samples from snapshots with charts and anomaly highlights
- **System Explorer** — unified connected navigation across apps, processes, startup, projects, environments, ports, knowledge
- **Knowledge Engine 2** — offline knowledge pack with 2,600+ local entries (apps, agents, packages, ports, frameworks)
- **Natural Language Search 2** — richer local queries (Docker/Python projects, inactive apps, unused models, weekly installs)
- **Assistant Intelligence** — evidence, confidence, related items, timeline/project/report links on every answer
- **Developer Dashboard** — projects, repos, branches, containers, databases, venvs, AI servers, ports, workspace health
- **Automation Rules** — weekly snapshots, monthly reports, startup/port/downloads/storage notifications (local only)
- **Visual Analytics** — timeline charts, usage charts, relationship tables, workspace map, storage treemap helpers
- **Plugin Architecture** — collectors exposed as plugins with isolated failures and manifests
- **Performance helpers** — cache invalidation, progress indicators retained on collect, collector cache setting
- **Professional polish** — expanded navigation, saved searches, pinned projects/workspaces, folder tools retained

### Changed

- Schema version bumped to **4** with additive tables/columns (`workspaces`, `workspace_members`, `usage_samples`, `automation_rules`, `automation_runs`, `recommendation_records`, inventory `workspace_id`/`usage_score`/`last_used_at`)
- Snapshot save records usage samples and evaluates due automation rules
- Projects / Timeline / Search / Assistant / Cleanup Advisor pages upgraded to 4.0 renderers while preserving prior inventory pages

### Security

- Backward compatible with MacScope 3.x databases
- Workspace stop/start only targets assigned members
- Assistant remains grounded in local evidence only
- Destructive actions remain Settings-gated

## [3.0.0] — 2026-07-30

### Added

- System Timeline, Projects, Knowledge Engine, Relationship Graph expansions
- Cleanup Advisor, Storage Explorer, Startup Analyzer
- Natural-language search, grounded Assistant, Crash History, Permissions Explorer
- Update Awareness, UI polish (palette, favorites/pins/notes, folder shortcuts)

### Changed

- Schema version 3 with additive migrations

## [2.0.0] — 2026-07-29

### Added

- Full inventory suite (Homebrew/Python/Node/Docker/AI), reports, relationships, cleanup review, Application Support data layout

## [1.0.0] — 2026-07-29

### Added

- Initial local Streamlit macOS inventory application with snapshots and guarded actions

## Version lineage summary

| Line | Focus |
| --- | --- |
| **1.x** | Local inventory foundation |
| **2.0** | Inventory suite + reports |
| **3.0** | Administration suite (timeline/projects/advisor/assistant) |
| **4.0** | Understanding platform (workspaces, usage, explorer, automation, plugins) |

[Unreleased]: https://github.com/pcircuitdude/MacScope/compare/v4.0.0...HEAD
[4.0.0]: https://github.com/pcircuitdude/MacScope/releases/tag/v4.0.0
[3.0.0]: https://github.com/pcircuitdude/MacScope/releases/tag/v3.0.0
[2.0.0]: https://github.com/pcircuitdude/MacScope/releases/tag/v2.0.0
[1.0.0]: https://github.com/pcircuitdude/MacScope/releases/tag/v1.0.0
