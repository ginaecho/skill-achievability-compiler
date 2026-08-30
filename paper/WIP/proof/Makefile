# Mechanized audit of the WIP deviation-layer paper.  Coq 8.18, stdlib only.
COQC ?= coqc
all: DeviationLayer.vo check
DeviationLayer.vo: DeviationLayer.v
	$(COQC) DeviationLayer.v
check: DeviationLayer.vo
	$(COQC) check_dev.v
	$(COQC) check_co.v
clean:
	rm -f *.vo *.vok *.vos *.glob .*.aux
.PHONY: all check clean
