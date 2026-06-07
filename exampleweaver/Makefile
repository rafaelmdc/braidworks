.PHONY: help test verify lint fmt
help:
	@echo "test    - run conformance + golden tests"
	@echo "verify  - check the weaver conforms to weaver.spec.toml"
	@echo "lint    - ruff check"
	@echo "fmt     - ruff format"

test:
	uv run --extra test python -m pytest -q

verify:
	uv run --extra test weaverkit verify --spec weaver.spec.toml --package exampleweaver

lint:
	uv run ruff check .

fmt:
	uv run ruff format .
