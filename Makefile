# Braidworks developer tasks.
# Tests are per-package and the working directory matters (taxonweaver tests
# import `from tests....`), so each target cd's into the right package.

.PHONY: help sync test test-core test-weaver lint fmt clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

sync:  ## Create/refresh the workspace venv with all extras
	uv sync --all-extras

test: test-core test-weaver  ## Run every package's test suite

test-core:  ## Run the braidworks-core suite
	cd braidworks-core && uv run --extra test python -m pytest -q

test-weaver:  ## Run the taxonweaver suite (delegates to taxonweaver/Makefile)
	$(MAKE) -C taxonweaver test

# Lint every package (incl. the migrated taxonomy_resolver/taxonomy_tools) and tests.
LINT_PATHS = braidworks-core/src braidworks-core/tests taxonweaver/src taxonweaver/tests

lint:  ## Lint all packages and tests with ruff
	uvx ruff check $(LINT_PATHS)

fmt:  ## Auto-format with ruff
	uvx ruff format $(LINT_PATHS)

clean:  ## Remove caches and build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
