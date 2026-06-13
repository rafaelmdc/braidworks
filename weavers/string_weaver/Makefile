.PHONY: help test verify lint fmt
help:
	@echo "test    - run conformance + golden tests"
	@echo "verify  - check the weaver conforms to weaver.spec.toml"
	@echo "lint    - ruff check"
	@echo "fmt     - ruff format"

test:
	uv run --extra test python -m pytest -q

test-live:
	BRAIDWORKS_RUN_LIVE=1 uv run --extra test python -m pytest tests/test_e2e_live.py -v

verify:
	uv run --extra test weaverkit verify --spec weaver.spec.toml --package string_weaver

lint:
	uv run ruff check .

fmt:
	uv run ruff format .
