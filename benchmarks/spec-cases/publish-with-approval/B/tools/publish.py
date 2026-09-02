import json, os, sys
if not os.path.exists(".approved"):
    print("publish: refused -- report is not approved"); sys.exit(3)
tok = open(".approved").read().strip()
json.dump({"published": True, "approval": tok}, open("published.json", "w"))
print("published")
