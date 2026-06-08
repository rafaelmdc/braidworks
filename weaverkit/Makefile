# weaverkit developer tasks — the weaver guardrail toolkit.
# Run from this directory; the suite imports `from tests....`, so cwd matters.

.PHONY: help test lint fmt new verify

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

test:  ## Run the weaverkit suite (spec, conformance, scaffold, CLI)
	uv run --extra test python -m pytest -q

new:  ## Scaffold a weaver: make new SPEC=path/weaver.spec.toml DEST=fooweaver
	uv run weaverkit new --spec "$(SPEC)" --dest "$(DEST)"

verify:  ## Verify a weaver against its spec: make verify SPEC=path PACKAGE=fooweaver
	uv run weaverkit verify --spec "$(SPEC)" $(if $(PACKAGE),--package "$(PACKAGE)",)

lint:  ## Lint this package with ruff
	uvx ruff check src tests

fmt:  ## Auto-format this package with ruff
	uvx ruff format src tests
