# Contributing to CodeScan

## Local Setup

1. Install Python 3.12+.
2. Clone the repository and create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install ruff
   ```
4. Copy the example env file:
   ```bash
   cp example.env .env
   ```

## Install Git Hooks

```bash
./scripts/install-hooks.sh
```

## Build and Test Commands

```bash
ruff check .        # Lint
pytest              # Run tests
ruff check . && pytest  # Full smoke check (used in CI and pre-commit)
```

## Local Git Setup

Run these once after cloning:

```bash
git config pull.rebase true          # rebase on pull instead of merge commit
git config core.autocrlf input       # normalize CRLF → LF on commit (macOS/Linux)
git config push.autoSetupRemote true # git push without needing -u the first time
git config init.defaultBranch main   # default branch name for new repos
```

For Windows contributors, use `core.autocrlf true` instead of `input`.

## Coding Style

- Follow PEP 8; enforced via `ruff`.
- Keep files under 200 lines — extract modules when approaching the limit.
- Use type annotations throughout.
- Write docstrings for all public functions.

## Branch Naming

| Branch prefix | Conventional Commit type | Example |
|---|---|---|
| `feature/` | `feat:` | `feature/add-ship-placement` |
| `fix/` | `fix:` | `fix/crash-on-empty-board` |
| `chore/` | `chore:` | `chore/update-dependencies` |
| `docs/` | `docs:` | `docs/update-contributing` |
| `refactor/` | `refactor:` | `refactor/extract-ai-logic` |
| `ci/` | `ci:` | `ci/add-dependabot` |

Branch names use **kebab-case**. Never commit directly to `main` — always open a PR.

## Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):
```
<type>(<optional scope>): <description>
```
Types: `feat` | `fix` | `chore` | `docs` | `style` | `refactor` | `test` | `ci` | `build` | `perf` | `revert`

The `commit-msg` hook enforces this automatically after running `./scripts/install-hooks.sh`.

## PR Checklist

- [ ] Smoke check passes (`ruff check . && pytest`)
- [ ] Manual test completed for changed functionality
- [ ] Updated docs if behavior changed
- [ ] No regressions in adjacent features
