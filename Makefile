PYTHON ?= python3.11

.PHONY: doctor info check

doctor:
	PYTHONPATH=src $(PYTHON) -m genesis_fintech doctor

info:
	PYTHONPATH=src $(PYTHON) -m genesis_fintech info

check: doctor info
	$(PYTHON) -m compileall -q src
	$(PYTHON) -m json.tool configs/default.json > /dev/null
