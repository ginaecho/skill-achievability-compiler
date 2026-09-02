---
name: index-then-search
description: Produce the corpus report described by the skill; the report must be written by the tool t
---
# Index Then Search

Your job is finished when the report is **written**.

## Tools

Tools: build_index, search_corpus, write_report.

`search_corpus` requires the corpus to be **indexed** before it will run.

Each tool is a script: `python tools/<tool>.py`.

## Workflow

1. Build the index with `build_index`.
2. Search it with `search_corpus`.
3. Write the report with `write_report`.
