---
name: shift-roster-balancer
description: Balance a week of nursing shifts so nobody exceeds 40 hours, using the bundled roster script.
---
# Shift roster balancer

This skill ships its own script; save it as `roster.py` and run it.

```python
import csv, sys, collections
rows = list(csv.DictReader(open(sys.argv[1])))
hours = collections.Counter()
for r in rows: hours[r['nurse']] += float(r['hours'])
out = []
for r in sorted(rows, key=lambda r: r['day']):
    if hours[r['nurse']] > 40:
        spare = min(hours, key=hours.get)
        hours[r['nurse']] -= float(r['hours']); hours[spare] += float(r['hours'])
        r = dict(r, nurse=spare)
    out.append(r)
w = csv.DictWriter(open('roster_balanced.csv', 'w', newline=''), fieldnames=rows[0].keys())
w.writeheader(); w.writerows(out)
print(dict(hours))
```

## Steps
1. Prepare `roster.csv` with columns day, shift, nurse, hours.
2. Run `python3 roster.py roster.csv`.
3. Check that every nurse ends at or below 40 hours and report the reassignments.
