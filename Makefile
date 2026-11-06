PY := .venv/bin/python

.PHONY: venv install db demo test evals clean-db

venv:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"

install: venv

db:
	$(PY) -m reqtrace.build_db

demo: db
	$(PY) demo.py

test:
	$(PY) -m pytest

evals:
	$(PY) evals/run_evals.py

clean-db:
	rm -f reqtrace.db reqtrace_from_csv.db
