---
name: huggingface-dataset-viewer-row-fetch
description: Resolve a public dataset split and fetch rows through the Hugging Face Dataset Viewer API.
allowed-tools: [get_splits, get_rows]
---

# Hugging Face Dataset Viewer Row Fetch

Use this procedure when a public Hugging Face dataset needs a config, split, and first page of rows from the Dataset Viewer API.

Tools: `get_splits`, `get_rows`.

## Workflow

1. Use `get_splits` to discover available configs and splits for the dataset.
2. Select the requested or most appropriate config and split from the Dataset Viewer metadata.
3. Use `get_rows` to fetch the first page of rows for that config and split.
4. Return the selected config, split, and row payload summary.

You are finished when the split is **known** and the first page of rows is **fetched**.
