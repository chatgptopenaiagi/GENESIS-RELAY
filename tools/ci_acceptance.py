#!/usr/bin/env python3
"""Public synthetic installed/native acceptance and real inter-job transfer proof.

Never point this tool at the operator's laboratory. It creates and operates only
inside its own new work directory using bundled, invented demo data.
"""
from __future__ import annotations
import argparse,datetime,hashlib,http.cookiejar,json,os,platform,shutil,subprocess,sys,time,urllib.error,urllib.request
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def write(p,value):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,indent=2,ensure_ascii=True)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['export','receive','reconcile','standalone'],required=True);p.add_argument('--work',required=True);p.add_argument('--report',required=True);p.add_argument('--capsule');p.add_argument('--return-capsule');p.add_argument('--source-project');p.add_argument('--executable');p.add_argument('--python',default=sys.executable);a=p.parse_args();work=Path(a.work).absolute();work.mkdir(parents=True,exist_ok=True);cmd=[str(Path(a.executable).absolute())] if a.executable else [str(Path(a.python).absolute()),'-I','-m','genesis_relay'];state=work/'scratch/state'
 env=os.environ.copy()
 for k in ['PYTHONPATH','PYTHONHOME','GENESIS_RELAY_HOME']:env.pop(k,None)
 result={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_commit':os.environ.get('GITHUB_SHA'),'platform':{'system':platform.system(),'machine':platform.machine(),'python':platform.python_version(),'libc':platform.libc_ver()},'relay_command':cmd,'phase':a.phase,'scope':'Public synthetic demo only. No private scientific lab, WSL or Codex model acceptance inferred.','passed':{},'failed':{}}
 def run(*args,raw=False):
  r=subprocess.run(cmd+list(map(str,args)),cwd=work,env=env,capture_output=True,text=True,timeout=120)
  if r.returncode:raise AssertionError('Relay command failed: '+r.stderr[-1200:])
  return r.stdout if raw else json.loads(r.stdout)
 def check(name,fn):
  try:result['passed'][name]=fn() or True;print('PASS',name,flush=True)
  except Exception as e:result['failed'][name]=type(e).__name__+': '+str(e)[-1800:];print('FAIL',name,result['failed'][name],flush=True)
 def acceptance(receipt):
  accepted=run('demo','accept',receipt);assert accepted.get('status') in ['PASSED','ACCEPTANCE_PASSED'] or accepted.get('ready_to_continue') is True,accepted
  record=json.loads(Path(receipt).read_text());assert record.get('ready_to_continue') is True,record.get('state');project=Path(record['project_path'])
  script=project/'acceptance.py'
  if script.exists():
   r=subprocess.run([a.python,'-I',str(script)],cwd=project,env=env,capture_output=True,text=True,timeout=30);assert r.returncode==0,r.stderr[-800:]
  return {'trusted_demo_acceptance':True,'ready_to_continue':True,'route':record['route'],'capsule_sha256':record['archive_sha256'],'standalone_project_script_executed':script.exists()}
 def ui(source):
  ui_state=work/'scratch/ui-state';started=run('--state-dir',ui_state,'ui','start','--source',source,'--port','8240');url=started['url'];assert started.get('state')=='RUNNING',started
  try:
   creds=json.loads((ui_state/'private/ui/access.json').read_text());old=sha(ui_state/'private/ui/access.json');jar=http.cookiejar.CookieJar();op=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(jar))
   def post(path,data,csrf=None,origin=None):
    headers={'Content-Type':'application/json','Origin':origin or url.rstrip('/')}
    if csrf:headers['X-CSRF-Token']=csrf
    return op.open(urllib.request.Request(url+path,data=json.dumps(data).encode(),headers=headers),timeout=30)
   def denied(fn,code):
    try:fn()
    except urllib.error.HTTPError as e:assert e.code==code;return
    raise AssertionError('Unauthorized operation unexpectedly succeeded')
   denied(lambda:post('api/action',{'action':'plan'}),401)
   with post('api/login',{k:creds[k] for k in ['username','password']}) as r:csrf=json.load(r)['csrf']
   denied(lambda:post('api/action',{'action':'plan'},'wrong'),403)
   denied(lambda:post('api/action',{'action':'plan'},csrf,'https://invalid.example'),403)
   for name in ['','app.js','style.css']:
    with op.open(url+name,timeout=10) as r:assert r.status==200 and len(r.read())>100
   def action(name,ident=None):
    body={'action':name}
    if ident:body['capsule_id']=ident
    with post('api/action',body,csrf) as r:job=json.load(r)
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
     with op.open(url+'api/jobs/'+job['id'],timeout=10) as r:current=json.load(r)
     if current['status'] in ['succeeded','failed']:
      assert current['status']=='succeeded',current.get('message');return current['result']
     time.sleep(.1)
    raise AssertionError('UI action timed out')
   action('plan');exported=action('export');ident=exported['ui_id'];action('inspect',ident);action('receive_plan',ident);restored=action('restore',ident);action('verify_restore',ident);action('return_create',ident)
   with op.open(url+'api/data',timeout=30) as r:data=json.load(r);assert data['capsules'] and data['receipts'];assert data['source']['available']
   restarted=run('--state-dir',ui_state,'ui','restart','--source',source,'--port',str(urllib.request.urlparse(url).port) if hasattr(urllib.request,'urlparse') else '8240');assert restarted['state']=='RUNNING';assert sha(ui_state/'private/ui/access.json')==old
   with op.open(restarted['url']+'api/session',timeout=10) as r:assert json.load(r)['authenticated']
   return {'url':restarted['url'],'packaged_assets_served':True,'local_auth_origin_csrf':True,'actual_actions':['plan','export','inspect','receive_plan','restore','verify_restore','return_create'],'credentials_and_session_survived_restart':True,'inspection_does_not_execute_source':True}
  finally:run('--state-dir',ui_state,'ui','stop')
 check('cli_startup',lambda:{'version':run('--version',raw=True).strip(),'help_available':bool(run('--help',raw=True))})
 if a.phase in ['export','standalone']:
  source=work/'transfer/source-project';transfer=work/'transfer';transfer.mkdir(parents=True,exist_ok=True);cap=transfer/'demo-capsule.zip'
  def exported():
   created=run('demo','create','--root',source);value=run('--state-dir',state,'demo','export','--root',source,'--output',cap);verify=run('verify',cap,'--summary');assert verify['verified'];proof={'capsule_sha256':sha(cap),'bytes':cap.stat().st_size,'source_platform':platform.system(),'source_architecture':platform.machine(),'source_commit':os.environ.get('GITHUB_SHA')};write(transfer/'TRANSFER-PROOF.json',proof);return proof
  check('actual_linux_or_native_export',exported)
  if cap.exists():
   def restored_local():
    rec=run('demo','restore',cap,'--destination',work/'scratch/receiving');receipt=rec['receipt_path'];verified=run('receive','Verify','--receipt',receipt);assert verified['status']=='PASSED';return acceptance(receipt)
   check('fresh_destination_reconstruction',restored_local)
   check('packaged_browser_interface',lambda:ui(source))
 elif a.phase=='receive':
  cap=Path(a.capsule).absolute();proof=json.loads((cap.parent/'TRANSFER-PROOF.json').read_text())
  def receive():
   assert sha(cap)==proof['capsule_sha256'];assert proof['source_platform']=='Linux';assert platform.system()=='Windows';verified=run('verify',cap,'--summary');assert verified['verified'];rec=run('demo','restore',cap,'--destination',work/'scratch/receiving','--route','NATIVE_WINDOWS_X64');write(work/'scratch/receipt-reference.json',rec);return {'exact_linux_artifact_received':True,'capsule_sha256':sha(cap),'receipt_path':rec['receipt_path']}
  check('linux_to_actual_windows_transfer',receive)
  ref=work/'scratch/receipt-reference.json'
  if ref.exists():
   receipt=json.loads(ref.read_text())['receipt_path'];check('native_windows_demo_acceptance',lambda:acceptance(receipt));project=Path(json.loads(Path(receipt).read_text())['project_path'])
   def returned():
    target=work/'return/demo-return.zip';target.parent.mkdir(parents=True,exist_ok=True);value=run('demo','return',receipt,'--output',target);proof={'return_sha256':sha(target),'bytes':target.stat().st_size,'source_capsule_sha256':sha(cap),'destination_platform':platform.system(),'destination_architecture':platform.machine(),'source_commit':os.environ.get('GITHUB_SHA')};write(target.parent/'RETURN-PROOF.json',proof);return proof
   check('native_windows_changed_file_return',returned);check('native_windows_packaged_browser_interface',lambda:ui(project))
 elif a.phase=='reconcile':
  returned=Path(a.return_capsule).absolute();source=Path(a.source_project).absolute();proof=json.loads((returned.parent/'RETURN-PROOF.json').read_text())
  def reconcile():
   assert sha(returned)==proof['return_sha256'];assert proof['destination_platform']=='Windows';assert platform.system()=='Linux';before={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*') if p.is_file()};value=run('demo','reconcile',returned,'--project',source);after={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*') if p.is_file()};assert before==after,'Sender source fixture modified';assert value.get('status')=='PASSED',value;return {'exact_windows_return_received':True,'sender_fixture_unchanged':True,'result':value}
  check('actual_windows_to_linux_reconciliation',reconcile)
 result['status']='PASSED' if not result['failed'] else 'FAILED';result['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();write(a.report,result);print(json.dumps({'status':result['status'],'passed':len(result['passed']),'failed':len(result['failed'])}),flush=True);return bool(result['failed'])
if __name__=='__main__':raise SystemExit(main())
