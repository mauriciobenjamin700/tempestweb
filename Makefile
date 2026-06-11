VENV := .venv
PY := $(VENV)/bin/python
export VIRTUAL_ENV := $(CURDIR)/$(VENV)

.PHONY: setup lint type test test-js check fmt worktree-add worktree-list worktree-rm

setup:  ## Create venv, install deps (Python + JS test tooling)
	uv venv
	uv pip install -e ".[dev,server,cli]"
	npm install

lint:  ## ruff lint + format check (app only; _core excluded)
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .

fmt:  ## auto-format + autofix
	$(VENV)/bin/ruff format .
	$(VENV)/bin/ruff check --fix .

type:  ## mypy --strict on the app package
	$(VENV)/bin/mypy tempestweb

test:  ## pytest
	$(VENV)/bin/pytest -q

test-js:  ## pure-JS client tests via node:test + jsdom
	node --test "tests/client/**/*.test.js"

check: lint type test test-js  ## everything; the gate every phase must pass

# --- worktree tooling (one worktree per agent/phase) -------------------------
# Usage: make worktree-add ID=w1 SLUG=dom-patcher BASE=main
worktree-add:  ## create ../tempestweb-<ID> on branch feat/<ID>-<SLUG> off BASE
	git worktree add -b feat/$(ID)-$(SLUG) ../tempestweb-$(ID) $(or $(BASE),HEAD)

worktree-list:  ## list active worktrees
	git worktree list

# Usage: make worktree-rm ID=w1
worktree-rm:  ## remove a worktree (after merging/abandoning)
	git worktree remove ../tempestweb-$(ID)
