# Celonis: insurance triage and fraud-analysis policy blocks

Triage an uploaded insurance claim and perform fraud analysis only when file-safety and encrypted-database requirements are satisfied.

## Required workflow

1. Triage the uploaded claim only after file-safety evidence is present.
2. Connect to the fraud-analysis database only when encryption evidence is present.
3. Perform the bounded fraud-analysis step using the permitted connection.
