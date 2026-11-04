import hashlib
body = open("report.md").read()
tok = "APPROVED-" + hashlib.sha256(("reviewer-7:" + body).encode()).hexdigest()[:16]
open(".approved", "w").write(tok)
print("approved:", tok)
