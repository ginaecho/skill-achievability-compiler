---
name: bibtex-cleaner
description: Clean a messy BibTeX library - deduplicate entries, normalize keys and fix capitalization of titles.
---
# BibTeX cleanup

1. Parse `refs.bib` with `bibtexparser`.
2. Merge duplicates (same DOI, or same title and year), keeping the most complete entry.
3. Regenerate keys as `lastnameYEARfirstword`, protect capitalized words in titles with braces.
4. Write `refs_clean.bib` and a `changes.md` report.
