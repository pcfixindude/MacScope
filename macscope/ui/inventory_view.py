from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st

from identifier import summary_flags
from snapshot import row_as_dict
from utils import format_bytes, json_loads


FILTER_LABELS = [
    "Running",
    "Starts automatically",
    "Third-party",
    "Apple",
    "Safe",
    "Caution",
    "Protected",
    "Unknown",
    "Orphaned",
]

FILTER_KEY = {
    "Running": "running",
    "Starts automatically": "starts_automatically",
    "Third-party": "third_party",
    "Apple": "apple",
    "Safe": "safe",
    "Caution": "caution",
    "Protected": "protected",
    "Unknown": "unknown",
    "Orphaned": "orphaned",
}

SUMMARY_COLUMNS = [
    "Name",
    "Type",
    "Status",
    "Risk",
    "Classification",
    "Running",
    "Startup",
    "Version",
    "Publisher",
    "Path",
]


def rows_to_records(rows: list[Any]) -> list[dict[str, Any]]:
    records = []
    for row in rows:
        record = row_as_dict(row)
        # Attach filter flags using a lightweight shim
        class _Shim:
            pass

        shim = _Shim()
        for attr in (
            "classification",
            "risk",
            "running_state",
            "status",
            "startup_state",
            "category",
            "protected",
            "details",
        ):
            setattr(shim, attr, getattr(row, attr, None) if attr != "details" else json_loads(row.details_json))
        record["_flags"] = summary_flags(shim)
        records.append(record)
    return records


def apply_filters(records: list[dict[str, Any]], selected: list[str], query: str) -> list[dict[str, Any]]:
    filtered = records
    if selected:
        keys = [FILTER_KEY[label] for label in selected if label in FILTER_KEY]
        filtered = [r for r in filtered if any(r.get("_flags", {}).get(k) for k in keys)]
    if query:
        q = query.lower()
        filtered = [
            r
            for r in filtered
            if any(
                q in str(r.get(col, "")).lower()
                for col in (
                    "Name",
                    "Label",
                    "Bundle ID",
                    "Stable ID",
                    "Type",
                    "Subtype",
                    "Status",
                    "Path",
                    "Executable",
                    "Publisher",
                    "Classification",
                    "Explanation",
                    "Related",
                    "Source",
                    "Removal guidance",
                )
            )
        ]
    return filtered


def render_inventory(
    title: str,
    rows: list[Any],
    *,
    categories: list[str] | None = None,
    snapshot_label: str = "",
    key_prefix: str = "inv",
    show_header: bool = True,
) -> list[dict[str, Any]]:
    if show_header and title:
        st.title(title)
    if categories:
        rows = [r for r in rows if r.category in categories]

    records = rows_to_records(rows)
    query = st.text_input("Search", placeholder="Name, label, bundle id, path, publisher…", key=f"{key_prefix}_search")
    selected_filters = st.multiselect("Filters", FILTER_LABELS, key=f"{key_prefix}_filters")
    filtered = apply_filters(records, selected_filters, query)

    st.caption(f"{len(filtered):,} matching items" + (f" · {snapshot_label}" if snapshot_label else ""))

    if not filtered:
        st.info("No items match the current search and filters.")
        return filtered

    summary = pd.DataFrame([{c: r.get(c) for c in SUMMARY_COLUMNS} for r in filtered])
    sort_col = st.selectbox("Sort by", SUMMARY_COLUMNS, index=0, key=f"{key_prefix}_sort")
    ascending = st.checkbox("Ascending", value=True, key=f"{key_prefix}_asc")
    summary = summary.sort_values(by=sort_col, ascending=ascending, kind="mergesort")
    st.dataframe(summary, use_container_width=True, hide_index=True, height=360)

    labels = [
        f"{r.get('Name')} · {r.get('Type') or r.get('Category')} · {r.get('Path') or r.get('Label') or r.get('ID')}"
        for r in filtered
    ]
    choice = st.selectbox("Inspect item", labels, key=f"{key_prefix}_inspect")
    selected = filtered[labels.index(choice)]
    render_detail_panel(selected)
    return filtered


def render_detail_panel(record: dict[str, Any]) -> None:
    st.subheader("Item details")

    disk = record.get("Disk")
    disk_display = format_bytes(disk) if disk is not None else None
    confidence = record.get("Confidence")
    confidence_display = f"{confidence:.0%}" if isinstance(confidence, (int, float)) else confidence
    orphan = record.get("Orphan")
    orphan_display = "Yes" if orphan else ("No" if orphan is not None else None)

    fields = [
        ("Name", record.get("Name")),
        ("Stable ID", record.get("Stable ID")),
        ("Label", record.get("Label")),
        ("Bundle ID", record.get("Bundle ID")),
        ("Category", record.get("Category")),
        ("Type", record.get("Type")),
        ("Subtype", record.get("Subtype")),
        ("Status", record.get("Status")),
        ("Enabled", record.get("Enabled")),
        ("Path", record.get("Path")),
        ("Executable path", record.get("Executable")),
        ("Configuration path", record.get("Configuration path")),
        ("Version", record.get("Version")),
        ("Build", record.get("Build")),
        ("Publisher / signing identity", record.get("Publisher")),
        ("Signing identity", record.get("Signing")),
        ("Team ID", record.get("Team ID")),
        ("Installation source", record.get("Source")),
        ("Running state", record.get("Running")),
        ("Startup state", record.get("Startup")),
        ("PID", record.get("PID")),
        ("Parent process", record.get("Parent")),
        ("Owner", record.get("Owner")),
        ("CPU %", record.get("CPU %")),
        ("Memory %", record.get("Memory %")),
        ("Disk usage", disk_display),
        ("Network ports", record.get("Ports")),
        ("Risk classification", record.get("Risk")),
        ("Identification", record.get("Classification")),
        ("Confidence", confidence_display),
        ("Orphaned", orphan_display),
        ("Explanation", record.get("Explanation")),
        ("Removal guidance", record.get("Removal guidance")),
        ("Related application", record.get("Related")),
        ("Related package", record.get("Related package")),
        ("Related service", record.get("Related service")),
        ("Available actions", record.get("Actions")),
        ("Protected", record.get("Protected")),
    ]

    row_obj = record.get("_row")
    if row_obj is not None:
        command = getattr(row_obj, "command", None)
        if command:
            fields.append(("Command", command))
        for attr, label in (
            ("technical_name", "Technical name"),
            ("install_date", "Install date"),
            ("modification_date", "Modification date"),
            ("configuration_path", "Configuration path"),
        ):
            value = getattr(row_obj, attr, None)
            if value and not any(existing_label == label for existing_label, _ in fields):
                fields.append((label, value))

    for label, value in fields:
        if value is None or value == "":
            continue
        st.markdown(f"**{label}:** {value}")

    details = record.get("Details") or {}
    if details:
        with st.expander("Raw collector details", expanded=False):
            st.json(details)
