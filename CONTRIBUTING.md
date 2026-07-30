# Contributing to MacScope

Thank you for your interest in improving MacScope. This guide explains how to collaborate safely and productively.

## Project philosophy

MacScope is a **local-only** macOS administration suite. Contributions should preserve:

- Privacy first — no cloud telemetry, no inventory uploads, no required API keys
- Safety first — destructive actions stay gated, previewed, and reversible where practical
- Honesty — never invent facts in Assistant answers or invent malware verdicts
- Continuity — extend existing collectors, models, pages, and database tables rather than duplicating them
- Clarity — prefer readable, maintainable code over clever abstractions

If a change would make MacScope less local, less safe, or more opaque, it is out of scope.

## Code style

- Python 3.12+ with modern typing (`from __future__ import annotations` where already used)
- Prefer small, focused modules that match existing package layout under `macscope/`
- Follow patterns in nearby files for naming, logging, and error handling
- Keep Streamlit UI changes minimal and consistent with existing pages
- Run formatting/lint tooling available in the project (`ruff` is listed in requirements)
- See [STYLE_GUIDE.md](STYLE_GUIDE.md) for conventions

## Branch strategy

- `main` — stable, releasable branch
- Feature work: `feature/<short-description>`
- Bug fixes: `fix/<short-description>`
- Documentation: `docs/<short-description>`
- Keep branches focused; avoid mixing unrelated refactors with feature work

## Commit message guidance

Use concise, imperative subjects:

```text
Add crash collector coverage for DiagnosticReports
Fix timeline delta when previous snapshot is empty
Docs: clarify Full Disk Access troubleshooting
```

Guidelines:

- Prefer one logical change per commit when practical
- Explain *why* in the body if the subject is not enough
- Do not commit local databases, logs, secrets, or `dist/` artifacts
- Do not amend shared history unless maintainers request it

## How to report bugs

1. Search existing issues to avoid duplicates.
2. Open a bug report using the **Bug Report** template.
3. Include macOS version, MacScope version (`VERSION`), Python version, and reproduction steps.
4. Attach relevant Diagnostics excerpts when safe — redact personal paths if needed.
5. Never paste secrets, passwords, or Full Disk Access dumps containing private content without redaction.

## How to request features

1. Open a **Feature Request** using the template.
2. Describe the problem, proposed solution, and alternatives considered.
3. Explain how the feature stays local-only and safe for system-management workflows.
4. Prefer extending an existing subsystem (collectors, timeline, knowledge, cleanup) over adding a parallel implementation.

## How to submit pull requests

1. Fork the repository (or create a branch if you have write access).
2. Create a focused branch from up-to-date `main`.
3. Implement the change with tests and documentation updates.
4. Run the validation commands in [Testing requirements](#testing-requirements).
5. Open a pull request using the PR template.
6. Link related issues and describe risk/safety impact for management actions.

## Testing requirements

Before requesting review:

```bash
source .venv/bin/activate
python -m compileall -q -x '.venv|.venv312|dist' .
pytest -q
```

Additional expectations:

- Add or update tests for new collectors, actions, migrations, and search/assistant logic
- Prefer deterministic unit tests; avoid requiring Docker/Homebrew when a fixture can stub the dependency
- Do not rely on machine-specific inventory contents
- If UI-only documentation changes, note that application tests were still run

## Review expectations

Maintainers look for:

- Correctness and macOS safety
- Backward-compatible database/schema changes (additive migrations only unless discussed)
- No duplication of collectors, tables, or pages
- Clear docs for user-facing behavior
- Adequate tests
- No secrets or local inventory data in the diff

Reviews may request smaller PRs when scope is too broad.

## Documentation requirements

Update relevant docs when behavior or workflows change:

- `README.md` for install/launch/feature highlights
- `CHANGELOG.md` under an `[Unreleased]` section (or the next version when releasing)
- `docs/user-guide/` for end-user workflows
- `docs/developer-guide/` / `docs/architecture/` for contributor-facing design
- `ROADMAP.md` when completing or planning major work

Documentation-only PRs are welcome.

## Coding standards

- Reuse `Item`, collectors, settings, actions, and snapshot APIs
- Stable identifiers must remain deterministic across snapshots
- Prefer Trash and backups over permanent deletion
- Guard destructive paths behind settings acknowledgement
- Keep network usage optional and user-initiated (for example, opening a docs URL)
- Avoid whole-disk recursive scans on every page render

## Safety requirements for system-management code

Contributors working near processes, launchd, Homebrew, Docker, or filesystem cleanup must:

1. Preserve protection rules for critical processes and `/System` paths
2. Preview impact before mutation
3. Require explicit confirmation for destructive actions
4. Back up plists / support restore where the existing action system does
5. Never store passwords or automate improvised privilege escalation
6. Never claim malware detection or invent “safe to remove” certainty beyond documented heuristics
7. Keep Assistant and recommendations grounded in local inventory facts
8. Log enough for Diagnostics without writing secrets

If unsure whether an action is safe enough for MacScope, open an issue for design discussion before implementing.
