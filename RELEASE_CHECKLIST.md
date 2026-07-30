# Release Checklist

Use this checklist for every MacScope version bump and GitHub Release.

For 4.0.x specifically, also verify Workspaces start/stop only assigned members, Assistant evidence panels render, and `macscope/data/knowledge_pack.json` is included in the ZIP.

## 1. Preflight

- [ ] Working tree is clean except intentional release changes
- [ ] You are on `main` (or the agreed release branch)
- [ ] `git pull` / remote is up to date
- [ ] No local inventory DB/logs staged for commit

## 2. Quality gates

- [ ] Compile check:

  ```bash
  source .venv/bin/activate
  python -m compileall -q -x '.venv|.venv312|dist' .
  ```

- [ ] Full test suite:

  ```bash
  pytest -q
  ```

- [ ] Optional lint (advisory until fully clean):

  ```bash
  ruff check .
  ```

- [ ] Smoke test Streamlit:

  ```bash
  python -m streamlit run app.py --server.headless true --server.port 8599
  ```

  Confirm HTTP 200 and core pages load (Dashboard, Applications, Settings).

## 3. Version & docs

- [ ] Update `VERSION` (single-line semver, e.g. `3.0.1`)
- [ ] Update `config.APP_VERSION` and `macscope/__version__` if they are not derived automatically
- [ ] Update `CHANGELOG.md` (Keep a Changelog): move `[Unreleased]` notes into the new version section with date
- [ ] Verify `README.md` version badge / version mentions
- [ ] Update `ROADMAP.md` if major features shipped
- [ ] Confirm `SECURITY.md` supported-versions table if support policy changes

## 4. Build artifacts

- [ ] Build release ZIP:

  ```bash
  ./scripts/build_release.sh
  ```

- [ ] Confirm artifact path: `dist/MacScope-<VERSION>.zip`
- [ ] Spot-check ZIP contents (no `.venv`, no `*.db`, no secrets, includes `VERSION` + `README.md` + `MacScope.command`)

## 5. Git tagging

- [ ] Commit release documentation/version changes
- [ ] Tag annotated release:

  ```bash
  git tag -a "v<VERSION>" -m "MacScope <VERSION>"
  git push origin main
  git push origin "v<VERSION>"
  ```

## 6. GitHub Release

- [ ] Create GitHub Release for `v<VERSION>` (do **not** rely on auto-publish workflows)
- [ ] Paste changelog summary into the release notes
- [ ] Upload `dist/MacScope-<VERSION>.zip`
- [ ] Verify release asset download works
- [ ] Confirm Actions CI is green on the tagged commit when available

## 7. Post-release

- [ ] Smoke the downloaded ZIP on a clean shell (optional but recommended)
- [ ] Open `[Unreleased]` section in `CHANGELOG.md` for future work
- [ ] Close/milestone related issues
- [ ] Announce briefly in Discussions if appropriate

## Safety reminders

- Never publish `~/Library/Application Support/MacScope/` data
- Never include local `.env`, credentials, or machine inventory in the ZIP
- Do not enable automatic release publishing that uploads secrets
