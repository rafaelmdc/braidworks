# Braidworks developer tasks.
# Tests are per-package and the working directory matters (ncbi_weaver tests
# import `from tests....`), so each target cd's into the right package.
#
# Weavers are auto-discovered from weavers/* (matching the `members = ["weavers/*"]`
# workspace glob), so a newly scaffolded weaver is tested and linted with no edit here.

.PHONY: help sync test test-core test-kit test-weavers new-weaver verify-weaver index view serve lint fmt clean tags tags-check

# Every weaver package directory (each has its own Makefile + src/ + tests/).
WEAVER_DIRS := $(sort $(dir $(wildcard weavers/*/Makefile)))

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

sync:  ## Create/refresh the workspace venv with all extras
	uv sync --all-extras

test: test-core test-kit test-arq test-weavers  ## Run every package's test suite

test-core:  ## Run the braidworks-core suite
	cd braidworks-core && uv run --extra test python -m pytest -q

test-kit:  ## Run the weaverkit suite (delegates to weaverkit/Makefile)
	$(MAKE) -C weaverkit test

test-arq:  ## Run the braidworks-arq suite (inline; no Redis needed)
	cd braidworks-arq && uv run --extra test python -m pytest -q

test-weavers:  ## Run every weaver suite under weavers/* (auto-discovered)
	@for d in $(WEAVER_DIRS); do echo "== $$d =="; $(MAKE) -C $$d test || exit $$?; done

new-weaver:  ## Scaffold a weaver: make new-weaver SPEC=path/weaver.spec.toml DEST=weavers/foo_weaver
	$(MAKE) -C weaverkit new SPEC=$(abspath $(SPEC)) DEST=$(abspath $(DEST))

verify-weaver:  ## Verify a weaver: make verify-weaver SPEC=path PACKAGE=foo_weaver
	$(MAKE) -C weaverkit verify SPEC=$(abspath $(SPEC)) PACKAGE=$(PACKAGE)

index:  ## Build the cross-weaver index -> docs/weavers-index.tsv + docs/keys-index.md
	uv run weaverkit index --root . --out docs/weavers-index.tsv --keys-out docs/keys-index.md

# Where `make view` writes the interactive network view; override with VIEW_OUT=path.html.
VIEW_OUT ?= docs/braidworks-network.html
view:  ## Render the weaver-network view -> $(VIEW_OUT) (VIEW_OUT=.. to override; FROM=.. TO=.. adds a braid path)
	uv run weaverkit view --out $(VIEW_OUT) \
		$(if $(FROM),$(foreach k,$(FROM),--from $(k))) $(if $(TO),$(foreach k,$(TO),--to $(k)))

serve:  ## Run the interactive GUI (weaverkit serve; needs the [serve] extra: fastapi+uvicorn)
	uv run --with fastapi --with uvicorn weaverkit serve $(if $(PORT),--port $(PORT))

# Lint every package and its tests. Weaver src/tests are derived from WEAVER_DIRS,
# so a new weaver is linted automatically.
WEAVER_LINT_PATHS := $(foreach d,$(WEAVER_DIRS),$(d)src $(d)tests)
LINT_PATHS = braidworks-core/src braidworks-core/tests weaverkit/src weaverkit/tests \
	braidworks-arq/src braidworks-arq/tests \
	$(WEAVER_LINT_PATHS)

lint:  ## Lint all packages and tests with ruff
	uvx ruff check $(LINT_PATHS)

fmt:  ## Auto-format with ruff
	uvx ruff format $(LINT_PATHS)

clean:  ## Remove caches and build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache

tags-check:  ## List release tags missing for current package versions (nonzero if any)
	@python tools/release_tags.py missing

tags:  ## Create + push any missing <name>-v<version> release tags (CI does this on merge)
	python tools/release_tags.py create
