import os,sys,json
if not os.path.exists('hits.json'): print('write_report: refused -- no hits'); sys.exit(3)
open('report.md','w').write('# Report\n\n'+', '.join(json.load(open('hits.json'))['hits'])+'\n'); print('written')
