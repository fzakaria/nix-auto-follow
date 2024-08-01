.PHONY: help
help:             ## Show the help.
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@fgrep "##" Makefile | fgrep -v fgrep


.PHONY: show
show:             ## Show the current environment.
	@echo "Current environment:"
	@echo "Running using $(VIRTUAL_ENV)"
	@$(VIRTUAL_ENV)/bin/python -V
	@$(VIRTUAL_ENV)/bin/python -m site

.PHONY: fmt
fmt:              ## Format code using black & isort.
	isort src/ tests/
	black src/ tests/

.PHONY: lint
lint:             ## Run pep8, black, mypy linters.
	flake8 src/ tests/
	isort --check src/ tests/
	black --check src/ tests/
	pyright
	mypy --strict --install-types --non-interactive src tests

.PHONY: test
test:             ## Run pytest primarily.
	pytest