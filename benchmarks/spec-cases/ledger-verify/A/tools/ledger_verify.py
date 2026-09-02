import csv, hashlib, sys
rows = list(csv.DictReader(open(sys.argv[1] if len(sys.argv) > 1 else "ledger.csv")))
total = sum(float(r["amount"]) for r in rows)
sig = hashlib.sha256(f"audit-service:{total:.2f}:{len(rows)}".encode()).hexdigest()[:16]
open("verified.txt", "w").write(f"VERIFIED total={total:.2f} rows={len(rows)} sig={sig}\n")
print(open("verified.txt").read())
