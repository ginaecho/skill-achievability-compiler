import os,sys,json
if not os.path.exists('.index'):
    print('search_corpus: refused -- no index'); sys.exit(3)
json.dump({'hits':['a','b']}, open('hits.json','w')); print('2 hits')
