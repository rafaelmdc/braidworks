# Braidworks developer tasks.
# Tests are per-package and the working directory matters (taxonweaver tests
# import `from tests....`), so each target cd's into the right package.

.PHONY: help sync test test-core test-weaver test-kit test-example new-weaver verify-weaver index lint fmt clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

sync:  ## Create/refresh the workspace venv with all extras
	uv sync --all-extras

test: test-core test-weaver test-kit test-example  ## Run every package's test suite

test-core:  ## Run the braidworks-core suite
	cd braidworks-core && uv run --extra test python -m pytest -q

test-weaver:  ## Run the taxonweaver suite (delegates to taxonweaver/Makefile)
	$(MAKE) -C taxonweaver test

test-kit:  ## Run the weaverkit suite (delegates to weaverkit/Makefile)
	$(MAKE) -C weaverkit test

test-example:  ## Run the exampleweaver reference suite (delegates to its Makefile)
	$(MAKE) -C exampleweaver test

new-weaver:  ## Scaffold a weaver: make new-weaver SPEC=path/weaver.spec.toml DEST=fooweaver
	$(MAKE) -C weaverkit new SPEC=$(abspath $(SPEC)) DEST=$(abspath $(DEST))

verify-weaver:  ## Verify a weaver: make verify-weaver SPEC=path PACKAGE=fooweaver
	$(MAKE) -C weaverkit verify SPEC=$(abspath $(SPEC)) PACKAGE=$(PACKAGE)

index:  ## Build the cross-weaver key index -> docs/weavers-index.tsv
	uv run weaverkit index --root . --out docs/weavers-index.tsv

# Lint every package (incl. the migrated taxonomy_resolver/taxonomy_tools) and tests.
LINT_PATHS = braidworks-core/src braidworks-core/tests taxonweaver/src taxonweaver/tests \
	weaverkit/src weaverkit/tests exampleweaver/src exampleweaver/tests

lint:  ## Lint all packages and tests with ruff
	uvx ruff check $(LINT_PATHS)

fmt:  ## Auto-format with ruff
	uvx ruff format $(LINT_PATHS)

clean:  ## Remove caches and build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
