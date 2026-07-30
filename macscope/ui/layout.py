from __future__ import annotations

import secrets
from typing import Any

import streamlit as st

_ACTION_TOKENS_KEY = "_macscope_action_tokens"


def page_header(title: str, explanation: str = "") -> None:
    """Render a consistent page title and optional explanation."""
    st.title(title)
    if explanation:
        st.markdown(explanation)


def metrics_row(metrics: dict[str, Any], *, columns: int | None = None) -> None:
    """Render a horizontal row of Streamlit metrics from a label → value mapping."""
    if not metrics:
        return
    count = columns or min(len(metrics), 4)
    cols = st.columns(count)
    for index, (label, value) in enumerate(metrics.items()):
        cols[index % count].metric(label, value)


def ensure_action_token(action_id: str) -> str:
    """Return a stable one-time token for a destructive action slot."""
    bucket: dict[str, str] = st.session_state.setdefault(_ACTION_TOKENS_KEY, {})
    token = bucket.get(action_id)
    if not token:
        token = secrets.token_hex(16)
        bucket[action_id] = token
    return token


def consume_action_token(token: str) -> bool:
    """Consume a token once; return False if already used or unknown."""
    bucket: dict[str, str] = st.session_state.get(_ACTION_TOKENS_KEY, {})
    for action_id, stored in list(bucket.items()):
        if stored == token:
            del bucket[action_id]
            return True
    return False
