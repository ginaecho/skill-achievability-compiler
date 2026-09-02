# Mechanized metatheory for the WIP paper.  Coq 8.18, stdlib only.
COQC ?= coqc
all: audit core bridge regular
audit: DeviationLayer.vo
	$(COQC) check_dev.v
	$(COQC) check_co.v
core: Severity.vo
	$(COQC) check_sev.v
bridge: Bridge.vo
	$(COQC) check_bridge.v
regular: Regular.vo
	$(COQC) check_regular.v
DeviationLayer.vo: DeviationLayer.v
	$(COQC) DeviationLayer.v
Severity.vo: Severity.v
	$(COQC) Severity.v
Bridge.vo: Bridge.v Severity.vo
	$(COQC) Bridge.v
Regular.vo: Regular.v
	$(COQC) Regular.v
clean:
	rm -f *.vo *.vok *.vos *.glob .*.aux .lia.cache
.PHONY: all audit core bridge regular clean
