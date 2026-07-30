# Changelog

## 2.0.0 — 2026-07-29

### Added
- Full navigation for applications, processes, startup, login/background items, LaunchAgents/Daemons, Homebrew, Python, Node, Docker, AI models, network, storage, security, relationships, cleanup review, snapshots, reports, action history, diagnostics, settings, and about.
- Unified inventory item model with stable IDs and expanded metadata.
- Application Support data directory (`~/Library/Application Support/MacScope/`) for database, backups, reports, logs, exports, cache, and disabled items.
- Schema versioning and additive migrations from Version 1 databases.
- Python, Node, Docker, AI, and Storage collectors with bounded scans.
- Relationship derivation and Cleanup Review candidates.
- HTML/CSV/JSON/Markdown report exports with redaction settings.
- Expanded guarded actions including restore for backed-up plists, Docker lifecycle, environment cleanup, and Trash workflows.
- Local knowledge catalog for common Apple and third-party components.
- Persistent settings with destructive actions disabled until safety acknowledgement.
- Launcher dependency caching, already-running detection, and external log storage.
- Release and maintenance scripts under `scripts/`.

### Changed
- Version bumped to 2.0.0.
- Dashboard and inventory pages use summary + inspector layout across categories.
- Snapshot comparison expanded for AI, storage, security, and port close events.

### Safety
- Destructive actions remain off by default.
- System LaunchDaemons/Agents requiring elevation remain instruction-first.
- No cloud services, API keys, or inventory uploads.

## 1.0.0 — 2026-07-29

Initial Version 1 release with core inventory, snapshots, comparison, and guarded management actions.
