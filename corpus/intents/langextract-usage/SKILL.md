---
name: langextract-grounded-entities
description: Extract grounded entities from sample text with LangExtract and save the annotations as JSONL.
allowed-tools: [extract_hosted, extract_local, save_results]
---

# LangExtract Grounded Entity Export

Use this procedure when sample text and aligned examples should become grounded LangExtract annotations that are persisted for later review.

Tools: `extract_hosted`, `extract_local`, `save_results`.

## Workflow

1. Review the extraction classes, attributes, and example phrasing so the annotations match the supplied text.
2. Run either `extract_hosted` or `extract_local` for the extraction pass, choosing the hosted provider or local Ollama path for the run.
3. Inspect the grounded entity output for source spans and requested attributes.
4. Use `save_results` to persist the annotated documents as JSONL.

You are finished when the entities are **grounded** and the JSONL results are **saved**.
