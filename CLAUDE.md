# CLAUDE.md — CodeScan

## Project Overview

CodeScan is a Python static code analyzer that parses Python source files using the AST module, extracts structural and call-graph information, and stores it in a Neo4j graph database. It also exposes an MCP (Model Context Protocol) server for Cursor IDE integration, enabling LLM-driven codebase exploration.

- **Language / Runtime**: Python 3.12
- **Framework**: Standard library (ast), FastMCP, Neo4j Python driver
- **Architecture**: Single-responsibility modules — analyzer, MCP server, scanner CLI
- **Package / Namespace**: `codescan_lib`

---

## Required Skills — ALWAYS Invoke These

These skills **must** be invoked when the relevant situation arises. Never skip them.

| Situation | Skill |
|-----------|-------|
| Before any new feature or screen | `superpowers:brainstorming` |
| Planning multi-step changes | `superpowers:writing-plans` |
| Writing or fixing core logic | `superpowers:test-driven-development` |
| First sign of a bug or failure | `superpowers:systematic-debugging` |
| Before completing a feature branch | `superpowers:requesting-code-review` |
| Before claiming any task done | `superpowers:verification-before-completion` |
| Working on UI / frontend | `frontend-design:frontend-design` |
| After implementing — reviewing quality | `simplify` |

---

## Architecture

```
codescan/
├── codescan_lib/         <- Core library (analyzer, stats, constants)
├── codescan_mcp_server.py <- MCP server exposing graph query tools
├── scanner.py            <- CLI entry point for scanning codebases
├── docker-compose.yaml   <- Neo4j container setup
├── tests/                <- Pytest test suite
├── docs/                 <- GitHub Pages site
└── scripts/              <- Utility scripts (hooks installer, repo setup)
```

### Layer Rules
- `codescan_lib` must not import from `codescan_mcp_server.py` or `scanner.py`
- `scanner.py` and `codescan_mcp_server.py` import from `codescan_lib` — not each other
- No circular imports

---

## Coding Conventions

- All functions use type annotations
- Functions are pure where possible — no hidden side effects
- No hardcoded strings — use constants from `codescan_lib`
- Follow PEP 8; enforced via `ruff`
- Maximum 200 lines per file — extract modules when approaching the limit

---

## Engineering Principles

### File Size
- **200-line maximum per file** — extract a class, function, or module when approaching the limit

### DRY · SOLID · KISS · YAGNI
- Extract shared logic into named utilities; never copy-paste
- Single Responsibility: one class/function does one thing
- Don't add features not yet needed
- Delete dead code immediately

### TDD
- Write the failing test first, make it pass, then refactor
- Test names describe behaviour: `"should reject duplicate email"`
- One assertion per test — keep tests focused and readable

### Commit hygiene
- Follow Conventional Commits: `feat: ...` / `fix: ...` / `chore: ...`
- The `commit-msg` hook enforces this automatically

---

## Build Commands

```bash
ruff check .                # Lint / type-check
pytest                      # Run tests
ruff check . && pytest      # Full smoke check (used in CI and pre-commit)
```

---

## Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | This file — project conventions and session startup |
| `version.txt` | Semantic version (MAJOR.MINOR.PATCH) |
| `.github/workflows/` | CI, release, Pages, and container automation |
| `.githooks/` | Pre-commit and commit-msg hooks |
| `scripts/install-hooks.sh` | One-time hook installer |
| `scripts/setup-repo.sh` | One-time branch protection + repo settings |

---

## Starting a New Session

1. Read this file
2. Run `ruff check . && pytest` to confirm everything passes
3. Invoke `superpowers:brainstorming` before touching any feature
4. Follow the Required Skills table — every skill is mandatory, not optional
