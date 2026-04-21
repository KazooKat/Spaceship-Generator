# Release Guide

This project uses tag-driven releases. Pushing a `vX.Y.Z` tag to `main`
triggers `.github/workflows/release.yml`, which builds the sdist + wheel,
publishes to PyPI via Trusted Publishing (OIDC), and creates a GitHub
Release with auto-generated notes.

## 1. Manual release checklist

Follow these steps from a clean `main` checkout.

1. **Sync and verify a clean tree**
   ```bash
   git checkout main
   git pull --ff-only
   git status                 # must be clean
   ```

2. **Run the full test suite locally**
   ```bash
   python -m pip install -e ".[dev]"
   ruff check .
   pytest -q
   ```

3. **Bump the version**

   Pick a new version following [SemVer](https://semver.org/):
   - `MAJOR` — breaking API changes
   - `MINOR` — new features, backward compatible
   - `PATCH` — bug fixes only

   Update both of these to the same value:
   - `pyproject.toml` → `[project] version = "X.Y.Z"`
   - `src/spaceship_generator/__init__.py` → `__version__ = "X.Y.Z"` (add it
     if it does not exist yet)

4. **Update the changelog**

   Edit `docs/CHANGELOG.md`:
   - Rename the `## [Unreleased]` heading to `## [X.Y.Z] - YYYY-MM-DD`.
   - Add a new empty `## [Unreleased]` section at the top.
   - Group entries under `Added`, `Changed`, `Fixed`, `Removed`, `Security`.

5. **Commit the bump**
   ```bash
   git add pyproject.toml src/spaceship_generator/__init__.py docs/CHANGELOG.md
   git commit -m "chore(release): vX.Y.Z"
   ```

6. **Tag and push**
   ```bash
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin main
   git push origin vX.Y.Z
   ```

   The tag push fires the `Release` workflow. Watch it at
   `https://github.com/KazooKat/Spaceship-Generator/actions`.

7. **Verify the release**
   - The workflow's `build` job produces `dist/*.tar.gz` and `dist/*.whl`.
   - The `publish-pypi` job publishes to
     <https://pypi.org/project/spaceship-generator/>.
   - The `github-release` job attaches the wheel + sdist to
     <https://github.com/KazooKat/Spaceship-Generator/releases>.

## 2. Configure PyPI Trusted Publishing (one time)

Trusted Publishing uses OIDC — no API tokens stored in GitHub.

1. Log in to [PyPI](https://pypi.org/) as a maintainer of
   `spaceship-generator`.
2. Go to **Your projects → spaceship-generator → Publishing**, or for a
   first-time release, **Account settings → Publishing → Add a pending
   publisher**.
3. Fill in:
   - **PyPI project name**: `spaceship-generator`
   - **Owner**: `KazooKat`
   - **Repository name**: `Spaceship-Generator`
   - **Workflow filename**: `release.yml`
   - **Environment name**: `pypi`
4. Save. Nothing else needs to happen in GitHub — the workflow's
   `publish-pypi` job already declares `environment: pypi` and
   `permissions: id-token: write`.
5. (Optional) Create a matching trusted publisher on
   [TestPyPI](https://test.pypi.org/) for dry runs, and uncomment the
   `repository-url` line in `.github/workflows/release.yml`.

Docs: <https://docs.pypi.org/trusted-publishers/>

## 3. Cutting a hotfix

Use when a bug in the latest release needs a patch without shipping
unfinished `main` work.

1. **Branch from the release tag**
   ```bash
   git fetch --tags
   git checkout -b hotfix/X.Y.(Z+1) vX.Y.Z
   ```

2. **Fix the bug and add a regression test**
   - Keep the diff minimal.
   - Run `ruff check .` and `pytest -q` locally.

3. **Bump the patch version** in `pyproject.toml` and `__init__.py`, and
   add a `## [X.Y.(Z+1)] - YYYY-MM-DD` section to `docs/CHANGELOG.md`
   under `Fixed`.

4. **Open a PR to `main`** titled `hotfix: vX.Y.(Z+1) — <short reason>`.
   Once CI is green, merge with a merge commit (not squash) so the
   hotfix branch history is preserved.

5. **Tag and push from `main`** after the merge:
   ```bash
   git checkout main && git pull --ff-only
   git tag -a vX.Y.(Z+1) -m "Hotfix vX.Y.(Z+1)"
   git push origin vX.Y.(Z+1)
   ```

6. **Delete the hotfix branch** once the release workflow is green:
   ```bash
   git branch -d hotfix/X.Y.(Z+1)
   git push origin --delete hotfix/X.Y.(Z+1)
   ```

## 4. Troubleshooting

- **`twine check` fails in `build` job** — almost always a malformed
  `README.md` or `pyproject.toml` metadata. Fix locally with
  `python -m build && python -m twine check dist/*`.
- **`publish-pypi` fails with `invalid-publisher`** — the pending
  publisher on PyPI does not match the workflow. Double-check repo
  owner, repo name, workflow filename (`release.yml`), and environment
  name (`pypi`).
- **Release job succeeds but PyPI shows nothing** — the version in
  `pyproject.toml` is already published. PyPI never allows overwriting
  an existing version; bump and re-tag.
- **GitHub Release missing assets** — check the `github-release` job
  logs; the wheel/sdist filenames must match the `files:` glob.
