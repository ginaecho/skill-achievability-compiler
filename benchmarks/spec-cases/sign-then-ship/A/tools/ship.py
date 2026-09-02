import os,json
json.dump({'shipped':True,'signature':(open('.sig').read() if os.path.exists('.sig') else None)}, open('ship.json','w')); print('shipped')
