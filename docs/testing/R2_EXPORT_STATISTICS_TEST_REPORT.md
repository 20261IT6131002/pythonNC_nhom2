# R2 verification — FR-15 Export and FR-16 Statistics

Base is `develop@7fddd69` after PR #18. Verification used Python 3.12,
MongoDB 7.0.28, Linux Tk/Xvfb, and synthetic fixture data.

| Requirement | Evidence |
| --- | --- |
| AC-15a / TC-EXP-001 | UTF-8 Markdown, relative image link and byte-identical attachment from inline and GridFS storage. |
| AC-15b / TC-EXP-001 | Extracted Vietnamese text from a multipage PDF. The test checks embedded Unicode mapping and an image object. Installed-wheel smoke checks the packaged font and license. |
| TC-EXP-002 / LOCK-D09 | Synthetic permission failure removes staging and preserves existing files. A generated bundle name ignores note titles and original image filenames. The command denies locked or trashed records and stale versions. |
| AC-16a / TC-STAT-001 | Seeded Mongo counts include active locked notes, exclude trash and fold dangling categories into the uncategorized bucket. |
| AC-16b / TC-STAT-002 | Exact counts, percentage of active notes and an empty state with zero counts. Real Tk desktop scenario exercises both export menu options and statistics before and after saving. |
| AC-17c / R1 carryover | A locked new-note draft without a Mongo ID reuses its original operation ID. Test covers an uncommitted create and an acknowledged-data/lost-response retry. A bad passphrase preserves the draft. The desktop save uses the locked route. |

```bash
python -m ruff check .
python -m ruff format --check .
python -m compileall -q src scripts
python -m pip check
python -m pytest -q tests/unit tests/contract tests/ui
python -m pytest -q tests/integration -m 'not ui and not native_secret_store'
python -m pytest -q tests/integration/test_desktop.py --junitxml=desktop.xml
python scripts/verify_desktop_e2e.py desktop.xml
python -m pip wheel --no-deps --wheel-dir .pytest_cache/r2-wheels .
python scripts/verify_secure_storage_package.py .pytest_cache/r2-wheels
git diff --check
```

Local result: **581 unit/contract/UI**, **216 non-UI Mongo integration** and
**14 desktop Mongo** cases passed. The desktop JUnit gate verified all 14
cases without skips. Lint, formatting, compile, dependency consistency and
the installed-wheel security, draft and PDF smoke checks passed.

Export uses the selected saved revision and a user-selected existing directory.
The app writes a private staging directory and publishes the complete bundle
under a generated name. Markdown preserves the body as UTF-8. PDF uses the
bundled DejaVu Sans font for Vietnamese and does not promise coverage for
arbitrary scripts or emoji. Database records and attachments are read-only
during export. The operation does not consult or unlock encrypted data.
Statistics are a snapshot across active records and do not apply the sidebar
search filters. Local checks use synthetic data. Hosted CI and reviewer
approval are tracked on the PR.
