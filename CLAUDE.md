# CLAUDE.md — CodeScan

CodeScan parses Python source with `ast`, stores structure and the call graph in Neo4j, and serves the
graph to Cursor through an MCP server. Python 3.12, package `codescan_lib`.

## Check before and after a change

```bash
bash scripts/gate.sh                 # ruff, then pytest against the local Neo4j on port 7600
bash scripts/gate.sh tests/test_x.py # ruff, then only those tests
```

The tests need the Neo4j container running (`codescan-neo4j-dev`, or `docker compose up -d`).

## Skills

Invoke the skill when its situation arises:

| Situation | Skill |
|-----------|-------|
| Before any new feature or screen | `superpowers:brainstorming` |
| Planning multi-step changes | `superpowers:writing-plans` |
| Writing or fixing core logic | `superpowers:test-driven-development` |
| First sign of a bug or failure | `superpowers:systematic-debugging` |
| Before completing a feature branch | `superpowers:requesting-code-review` |
| Before claiming any task done | `superpowers:verification-before-completion` |
| Working on UI / frontend | `frontend-design:frontend-design` |
| After implementing, reviewing quality | `simplify` |

## Layout and layers

```
codescan_lib/            core library: analyzer, MCP tools (mcp_tools/), stats, constants
codescan_mcp_server.py   MCP server exposing the graph query tools
scanner.py               CLI that scans a codebase into Neo4j
docker-compose.yaml      Neo4j container
tests/                   pytest suite
docs/                    GitHub Pages site and design notes; docs/lean/ holds graph-loop specs
scripts/                 hook installer, repo setup
```

- `codescan_lib` never imports `codescan_mcp_server.py` or `scanner.py`; those two import from
  `codescan_lib`, not from each other. No circular imports.

## Code

- At most 200 lines per file; extract a class, function or module before reaching it.
- Type annotations on every function. Pure functions where possible.
- No hardcoded strings: use constants from `codescan_lib`.
- DRY, single responsibility, YAGNI; delete dead code.
- Tests first. Test names describe behaviour (`should reject duplicate email`), one assertion per test.
- Conventional Commits (`feat:`, `fix:`, `chore:`); the `commit-msg` hook enforces them.

## Key files

`version.txt` holds the semantic version. `.github/workflows/` runs CI, release, Pages and the container
build. `.githooks/` holds the hooks; `scripts/install-hooks.sh` installs them once, and
`scripts/setup-repo.sh` sets branch protection once.

## Autonomous builds (graph-loop)

graph-loop builds features from the specs in `docs/lean/`, one per pull request, with the profile in
`profile-python-neo4j.md` (its suite is `bash scripts/gate.sh`). When working as graph-loop's builder:

- The spec is the settled brainstorm and plan: skip `superpowers:brainstorming` and
  `superpowers:writing-plans`, and never stop to ask a person. Questions go in the pull request.
- The other rules in this file still apply: tests first, the 200-line limit, constants, layer rules.
