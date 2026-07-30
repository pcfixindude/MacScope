# MacScope

MacScope is a **local-only** macOS inventory, monitoring, startup-management, software-management, cleanup-analysis, and historical-comparison application.

It helps you see what is installed, what is running, what starts automatically, how components relate, what resources they use, and which items may be safe to stop, disable, or remove — with previews, confirmations, backups, and an action history.

**Version:** 2.0.0

## Screenshots

> Place screenshots here after first launch:
>
> - `docs/screenshots/dashboard.png`
> - `docs/screenshots/applications.png`
> - `docs/screenshots/cleanup.png`
> - `docs/screenshots/compare.png`

## Installation

```bash
cd ~/Projects/MacScope
chmod +x MacScope.command scripts/*.sh
./scripts/install.sh
```

Requires Python 3.12+ (3.13 also fine). The installer creates `.venv` and installs dependencies.

## Double-click launch

Double-click `MacScope.command`, or run:

```bash
cd ~/Projects/MacScope
./MacScope.command
```

The launcher:

- Resolves its own location
- Creates/reuses `.venv`
- Installs dependencies only when `requirements.txt` changes
- Starts Streamlit and opens the browser
- Reuses an already-running instance on port 8501 when present
- Writes launcher logs under `~/Library/Application Support/MacScope/logs/`

## Terminal launch

```bash
cd ~/Projects/MacScope
source .venv/bin/activate
python -m streamlit run app.py
```

Exact command after setup:

```bash
cd ~/Projects/MacScope && source .venv/bin/activate && python -m streamlit run app.py
```

## Feature overview

- Applications, processes, login/background items, LaunchAgents/Daemons
- Homebrew formulas, casks, and services
- Python / Node / Docker / local AI software and models
- Network listeners with binding classification
- Storage and security summaries
- Relationships between components
- Cleanup Review with preview/selection
- Snapshots and rich comparison
- HTML/CSV/JSON/Markdown reports with redaction
- Action history with restore for backed-up plists
- Diagnostics and Settings

## Safety model

- No cloud services, no API keys, no inventory uploads
- Destructive actions disabled until Settings acknowledgement
- `/System` and Apple-protected components blocked
- Critical processes protected (launchd, WindowServer, loginwindow, kernel, MacScope, parent shell)
- Prefer Trash over permanent deletion
- Plists backed up before disable/move
- System elevation is instruction-first (no password storage in Streamlit)
- Unknown items are never labeled malware

## Data-storage locations

All runtime data lives outside the repository:

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

## Privacy statement

MacScope runs entirely on your Mac. It does not send system inventory to the internet. Optional homepage links in the local catalog open only when you click them.

## Supported actions

- Stop/force-quit processes (with protection + confirmation)
- Unload/disable/re-enable user LaunchAgents; backup/restore plists
- Homebrew service start/stop/restart; uninstall with dependency review
- Quit/reveal/Trash applications; preview related files in cleanup flows
- Docker container/image lifecycle and selected prune categories after preview
- Remove selected venvs / node_modules / models after confirmation
- Export reports; restore backed-up plists from Action History

## Unsupported / intentional manual operations

- Arbitrary shell commands
- Silent bulk deletes
- Password collection / improvised privilege escalation for system LaunchDaemons
- Antivirus / malware verdicts
- Whole-disk recursive scans on every page render
- Automatic dependent uninstalls

## Troubleshooting

| Issue | Try |
| --- | --- |
| App does not open | Run `./MacScope.command` from Terminal; check `~/Library/Application Support/MacScope/logs/` |
| Empty login/background data | Grant Full Disk Access; confirm `sfltool dumpbtm` works |
| Docker page says not running | Start Docker Desktop |
| Homebrew empty | Ensure `brew` is on PATH for the launcher environment |
| Collector warnings | Open **Diagnostics** |
| Destructive buttons disabled | Settings → acknowledge safety notice → enable destructive actions |

## Development setup

```bash
./scripts/install.sh
./scripts/update_dependencies.sh
source .venv/bin/activate
```

## Test commands

```bash
./scripts/run_tests.sh
# or
source .venv/bin/activate && python -m compileall -q . && pytest -q
```

## Release build

```bash
./scripts/build_release.sh
```

Creates `dist/MacScope-2.0.0.zip`.

## Uninstalling MacScope itself

1. Quit MacScope / Streamlit.
2. Delete the project folder if desired.
3. Remove local data:

```bash
./scripts/reset_local_data.sh
```

Or delete `~/Library/Application Support/MacScope/` manually.
