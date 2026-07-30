## Summary

<!-- What changed and why? Keep it concise. -->

## Related issue

<!-- e.g. Fixes #123 — or N/A -->

## Testing performed

- [ ] `python -m compileall -q -x '.venv|.venv312|dist' .`
- [ ] `pytest -q`
- [ ] Manual Streamlit smoke (if UI touched)
- [ ] N/A — docs-only / no runtime impact

Notes:

<!-- Commands, platforms, or special setup used -->

## Screenshots

<!-- Required for UI-visible changes; otherwise write N/A -->

## Checklist

- [ ] Change preserves local-only privacy model
- [ ] No destructive behavior added without preview/confirmation/settings gates
- [ ] Reused existing collectors/models/pages where practical (no duplicates)
- [ ] Migrations are additive / backward compatible (or explicitly discussed)
- [ ] Docs/Changelog updated when user-facing
- [ ] No secrets, databases, logs, or `dist/` artifacts included
- [ ] Follows [CONTRIBUTING.md](../CONTRIBUTING.md) and [STYLE_GUIDE.md](../STYLE_GUIDE.md)
