# Roadmap

This roadmap tracks MacScope’s direction after the 3.0.0 release. Dates are aspirational; priorities may change based on user feedback and safety review.

## Completed

### 1.x — Foundation
- Local Streamlit application shell
- Core collectors: applications, processes, launch items, login/background, Homebrew, network, system
- SQLite snapshots and comparison
- Guarded actions with protection rules
- Basic documentation and release packaging

### 2.0 — Inventory suite
- Python / Node / Docker / AI collectors
- Storage and security summaries
- Relationships engine (initial)
- Cleanup Review
- Reports (HTML/CSV/JSON/Markdown) with redaction
- Application Support data layout
- Settings, Diagnostics, Action History restore flows

### 3.0 — Administration suite
- System Timeline
- Project awareness / Project Workspaces
- Local Knowledge Engine
- Expanded Relationship Graph (tree + table)
- Cleanup Advisor
- Storage Explorer
- Startup Analyzer
- Natural-language inventory search (local rules)
- Grounded local Assistant
- Crash History and Permissions Explorer
- Update Awareness (detect only)
- UI polish: command palette, favorites/pins/notes, folder shortcuts

## In Progress

- Community documentation and GitHub project polish
- Screenshot capture for README / user guide placeholders
- Broader automated CI coverage for release validation

## Planned

- Richer project workspace linking (deeper Git/workspace metadata without network dependency)
- Expanded local knowledge catalog coverage
- Improved Cleanup Advisor confidence calibration and false-positive reduction
- More complete permissions visibility where macOS APIs allow (still read-only)
- Exportable timeline digests for audits
- Optional offline packaging improvements for non-developer users
- Accessibility pass on Streamlit navigation and dense tables

## Future Ideas

- Signed / notarized outer launcher packaging (outside the Python tree)
- Read-only “audit mode” profile with destructive UI hidden entirely
- Deeper Docker/Homebrew dependency graphs
- Optional local embedding index for semantic search (still offline; no cloud)
- Plugin-style collector registration with strict safety contracts
- Multi-user admin notes syncing **only** via user-controlled local/shared folders (never a MacScope cloud)

## Non-goals

- Cloud inventory sync or SaaS control plane
- Automatic malware verdicts
- Silent bulk deletion
- Password storage or improvised privilege escalation
- Mandatory internet access for core inventory features

Suggestions welcome via GitHub Discussions (**Ideas**) or Feature Request issues.
