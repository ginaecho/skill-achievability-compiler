---
name: acme-release-notes
description: Generate customer-facing release notes for an ACME product release from the internal change log using acmectl.
---
# ACME release notes

Use this skill when a product manager asks for release notes for an ACME release train.

## Workflow
1. Pull the merged change entries for the release with the internal release CLI:
   `acmectl changelog --train <train-id> --format json > changes.json`
   (`acmectl` is installed on ACME engineering laptops and authenticates with your SSO session.)
2. Group entries by component and drop entries labelled `internal-only`.
3. Rewrite each entry in plain customer language, one line each, past tense.
4. Save the notes as `release-notes-<train-id>.md` with sections New, Improved, Fixed.
