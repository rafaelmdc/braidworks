# taxon_weaver developer tasks — weaver-specific command macros live here.
# Run from this directory: the suite imports `from tests....`, so cwd matters,
# and a Makefile here naturally runs in this package's directory.

.PHONY: help test test-live ensure lint fmt

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

test:  ## Run the taxon_weaver suite (the live E2E self-skips without BRAIDWORKS_RUN_LIVE)
	uv run --extra test python -m pytest -q

test-live:  ## Run the live NCBI E2E (downloads ~70 MB, builds ~1.2 GB into the user cache)
	BRAIDWORKS_RUN_LIVE=1 uv run --extra test python -m pytest tests/test_e2e_live.py -v

ensure:  ## Build/refresh the local taxonomy DB in the user cache (taxon-weaver ensure)
	uv run taxon-weaver ensure

lint:  ## Lint this package with ruff
	uvx ruff check src tests

fmt:  ## Auto-format this package with ruff
	uvx ruff format src tests
