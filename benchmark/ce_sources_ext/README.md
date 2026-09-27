# ce_sources_ext: extension of the public agent-skill corpus

137 further real, publicly available `SKILL.md` documents, stored verbatim
(byte-identical to upstream) at `<id>/SKILL.md` next to the license that
covers it (`<id>/LICENSE`). Provenance is in `sources.json`, with the same
fields as `benchmark/ce_sources/sources.json` (no `domain` label).

Collected on 2026-09-27 by `scripts/collect_ce_sources_ext.py` from
`git clone --depth 1` checkouts of each repository's default branch.

## Selection rules

The rules of `benchmark/ce_sources/README.md` (license, size, skipped
directories, exact and near-duplicate removal, round-robin by first hyphen
token in a fixed sha256 order), with these differences:

- **Sources.**
  - The three collections capped in `ce_sources` (microsoft/skills,
    github/awesome-copilot, trailofbits/skills) contribute up to 20 skills
    each beyond those already in `ce_sources`.
  - Three repositories new to the corpus (NVIDIA/skills,
    addyosmani/agent-skills, muratcankoylan/Agent-Skills-for-Context-Engineering)
    contribute up to 30 each.
- **Licenses.** CC-BY-4.0 is also accepted.
- **Disjointness.** Candidates are de-duplicated against `ce_sources` and
  `compaction_sources`, and against each other.

## Counts

Total: **137** skills. Licenses: Apache-2.0 1, CC-BY-4.0 30, CC-BY-SA-4.0 20, MIT 86.

| repository | skills |
|---|---|
| addyosmani/agent-skills | 25 |
| github/awesome-copilot | 20 |
| microsoft/skills | 20 |
| muratcankoylan/Agent-Skills-for-Context-Engineering | 22 |
| nvidia/skills | 30 |
| trailofbits/skills | 20 |
