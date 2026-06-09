.PHONY: test lint worker

test:  ## Run the suite (eager mode; no Redis needed)
	uv run --extra test python -m pytest -q

lint:  ## Lint with ruff
	uvx ruff check src tests

worker:  ## Run a worker serving one weaver's queue: make worker WEAVER=ncbi
	uv run celery -A braidworks_celery.app worker -Q weaver.$(WEAVER) -l info
