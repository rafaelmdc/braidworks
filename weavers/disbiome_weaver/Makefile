.PHONY: help test test-live verify lint fmt
help:
	@echo "test      - run conformance + golden + behavior tests (live E2E self-skips)"
	@echo "test-live - run the opt-in live E2E (fetches ~7 MB from the Disbiome API)"
	@echo "verify    - check the weaver conforms to weaver.spec.toml"
	@echo "lint      - ruff check"
	@echo "fmt       - ruff format"

test:
	uv run --extra test python -m pytest -q

test-live:
	BRAIDWORKS_RUN_LIVE=1 uv run --extra test python -m pytest -q tests/test_e2e_live.py

verify:
	uv run --extra test weaverkit verify --spec weaver.spec.toml --package disbiome_weaver

lint:
	uv run ruff check .

fmt:
	uv run ruff format .
