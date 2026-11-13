PYTHON ?= python3.11

.PHONY: doctor info test check

doctor:
	PYTHONPATH=src $(PYTHON) -m genesis_fintech doctor

info:
	PYTHONPATH=src $(PYTHON) -m genesis_fintech info

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

check: doctor info test
	$(PYTHON) -m compileall -q src
	$(PYTHON) -m json.tool configs/default.json > /dev/null
	$(PYTHON) -m json.tool configs/clean.json > /dev/null
	$(PYTHON) -m json.tool configs/scenario.json > /dev/null
	$(PYTHON) -m json.tool configs/full.json > /dev/null
	$(PYTHON) -m json.tool configs/interactions.json > /dev/null
