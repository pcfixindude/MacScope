from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from config import EXPORTS_DIR, REPORTS_DIR, ensure_data_dirs
from macscope.redaction import redact_mapping, redact_text
from macscope.settings import load_settings
from utils import json_dumps


def _out_dir() -> Path:
    settings = load_settings()
    path = Path(settings.report_output_folder or REPORTS_DIR).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def export_json_snapshot(snapshot_meta: dict[str, Any], rows: list[dict[str, Any]]) -> Path:
    ensure_data_dirs()
    settings = load_settings()
    payload = {
        "snapshot": redact_mapping(snapshot_meta, settings),
        "items": [redact_mapping(r, settings) for r in rows],
    }
    path = _out_dir() / f"macscope-snapshot-{snapshot_meta.get('id', 'latest')}.json"
    path.write_text(json_dumps(payload), encoding="utf-8")
    return path


def export_csv_category(category: str, rows: Iterable[dict[str, Any]]) -> Path:
    ensure_data_dirs()
    settings = load_settings()
    path = _out_dir() / f"macscope-{category.lower().replace(' ', '-')}.csv"
    rows = [redact_mapping(dict(r), settings) for r in rows]
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames and not str(key).startswith("_"):
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fieldnames})
    return path


def export_markdown_summary(snapshot_meta: dict[str, Any], summary: dict[str, Any], actions: list[dict[str, Any]]) -> Path:
    ensure_data_dirs()
    settings = load_settings()
    snap = redact_mapping(snapshot_meta, settings)
    lines = [
        f"# MacScope Report",
        "",
        f"- Snapshot: {snap.get('id')}",
        f"- Created: {snap.get('created_at')}",
        f"- Host: {snap.get('hostname')}",
        "",
        "## Summary",
    ]
    for key, value in summary.items():
        lines.append(f"- **{key}**: {value}")
    lines.extend(["", "## Recent actions"])
    if not actions:
        lines.append("- None")
    for action in actions[:50]:
        action = redact_mapping(action, settings)
        lines.append(
            f"- {action.get('created_at')}: {action.get('action')} → {action.get('target')} ({action.get('result')})"
        )
    path = _out_dir() / f"macscope-summary-{snap.get('id', 'latest')}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def export_html_report(
    snapshot_meta: dict[str, Any],
    summary: dict[str, Any],
    sections: dict[str, list[dict[str, Any]]],
    actions: list[dict[str, Any]],
    security: list[dict[str, Any]],
    cleanup: list[dict[str, Any]],
) -> Path:
    ensure_data_dirs()
    settings = load_settings()
    snap = redact_mapping(snapshot_meta, settings)

    def esc(value: Any) -> str:
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    toc = "\n".join(f'<li><a href="#{esc(name)}">{esc(name)}</a></li>' for name in sections)
    cards = "\n".join(
        f'<div class="card"><div class="label">{esc(k)}</div><div class="value">{esc(v)}</div></div>'
        for k, v in summary.items()
    )
    body_sections = []
    for name, rows in sections.items():
        rows = [redact_mapping(r, settings) for r in rows]
        items_html = []
        for row in rows[:500]:
            detail = esc(json.dumps({k: v for k, v in row.items() if not str(k).startswith("_")}, default=str)[:2000])
            items_html.append(
                f"<details><summary>{esc(row.get('Name') or row.get('name'))} · {esc(row.get('Type') or row.get('Category') or '')}</summary>"
                f"<pre>{detail}</pre></details>"
            )
        body_sections.append(f'<section id="{esc(name)}"><h2>{esc(name)} ({len(rows)})</h2>{"".join(items_html) or "<p>None</p>"}</section>')

    actions_html = "".join(
        f"<li>{esc(redact_text(str(a.get('created_at')), settings))}: {esc(a.get('action'))} → {esc(a.get('target'))} ({esc(a.get('result'))})</li>"
        for a in actions[:100]
    )
    security_html = "".join(
        f"<li><strong>{esc(s.get('Name') or s.get('name'))}</strong>: {esc(s.get('Status') or s.get('status'))}</li>"
        for s in security
    )
    cleanup_html = "".join(
        f"<li>{esc(c.get('name'))} — {esc(c.get('reason'))} ({esc(c.get('risk'))})</li>"
        for c in cleanup[:100]
    )

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>MacScope Report</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:2rem;background:#f6f7f9;color:#1b1b1b}}
.cards{{display:flex;flex-wrap:wrap;gap:1rem}}
.card{{background:#fff;border:1px solid #ddd;border-radius:10px;padding:1rem;min-width:140px}}
.label{{font-size:12px;color:#666}} .value{{font-size:22px;font-weight:600}}
section{{background:#fff;border:1px solid #ddd;border-radius:10px;padding:1rem;margin:1rem 0}}
input{{width:100%;padding:.6rem;margin:.5rem 0 1rem;border:1px solid #ccc;border-radius:8px}}
pre{{white-space:pre-wrap;background:#f0f0f0;padding:.75rem;border-radius:8px}}
</style></head><body>
<h1>MacScope Report</h1>
<p>Snapshot #{esc(snap.get('id'))} · {esc(snap.get('created_at'))} · {esc(snap.get('hostname'))}</p>
<input id="q" placeholder="Search report…" oninput="filter()"/>
<div class="cards">{cards}</div>
<nav><h2>Contents</h2><ol>{toc}
<li><a href="#security">Security</a></li>
<li><a href="#cleanup">Cleanup candidates</a></li>
<li><a href="#actions">Action history</a></li>
</ol></nav>
{''.join(body_sections)}
<section id="security"><h2>Security summary</h2><ul>{security_html or '<li>None</li>'}</ul></section>
<section id="cleanup"><h2>Cleanup candidates</h2><ul>{cleanup_html or '<li>None</li>'}</ul></section>
<section id="actions"><h2>Action history summary</h2><ul>{actions_html or '<li>None</li>'}</ul></section>
<script>
function filter(){{
  const q=document.getElementById('q').value.toLowerCase();
  document.querySelectorAll('details').forEach(d=>{{
    d.style.display=!q||d.innerText.toLowerCase().includes(q)?'':'none';
  }});
}}
</script>
</body></html>"""
    path = _out_dir() / f"macscope-report-{snap.get('id', datetime.utcnow().strftime('%Y%m%d%H%M%S'))}.html"
    path.write_text(html, encoding="utf-8")
    return path
