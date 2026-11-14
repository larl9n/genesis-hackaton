PYTHON ?= python3.11
RUN_DIR ?= artifacts/submission-check

.PHONY: doctor info test check evaluate release

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
	$(PYTHON) -m json.tool configs/dataset.json > /dev/null

evaluate:
	mkdir -p "$$(dirname "$(RUN_DIR)")"
	mkdir "$(RUN_DIR)"
	PYTHONPATH=src $(PYTHON) -m genesis_fintech generate-dataset --spec configs/dataset.json --output "$(RUN_DIR)/corpus"
	cmp "$(RUN_DIR)/corpus/public-index.json" datasets/public-v1.index.json
	cmp "$(RUN_DIR)/corpus/public-train-dev.tar.gz" datasets/public-v1.tar.gz
	PYTHONPATH=src $(PYTHON) -m genesis_fintech evaluate-dataset "$(RUN_DIR)/corpus" --output "$(RUN_DIR)/evaluation" --replay

release:
	$(PYTHON) scripts/build_release.py --output dist/release-v0.5.0
	$(PYTHON) scripts/verify_release.py dist/release-v0.5.0 --full-check
