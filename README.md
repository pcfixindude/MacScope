# MacScope

[![Latest Release](https://img.shields.io/github/v/release/pcfixindude/MacScope?label=release)](https://github.com/pcircuitdude/MacScope/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Platform: macOS](https://img.shields.io/badge/platform-macOS-black.svg)](#supported-macos-versions)
[![CI](https://img.shields.io/github/actions/workflow/status/pcircuitdude/MacScope/ci.yml?branch=main&label=CI)](https://github.com/pcircuitdude/MacScope/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-pytest-informational.svg)](#running-tests)

**Local-only macOS inventory, monitoring, startup management, cleanup analysis, and historical comparison.**

MacScope helps you see what is installed, what is running, what starts automatically, how components relate, what resources they use, and which items may be safe to stop, disable, or remove — with previews, confirmations, backups, and an action history.

**Current version:** 3.0.0

> Polished open-source desktop administration suite for macOS power users and administrators. No cloud account. No inventory uploads. No required API keys.

---

## Feature highlights

- **Inventory** — Applications, processes, login/background items, LaunchAgents/Daemons, Homebrew, Python, Node, Docker, local AI software/models, network listeners, storage & security summaries
- **System Timeline** — Persistent history of software/startup/security/runtime changes and management actions
- **Project Workspaces** — Discover development projects and group related inventory
- **Knowledge Engine** — Offline metadata for common software (purpose, developer, ports, typical startup, removal guidance)
- **Relationship Graph** — Application↔process/startup links, project links, Homebrew services, AI server→model (tree + table)
- **Cleanup Advisor** — Recommendations with reason, estimated reclaim, confidence, and risk
- **Storage Explorer** — Drill-down buckets with treemap-style visualization when practical
- **Startup Analyzer** — Low / Medium / High startup impact estimates
- **Natural-language Search** — Local rule-based queries over inventory
- **Assistant** — Answers grounded only in local inventory + timeline facts
- **Crash History & Permissions Explorer** — DiagnosticReports grouping and TCC-oriented permission views when readable
- **Update Awareness** — Detect Homebrew/Node/Docker/Python/LM Studio updates without auto-installing
- **Snapshots & Reports** — Point-in-time history; HTML/CSV/JSON/Markdown exports with redaction
- **Guarded actions** — Stop processes, manage user LaunchAgents, Homebrew services, Trash apps, Docker lifecycle, and more — behind safety gates

Full narrative walkthrough: [User Guide](docs/user-guide/USER_GUIDE.md).

---

## Screenshots

> Replace placeholders under [`docs/images/`](docs/images/) after capturing a local session.

| Dashboard | Applications | Processes |
| --- | --- | --- |
| ![Dashboard](docs/images/dashboard.png) | ![Applications](docs/images/applications.png) | ![Processes](docs/images/processes.png) |

| Projects | Timeline | Cleanup Advisor |
| --- | --- | --- |
| ![Projects](docs/images/projects.png) | ![Timeline](docs/images/timeline.png) | ![Cleanup Advisor](docs/images/cleanup-advisor.png) |

| Assistant | Storage Explorer | Settings |
| --- | --- | --- |
| ![Assistant](docs/images/assistant.png) | ![Storage Explorer](docs/images/storage-explorer.png) | ![Settings](docs/images/settings.png) |

| Reports |
| --- |
| ![Reports](docs/images/reports.png) |

See also [`docs/screenshots/`](docs/screenshots/) for legacy placeholder paths.

---

## Architecture overview

MacScope is a Python / Streamlit app with read-only collectors, SQLite snapshots, a relationship/timeline layer, and a guarded action system.

```text
UI (Streamlit / app.py)
        │
        ▼
Collectors ──► Enrichment (knowledge, startup, projects)
        │
        ▼
Snapshots (SQLite) ◄── Timeline / Relationships / Annotations
        │
        ▼
Actions (preview → confirm → backup → mutate) + Reports
```

Deep dive: [Architecture](docs/architecture/ARCHITECTURE.md).

---

## Requirements

| Requirement | Notes |
| --- | --- |
| macOS | Primary runtime platform |
| Python | 3.12+ (3.13 supported) |
| Disk / permissions | Standard user home access; Full Disk Access optional for some collectors |
| Optional tools | Homebrew, Docker Desktop, Node — enhance inventory when installed |

### Supported macOS versions

| macOS | Support |
| --- | --- |
| macOS 14 Sonoma | Supported |
| macOS 15 Sequoia | Supported |
| macOS 13 Ventura | Best effort |
| Older releases | Not a focus; collectors/APIs may be incomplete |

Apple Silicon and Intel Macs are both in scope when Python and dependencies install cleanly.

---

## Installation

```bash
git clone https://github.com/pcircuitdude/MacScope.git
cd MacScope
chmod +x MacScope.command scripts/*.sh
./scripts/install.sh
```

The installer creates `.venv` and installs dependencies from `requirements.txt`.

Release ZIP users: expand `MacScope-3.0.0.zip`, then run the same `chmod` + `./scripts/install.sh` (or launch `MacScope.command`, which bootstraps the venv).

---

## Double-click launch

Double-click `MacScope.command`, or run:

```bash
cd /path/to/MacScope
./MacScope.command
```

The launcher:

- Resolves its own location
- Creates/reuses `.venv`
- Installs dependencies when `requirements.txt` changes
- Starts Streamlit and opens the browser
- Reuses an already-running instance on port 8501 when present
- Writes launcher logs under `~/Library/Application Support/MacScope/logs/`

---

## Terminal launch

```bash
cd /path/to/MacScope
source .venv/bin/activate
python -m streamlit run app.py
```

Exact one-liner after setup:

```bash
cd /path/to/MacScope && source .venv/bin/activate && python -m streamlit run app.py
```

---

## Privacy statement

MacScope runs entirely on your Mac.

- It does **not** send system inventory to the internet
- It does **not** require cloud AI, accounts, or API keys
- Optional documentation links open only when you click them
- Runtime data stays under `~/Library/Application Support/MacScope/`
- Reports and exports are written locally

Some optional CLIs MacScope may invoke (`brew`, `docker`, etc.) have their own network behavior outside MacScope’s control.

---

## Safety philosophy

- Destructive actions stay disabled until Settings acknowledgement
- `/System` and Apple-protected components are blocked
- Critical processes are protected (including `launchd`, `WindowServer`, `loginwindow`, kernel tasks, MacScope itself)
- Prefer Trash over permanent deletion
- Plists are backed up before disable/move when the action system supports it
- System elevation is instruction-first — **no password storage**
- Unknown items are never labeled malware
- Assistant answers only from local facts

See [SECURITY.md](SECURITY.md) for vulnerability reporting.

---

## Directory structure

```text
MacScope/
├── app.py                 # Streamlit entry / navigation
├── collector.py           # Collector orchestration
├── snapshot.py / compare.py
├── actions.py / protection.py
├── models.py / database.py / config.py
├── macscope/              # Collectors, UI, engines (timeline, projects, …)
├── tests/                 # Pytest suite
├── scripts/               # install, test, release helpers
├── docs/                  # User, developer, architecture docs + images
├── MacScope.command       # Double-click launcher
├── requirements.txt
├── VERSION
└── LICENSE                # MIT
```

Runtime (not in git):

```text
~/Library/Application Support/MacScope/
  database/
  backups/
  reports/
  logs/
  exports/
  cache/
  disabled-items/
  settings.json
```

---

## Reports

Generate HTML, CSV, JSON, or Markdown reports from a snapshot. Redaction options help when sharing with another administrator. Files land in Application Support `reports/` — openable from the Reports page / Tools & Folders.

## Snapshots

Snapshots capture point-in-time inventory for comparison and timeline deltas. Snapshot before major installs or cleanups when you want an audit trail.

## Cleanup Advisor

Advisor heuristics surface candidates (unused apps, old caches/downloads, duplicate models, unused environments, Docker leftovers, orphaned support folders, broken startup items, and more). Each recommendation includes reason, estimated reclaim, confidence, risk, and suggested action. **Always preview** before acting.

## Assistant

Ask natural questions about memory use, startup items, recent changes, or uninstall impact. Answers are grounded in the current snapshot and timeline only — never invented cloud completions.

## Project Workspaces

The Projects page discovers development workspaces from common roots and groups related applications, processes, ports, virtual environments, containers, databases, AI models, and startup items.

---

## Roadmap

High-level plans live in [ROADMAP.md](ROADMAP.md).

- **Completed:** 1.x foundation, 2.0 inventory suite, 3.0 administration suite
- **In progress:** community docs polish, screenshots, CI hardening
- **Planned:** richer project linking, advisor calibration, accessibility, offline packaging improvements

---

## FAQ

**Does MacScope need internet access?**  
No for core inventory and Assistant. Optional tools you already use may contact the network on their own.

**Is this antivirus?**  
No. MacScope does not issue malware verdicts.

**Will it delete things automatically?**  
No. Destructive actions require acknowledgement, preview, and confirmation.

**Where is my data?**  
`~/Library/Application Support/MacScope/`.

**Can I use it without Full Disk Access?**  
Yes for many collectors. Some login-item / TCC views need broader access.

**Does the Assistant call ChatGPT/Claude?**  
No. It uses local inventory rules/facts only.

---

## Troubleshooting

| Issue | Try |
| --- | --- |
| App does not open | Run `./MacScope.command` from Terminal; check `~/Library/Application Support/MacScope/logs/` |
| Empty login/background data | Grant Full Disk Access; confirm `sfltool dumpbtm` works |
| Docker page says not running | Start Docker Desktop |
| Homebrew empty | Ensure `brew` is on PATH for the launcher environment |
| Collector warnings | Open **Diagnostics** |
| Destructive buttons disabled | Settings → acknowledge safety notice → enable destructive actions |
| Port already in use | Quit the existing Streamlit instance or reuse the launcher’s port-8501 reuse behavior |

---

## Development setup

```bash
./scripts/install.sh
./scripts/update_dependencies.sh
source .venv/bin/activate
```

See [docs/developer-guide/DEVELOPMENT.md](docs/developer-guide/DEVELOPMENT.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## Running tests

```bash
./scripts/run_tests.sh
# or
source .venv/bin/activate && python -m compileall -q -x '.venv|.venv312|dist' . && pytest -q
```

## Building releases

```bash
./scripts/build_release.sh
```

Creates `dist/MacScope-<VERSION>.zip` (for example `dist/MacScope-3.0.0.zip`).

Human release steps: [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).  
CI validates ZIP creation but **does not publish** GitHub Releases automatically.

---

## Uninstalling MacScope itself

1. Quit MacScope / Streamlit.
2. Delete the project folder if desired.
3. Remove local data:

```bash
./scripts/reset_local_data.sh
```

Or delete `~/Library/Application Support/MacScope/` manually.

---

## License

MacScope is released under the [MIT License](LICENSE).

## Credits

- Built for local-first macOS administration workflows
- UI powered by [Streamlit](https://streamlit.io/)
- Community standards adapted from the [Contributor Covenant](CODE_OF_CONDUCT.md)
- Thanks to early testers and contributors

## Community

- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](SECURITY.md)
- [Style Guide](STYLE_GUIDE.md)
- [Changelog](CHANGELOG.md)
- [Discussions](https://github.com/pcircuitdude/MacScope/discussions) (enable in repo settings if not already on)
