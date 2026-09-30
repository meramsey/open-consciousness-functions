PY?=python3
OCF:=$(PY) scripts/ocf.py

.PHONY: help test validate indexes check lint clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

test: ## Run the pytest suite
	$(PY) -m pytest

validate: ## Validate all functions, proposals, and audio manifests
	$(OCF) validate --all

indexes: ## Regenerate all generated indexes
	$(OCF) build-index

lint: ## Lint Python (ruff), Markdown, and internal links
	ruff check scripts tests
	ruff format --check scripts tests
	$(PY) scripts/tools/check_markdown_links.py
	-command -v markdownlint >/dev/null && markdownlint . || echo "markdownlint not installed; skipping"

check: ## Full check: validate + refresh indexes + verify freshness
	$(OCF) validate --all
	$(OCF) build-index --check

doctor: ## Run the environment doctor
	$(OCF) doctor

clean: ## Remove generated caches
	rm -rf .pytest_cache .ruff_cache **/__pycache__