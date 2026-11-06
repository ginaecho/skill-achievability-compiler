# Ground truth of real-use round 2 (held out)

Executor reports (`real2_truth/execution/`, 300) and blind adjudications
(`real2_truth/adjudication/`, 140) of `runs/20261031_real2` on branch
`gc/paper-revision`, plus the main run's adjudication prompts and batches
(`real2_truth/held_out_of_repo/`).

Kept on this separate branch so no S or D sub-agent can read them while S calls are
pending (PLAN.md, amendment 4). After the last S call, copy them into the run with
`scripts/real2.py collect-exec` (point `--work` at a directory laid out as
`<case>/result.json` and `<case>/adjudication.json`) and the held-out files back to
`runs/20261031_real2/adjudication/` and `runs/20261031_real2/batches/`.
