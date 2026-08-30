# Mechanized audit + core metatheory for the WIP paper.  Coq 8.18, stdlib only.
COQC ?= coqc
all: audit core
audit: DeviationLayer.vo
	$(COQC) check_dev.v
	$(COQC) check_co.v
core: Severity.vo
	$(COQC) check_sev.v
DeviationLayer.vo: DeviationLayer.v
	$(COQC) DeviationLayer.v
Severity.vo: Severity.v
	$(COQC) Severity.v
clean:
	rm -f *.vo *.vok *.vos *.glob .*.aux .lia.cache
.PHONY: all audit core clean
