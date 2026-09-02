#!/usr/bin/env python3
import json, sys
CATALOG = {"std-150": "150"}
if len(sys.argv) < 2 or sys.argv[1] == "--list":
    for k, v in CATALOG.items():
        print(f"{k}  price={v}")
    sys.exit(0)
sku = sys.argv[1]
if sku not in CATALOG:
    print(f"unknown sku {sku}; use --list"); sys.exit(2)
json.dump({"sku": sku, "price": int(CATALOG[sku])}, open("order.json", "w"))
print(f"ordered {sku} at {CATALOG[sku]}")
