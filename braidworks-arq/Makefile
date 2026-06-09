.PHONY: test lint worker

test:  ## Run the suite (inline; no Redis needed)
	uv run --extra test python -m pytest -q

lint:  ## Lint with ruff
	uvx ruff check src tests

worker:  ## Run a worker serving one weaver's queue: make worker WEAVER=ncbi
	BRAIDWORKS_QUEUE=weaver.$(WEAVER) BRAIDWORKS_WEAVERS=$(WEAVER) \
		uv run arq braidworks_arq.WorkerSettings
