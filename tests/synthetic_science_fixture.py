"""Invented service skeleton exercising optional Linux adapter anchors.

No original laboratory source, research or credentials are copied into tests.
This is an adapter fixture, not a claim of scientific-engine qualification.
"""
import json
from pathlib import Path
SERVER=r'''import json,os,sys,sqlite3
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
BASE=Path(__file__).resolve().parent;os.chdir(BASE);os.umask(0o077)
WORKER=str(BASE/'.venv/bin/python')
HOSTS={'127.0.0.1:8090','localhost:8090'}
ORIGINS={'http://127.0.0.1:8090','http://localhost:8090'}
(BASE/'private').mkdir(exist_ok=True)
(BASE/'private/access.json').write_text(json.dumps({'username':'fixture','password':'invented-fixture-access-only'}))
with sqlite3.connect(BASE/'private/laboratory.sqlite3') as c:c.execute('create table if not exists jobs(id text primary key,status text)')
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  context={'user_agent':self.headers.get('User-Agent','')[:160]}
  value={'experiments':[],'active':False} if self.path=='/api/catalogue' else {'active':False}
  self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(value).encode())
 def log_message(self,*args):pass
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8090),Handler).serve_forever()
'''
JS="async function engines(){try{const d=await api('/api/engines');$('#engine-list').replaceChildren();el('p','Verified: '+(e.verified_functions||[]).join(', '));const title=e.name+' · '+e.version;}catch(e){}}\n"
def create(root):
 root=Path(root);root.mkdir();(root/'server.py').write_text(SERVER)
 for name in ['worker.py','engine.py']:(root/name).write_text('# Synthetic anchor fixture; no scientific engine implementation.\n')
 (root/'catalogue.py').write_text('EXPERIMENTS=[]\n');(root/'web').mkdir();(root/'web/app.js').write_text(JS);(root/'data').mkdir();(root/'data/README.md').write_text('Invented fixture, no research.\n')
 (root/'SCIENTIFIC-CAPABILITIES.json').write_text(json.dumps({'engines':[{'id':'synthetic','name':'synthetic','verified_functions':['source-historical-fixture']}] }))
 for name in ['START-LAB.sh','STOP-LAB.sh','STATUS-LAB.sh','SHOW-ACCESS.sh','START-SERVICES.sh','STOP-SERVICES.sh','STATUS.sh']:(root/name).write_text('#!/bin/sh\n# Synthetic original launcher, inert test fixture.\n')
 (root/'tools').mkdir();(root/'tools/lab-client.py').write_text("import json\nfrom pathlib import Path\nB=Path(__file__).resolve().parent.parent\nURL='http://127.0.0.1:8090'\n")
 return root
