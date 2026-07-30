# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 3.x | Yes |
| 2.x | Security fixes considered for critical issues |
| 1.x | No (please upgrade) |
| Pre-release / development builds | Best effort |

Always prefer the latest release from GitHub Releases.

## How to privately report vulnerabilities

Please **do not** open a public GitHub issue for security vulnerabilities.

Prefer one of these private channels:

1. GitHub Security Advisories for this repository:  
   `https://github.com/pcfixindude/MacScope/security/advisories/new`
2. If advisories are unavailable, contact the repository owner via GitHub with a private message titled `[SECURITY] MacScope` and wait for acknowledgment before posting details publicly.

Include:

- MacScope version (`VERSION` file or About page)
- macOS version and hardware generation if relevant
- Clear reproduction steps
- Impact assessment (data exposure, privilege escalation, unintended destructive action, etc.)
- Proof of concept **only if it does not destroy user data**
- Suggested remediation if you have one

## Expected response process

| Stage | Target |
| --- | --- |
| Acknowledgment | Within 7 days |
| Initial triage | Within 14 days |
| Fix / advisory plan | Based on severity and complexity |
| Public disclosure | Coordinated after a fix or mitigation is available when practical |

We may ask for more detail or a minimal reproduction. Complex issues involving launchd, TCC, or Full Disk Access may take longer to validate safely.

## Security principles

- Local-first: inventory and actions stay on the user’s Mac
- Least surprise: destructive operations require acknowledgement and confirmation
- Defense in depth: protection rules block critical processes and system paths
- Prefer reversible operations (Trash, backups, restore) over permanent deletion
- No password storage for administrative elevation
- No silent bulk deletes or arbitrary remote command execution
- Honest uncertainty: unknown items are not labeled malware

## Local-only privacy model

MacScope is designed so that:

- System inventory is stored in `~/Library/Application Support/MacScope/`
- No cloud AI, telemetry, or inventory upload is required
- Optional external links (documentation URLs) open only when the user chooses
- Reports and exports are written locally
- Contributors must not introduce mandatory network exfiltration of inventory data

Some collectors may invoke local CLI tools (`brew`, `docker`, `sfltool`, etc.). Those tools may have their own network behavior outside MacScope’s control. MacScope itself should not upload collected inventory.

## Responsible disclosure policy

We ask reporters to:

1. Give maintainers reasonable time to investigate and fix before public disclosure
2. Avoid privacy-invasive testing on machines or data they do not own
3. Avoid destructive proof-of-concept actions against production user data
4. Not demand ransom, coercion, or public shaming as a condition of disclosure

We commit to:

1. Treat good-faith reports seriously and respectfully
2. Credit reporters in release notes when they wish to be credited
3. Not pursue legal action against good-faith, non-destructive research conducted within this policy

Thank you for helping keep MacScope users safe.
