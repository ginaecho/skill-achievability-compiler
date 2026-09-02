import os,sys,json
if not (os.path.exists(".dev") and os.path.exists(".sre")):
    print('release: refused -- needs both approvals'); sys.exit(3)
json.dump({'released':True}, open('release.json','w')); print('released')
