import json, sys
who = sys.argv[1] if len(sys.argv) > 1 else "employee"
json.dump({"account": who, "id": abs(hash(who)) % 100000}, open("account.json", "w"))
print("account created for", who)
