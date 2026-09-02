# Mechanized metatheory for the WIP paper.  Coq 8.18, stdlib only.
COQC ?= coqc
all: audit core bridge regular mu repairs abort interleave kernel
audit: DeviationLayer.vo
	$(COQC) check_dev.v
	$(COQC) check_co.v
core: Severity.vo
	$(COQC) check_sev.v
bridge: Bridge.vo
	$(COQC) check_bridge.v
regular: Regular.vo
	$(COQC) check_regular.v
mu: Mu.vo
	$(COQC) check_mu.v
repairs: Repairs.vo
	$(COQC) check_repairs.v
abort: Abort.vo
	$(COQC) check_abort.v
interleave: Interleave.vo
	$(COQC) check_interleave.v
kernel: Kernel.vo
	$(COQC) check_kernel.v
# the executable kernel: extraction + OCaml driver
kernel/skillc_kernel: Kernel.vo extract.v kernel/driver.ml
	mkdir -p kernel && $(COQC) extract.v
	cd kernel && ocamlopt -w -a -o skillc_kernel kernel.mli kernel.ml driver.ml
binary: kernel/skillc_kernel
DeviationLayer.vo: DeviationLayer.v
	$(COQC) DeviationLayer.v
Severity.vo: Severity.v
	$(COQC) Severity.v
Bridge.vo: Bridge.v Severity.vo
	$(COQC) Bridge.v
Regular.vo: Regular.v
	$(COQC) Regular.v
Mu.vo: Mu.v Severity.vo Regular.vo
	$(COQC) Mu.v
Repairs.vo: Repairs.v Severity.vo
	$(COQC) Repairs.v
Abort.vo: Abort.v Severity.vo Bridge.vo Repairs.vo
	$(COQC) Abort.v
Interleave.vo: Interleave.v Severity.vo Bridge.vo
	$(COQC) Interleave.v
Kernel.vo: Kernel.v Severity.vo Regular.vo Mu.vo
	$(COQC) Kernel.v
clean:
	rm -f *.vo *.vok *.vos *.glob .*.aux .lia.cache kernel/*.cm* kernel/*.o
.PHONY: all audit core bridge regular mu repairs abort interleave kernel binary clean
