.PHONY: help test verify lint fmt
help:
	@echo "test    - run conformance + golden tests"
	@echo "verify  - check the weaver conforms to weaver.spec.toml"
	@echo "lint    - ruff check"
	@echo "fmt     - ruff format"

test:
	uv run --extra test python -m pytest -q

verify:
	uv run --extra test weaverkit verify --spec weaver.spec.toml --package example_weaver

lint:
	uvx ruff==0.16.10 check .

fmt:
	uvx ruff==0.16.10 format .
