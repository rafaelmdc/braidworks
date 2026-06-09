# Braidworks developer tasks.
# Tests are per-package and the working directory matters (taxon_weaver tests
# import `from tests....`), so each target cd's into the right package.

.PHONY: help sync test test-core test-weaver test-kit test-example new-weaver verify-weaver index lint fmt clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

sync:  ## Create/refresh the workspace venv with all extras
	uv sync --all-extras

test: test-core test-weaver test-kit test-example test-bacdive  ## Run every package's test suite

test-core:  ## Run the braidworks-core suite
	cd braidworks-core && uv run --extra test python -m pytest -q

test-weaver:  ## Run the taxon_weaver suite (delegates to weavers/taxon_weaver/Makefile)
	$(MAKE) -C weavers/taxon_weaver test

test-kit:  ## Run the weaverkit suite (delegates to weaverkit/Makefile)
	$(MAKE) -C weaverkit test

test-example:  ## Run the example_weaver reference suite (delegates to its Makefile)
	$(MAKE) -C weavers/example_weaver test

test-bacdive:  ## Run the bacdive_weaver suite (delegates to its Makefile)
	$(MAKE) -C weavers/bacdive_weaver test

new-weaver:  ## Scaffold a weaver: make new-weaver SPEC=path/weaver.spec.toml DEST=weavers/foo_weaver
	$(MAKE) -C weaverkit new SPEC=$(abspath $(SPEC)) DEST=$(abspath $(DEST))

verify-weaver:  ## Verify a weaver: make verify-weaver SPEC=path PACKAGE=foo_weaver
	$(MAKE) -C weaverkit verify SPEC=$(abspath $(SPEC)) PACKAGE=$(PACKAGE)

index:  ## Build the cross-weaver index -> docs/weavers-index.tsv + docs/keys-index.md
	uv run weaverkit index --root . --out docs/weavers-index.tsv --keys-out docs/keys-index.md

# Lint every package (incl. the migrated taxonomy_resolver/taxonomy_tools) and tests.
LINT_PATHS = braidworks-core/src braidworks-core/tests weavers/taxon_weaver/src weavers/taxon_weaver/tests \
	weaverkit/src weaverkit/tests weavers/example_weaver/src weavers/example_weaver/tests \
	weavers/bacdive_weaver/src weavers/bacdive_weaver/tests

lint:  ## Lint all packages and tests with ruff
	uvx ruff check $(LINT_PATHS)

fmt:  ## Auto-format with ruff
	uvx ruff format $(LINT_PATHS)

clean:  ## Remove caches and build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
