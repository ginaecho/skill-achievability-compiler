# Regenerate the token-free half of the evaluation, then check the paper
# against it.  The model-dependent results (live agents, usefulness runs,
# LLM compaction) need API calls and are NOT regenerated here; they ship as
# recorded, and `check` verifies the paper's numbers against them either way.
PY ?= python3

.PHONY: all results check proof paper clean-results

all: results check

# --- results that spend no model tokens ------------------------------------
results:
	$(PY) scripts/severity_eval.py
	$(PY) scripts/differential_test.py -n 150 --seed 20260902 --kmax 2 --quiet
	$(PY) scripts/differential_test.py -n 350 --seed 4242 --kmax 2 --quiet
	$(PY) scripts/grep_baseline.py
	$(PY) scripts/scan_skills.py --json --out paper/WIP/results/security_scan.json
	$(PY) scripts/token_economics.py

# --- the paper must agree with whatever is in results/ ---------------------
check:
	$(PY) scripts/check_paper_numbers.py
	$(PY) scripts/check_paper_citations.py

proof:
	$(MAKE) -C paper/WIP/proof
	$(PY) scripts/dump_statements.py

paper:
	cd paper/WIP && pdflatex -interaction=nonstopmode main.tex >/dev/null && \
	  pdflatex -interaction=nonstopmode main.tex >/dev/null && \
	  echo "pages: $$(pdfinfo main.pdf | awk '/Pages/{print $$2}')"

clean-results:
	@echo "results/ is the evaluation record; remove files by hand if you mean it"
