import hashlib, json, sys
who = sys.argv[1] if len(sys.argv) > 1 else "employee"
tok = "BADGE-" + hashlib.sha256(("badge-office:" + who).encode()).hexdigest()[:12]
json.dump({"badge": tok, "for": who}, open("badge.json", "w"))
print("badge issued:", tok)
