# Contributing

This project uses a branch-then-PR workflow.

## Local Gate
Before pushing your branch, you must pass the local gate. Run the following from the repository root:

```sh
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/ruff format . && .venv/bin/ruff check . && \
  .venv/bin/mypy --strict notebook_helpers.py && .venv/bin/pytest
```

## Release Steps
1. Update `CHANGELOG.md`: move `[Unreleased]` to `[x.y.z] - YYYY-MM-DD`.
2. Commit and push.
3. Tag the release: `git tag -a vx.y.z -m "vx.y.z" && git push origin vx.y.z`.
4. Create the GitHub release: `gh release create vx.y.z --generate-notes`.
