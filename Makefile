# Ledger task shortcuts.
#
# Logic lives in tasks.py so it also runs on Windows, where make is
# usually unavailable: `python tasks.py lint` == `make lint`.
#
#   make test PYTHON=.venv/bin/python        (Linux/macOS)
#   make test PYTHON=.venv/Scripts/python    (Windows)

PYTHON ?= python

.PHONY: install lint format test build-ui run db-init backup

install:
	$(PYTHON) tasks.py install

lint:
	$(PYTHON) tasks.py lint

format:
	$(PYTHON) tasks.py format

test:
	$(PYTHON) tasks.py test

build-ui:
	$(PYTHON) tasks.py build-ui

run:
	$(PYTHON) tasks.py run

db-init:
	$(PYTHON) tasks.py db-init

backup:
	$(PYTHON) tasks.py backup
