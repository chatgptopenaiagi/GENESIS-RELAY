"""Loopback UI security, private download and visible browser acceptance.

Default unittest run uses only isolated synthetic files and a temporary server.
`--browser` explicitly inspects the existing owned UI, without exporting or
stopping the source laboratory. Firefox/geckodriver must already be installed.
"""
import base64,datetime,hashlib,http.cookiejar,importlib.util,json,os,re,shutil,signal,socket,subprocess,sys,tempfile,threading,time,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B/'src'))
from genesis_relay import ui

class UITests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='relay-ui-');self.root=Path(self.tmp.name);self.state=self.root/'state';self.source=self.root/'source';self.source.mkdir();ui.setup(self.state);self.server=ui.Server(('127.0.0.1',0),ui.Handler);self.server.relay_state=self.state;self.server.relay_source=self.source;self.base='http://127.0.0.1:'+str(self.server.server_port);self.server.relay_url=self.base+'/';self.server.auth_failures={'count':0,'until':0};self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.op=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));c=ui.credentials(self.state);self.creds={k:c[k] for k in ['username','password']};self.token=None
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=5);self.tmp.cleanup()
 def req(self,path,body=None,headers=None,opener=None):
  h={'Accept':'application/json',**(headers or {})}
  if body is not None:h['Content-Type']='application/json'
  try:
   with (opener or self.op).open(urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=h),timeout=10) as r:return r.status,r.read(),dict(r.headers)
  except urllib.error.HTTPError as e:return e.code,e.read(),dict(e.headers)
 def login(self):
  code,raw,headers=self.req('/api/login',self.creds,{'Origin':self.base});self.assertEqual(code,200);self.token=json.loads(raw)['csrf'];return headers
 def mutate(self,body):return self.req('/api/action',body,{'Origin':self.base,'X-CSRF-Token':self.token})
 def test_public_login_private_inventory(self):
  self.assertEqual(self.req('/')[0],200);self.assertEqual(self.req('/api/data')[0],401);self.assertFalse(json.loads(self.req('/api/session')[1])['authenticated'])
 def test_login_private_cookie_and_security_headers(self):
  h=self.login();self.assertIn('HttpOnly',h['Set-Cookie']);self.assertIn('SameSite=Strict',h['Set-Cookie']);self.assertEqual(h['X-Frame-Options'],'DENY');self.assertEqual(h['Referrer-Policy'],'no-referrer');self.assertIn("default-src 'self'",h['Content-Security-Policy']);self.assertTrue(json.loads(self.req('/api/session')[1])['authenticated'])
 def test_origin_host_and_csrf_rejection(self):
  self.login();self.assertEqual(self.req('/api/data',headers={'Host':'attacker.invalid'})[0],403);self.assertEqual(self.req('/api/action',{'action':'export'},{'X-CSRF-Token':self.token})[0],403);self.assertEqual(self.req('/api/action',{'action':'export'},{'Origin':'http://evil.invalid','X-CSRF-Token':self.token})[0],403);self.assertEqual(self.req('/api/action',{'action':'export'},{'Origin':self.base})[0],403)
 def test_no_arbitrary_paths_or_shell_commands(self):
  self.login()
  for body in [{'action':'shell','command':'id'},{'action':'verify','capsule_id':'../../etc/passwd'},{'action':'export','source':'/etc'},{'action':'stop-service','port':8080}]:self.assertEqual(self.mutate(body)[0],400)
  for path in ['/private/ui/access.json','/../private/ui/access.json','/%2e%2e/private/ui/access.json','/download/../../etc/passwd.zip','/reports/no-such-report']:self.assertEqual(self.req(path)[0],404)
 def test_credentials_stay_private(self):
  self.login();raw=self.req('/api/data')[1];self.assertNotIn(self.creds['password'].encode(),raw);self.assertEqual((self.state/'private/ui/access.json').stat().st_mode&0o777,0o600);self.assertEqual((self.state/'private/ui').stat().st_mode&0o777,0o700)
 def test_logout_revokes_session(self):
  self.login();self.assertEqual(self.req('/api/logout',{}, {'Origin':self.base,'X-CSRF-Token':self.token})[0],200);self.assertEqual(self.req('/api/data')[0],401)
 def test_fixed_action_records_background_result(self):
  self.login()
  with patch.object(ui,'do_action',return_value={'message':'Synthetic fixed action finished.','result':{'fixture':True}}):
   code,body,_=self.mutate({'action':'plan'});self.assertEqual(code,202);ident=json.loads(body)['id'];deadline=time.monotonic()+5
   while time.monotonic()<deadline:
    record=json.loads(self.req('/api/jobs/'+ident)[1])
    if record['status']=='succeeded':break
    time.sleep(.02)
   self.assertEqual(record['status'],'succeeded');self.assertTrue((self.state/'ui-jobs'/(ident+'.json')).is_file())
 def test_private_streaming_download_range_and_hash(self):
  self.login();path=self.state/'capsules/fixture.zip';payload=b'PK\x03\x04'+os.urandom(1024*17);path.write_bytes(payload);ui.remember_capsule(self.state,path,{'capsule':{'capsule_id':'fixture','project_name':'Synthetic fixture'},'manifest':{'entries':[]},'completeness':{}});ident=ui.capsule_identifier(path)
  self.assertEqual(self.req('/download/'+ident+'.zip',opener=urllib.request.build_opener(urllib.request.ProxyHandler({})))[0],401)
  code,raw,headers=self.req('/download/'+ident+'.zip',headers={'Range':'bytes=2-99'});self.assertEqual(code,206);self.assertEqual(raw,payload[2:100]);self.assertEqual(headers['Content-Range'],'bytes 2-99/'+str(len(payload)));self.assertEqual(headers['ETag'],'"'+hashlib.sha256(payload).hexdigest()+'"')
  code,raw,_=self.req('/download/'+ident+'.zip');self.assertEqual(code,200);self.assertEqual(hashlib.sha256(raw).digest(),hashlib.sha256(payload).digest());self.assertEqual(self.req('/download/'+ident+'.zip',headers={'Range':'bytes=999999-'} )[0],416)
  before=path.stat();path.write_bytes(b'XX'+payload[2:]);os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns));self.assertEqual(self.req('/download/'+ident+'.zip')[0],409)
  logs=(self.state/'ui-evidence/downloads.jsonl').read_text();self.assertIn('not a destination receipt',logs);self.assertEqual(ui.receipts(self.state),[])
 def test_report_escapes_imported_text(self):
  self.login();p=self.state/'ui-evidence/example.md';p.write_text('<script>document.body.remove()</script>');item=next(x for x in ui.data_view(self.state,self.source)['reports'] if x['title']=='example.md');code,raw,_=self.req('/reports/'+item['id']);self.assertEqual(code,200);self.assertIn(b'&lt;script&gt;',raw);self.assertNotIn(b'<script>',raw)
 def test_foreign_identity_never_owned(self):
  self.assertFalse(ui.owned({'pid':os.getpid(),'identity':{}}));self.assertEqual(ui.identity(0),{})
 def test_receipt_companion_report_is_not_a_second_receipt(self):
  folder=self.state/'receiving/receipts';folder.mkdir(parents=True)
  ui.atomic(folder/'base.json',{'capsule_id':'one','project_path':str(self.root/'owned'),'receipt_path':str(folder/'base.json'),'state':'RESTORED'})
  ui.atomic(folder/'base-verification.json',{'capsule_id':'one','state':'RESTORED','status':'PASSED'})
  self.assertEqual(len(ui.receipts(self.state)),1)
 def test_receiver_ui_can_find_kept_immutable_capsule(self):
  folder=self.state/'capsules/one';folder.mkdir(parents=True);path=folder/'capsule.zip';path.write_bytes(b'PK synthetic kept evidence')
  self.assertIn(path.absolute(),ui.capsule_paths(self.state))
 def test_destination_reports_require_matching_new_identity(self):
  project=self.root/'owned';folder=project/'_relay';folder.mkdir(parents=True);receipt={'capsule_id':'one','archive_sha256':'a'*64,'project_path':str(project),'receipt_path':str(self.state/'receiving/receipts/one.json'),'route':'LOCAL_LINUX','restored_at':'2026-01-02T00:00:00+00:00'}
  record={'project_path':str(project),'source_capsule_id':'one','source_capsule_sha256':'a'*64,'route':'LOCAL_LINUX','started_at':'2026-01-01T00:00:00+00:00','status':'ACCEPTANCE_PASSED'}
  ui.atomic(folder/'ACCEPTANCE-LATEST.json',record);self.assertFalse(ui.destination_reports([receipt]));record['started_at']='2026-01-03T00:00:00+00:00';ui.atomic(folder/'ACCEPTANCE-LATEST.json',record);self.assertEqual(len(ui.destination_reports([receipt])),1);record['source_capsule_sha256']='b'*64;ui.atomic(folder/'ACCEPTANCE-LATEST.json',record);self.assertFalse(ui.destination_reports([receipt]))
 def test_installed_package_can_offer_bundled_windows_receiver(self):
  code=self.root/'installed/lib/site-packages/genesis_relay';folder=code/'windows';folder.mkdir(parents=True);(folder/'Receive-Relay.ps1').write_text('# Synthetic trusted receiver asset.\n');(folder/'not-an-asset.txt').write_text('Ignored')
  with patch.object(ui,'CODE',code):items=ui.software_assets()
  self.assertEqual([a['name'] for a in items],['Receive-Relay.ps1']);self.assertTrue(all(a['path'].startswith(str(code)) for a in items))
 def test_software_kit_and_checksums_are_exact_allowlisted_assets(self):
  code=self.root/'checkout/src/genesis_relay';code.mkdir(parents=True);folder=self.root/'checkout/dist';folder.mkdir()
  for name in ['genesis-relay-software-0.1.0.zip','SHA256SUMS','private-research.zip','access.json']:(folder/name).write_bytes(b'Synthetic fixture')
  with patch.object(ui,'CODE',code):items=ui.software_assets()
  self.assertEqual({x['name'] for x in items},{'genesis-relay-software-0.1.0.zip','SHA256SUMS'})
 def test_isolated_source_ui_lifecycle_ignores_cwd_and_pythonpath(self):
  state=self.root/'isolated-state';source=self.root/'isolated-project';source.mkdir();unrelated=self.root/'unrelated';unrelated.mkdir();hostile=self.root/'hostile';hostile.mkdir();(hostile/'genesis_relay').mkdir();(hostile/'genesis_relay/__init__.py').write_text('raise RuntimeError("ambient package must not be imported")\n')
  env=os.environ.copy();env['PYTHONPATH']=str(hostile);env['PYTHONHOME']=str(hostile)
  bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from genesis_relay.ui import main;raise SystemExit(main())';base=[sys.executable,'-I','-c',bootstrap,str(ui.CODE.parent)]
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  if port>65516:port=8120
  args=['--state-dir',str(state),'--source',str(source),'--port',str(port)]
  def invoke(action):
   p=subprocess.run([*base,action,*args],cwd=unrelated,env=env,capture_output=True,text=True,timeout=25)
   self.assertEqual(p.returncode,0,p.stdout+p.stderr);return json.loads(p.stdout)
  first=None
  try:
   first=invoke('start');self.assertEqual(first['state'],'RUNNING');self.assertTrue(first['owned']);record=ui.read(state/'private/ui/process.json');self.assertIn('-I',record['identity']['command'].split('\0'));self.assertIn(str(ui.CODE.parent),record['identity']['command'].split('\0'));self.assertTrue(ui.live(record));initial=record['pid']
   after=invoke('restart');self.assertEqual(after['state'],'RUNNING');self.assertNotEqual(ui.read(state/'private/ui/process.json')['pid'],initial);self.assertEqual(invoke('status')['state'],'RUNNING')
  finally:
   if first:invoke('stop')
  self.assertEqual(ui.status(state)['state'],'STOPPED')

class Browser:
 def __init__(self,evidence):
  self.session=None;self.process=None;self.mobile_active=False;self.evidence=evidence;self.evidence.mkdir(parents=True,exist_ok=True)
  for port in range(4472,4488):
   with socket.socket() as s:
    s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    try:s.bind(('127.0.0.1',port));self.port=port;break
    except OSError:continue
  else:raise RuntimeError('No free QA WebDriver port; nothing stopped')
  self.base='http://127.0.0.1:'+str(self.port);self.op=urllib.request.build_opener(urllib.request.ProxyHandler({}));self.log=(evidence/'ui-browser-driver.log').open('ab');self.process=subprocess.Popen([shutil.which('geckodriver') or '/usr/bin/geckodriver','--host','127.0.0.1','--port',str(self.port),'--allow-system-access'],stdin=subprocess.DEVNULL,stdout=self.log,stderr=self.log,start_new_session=True)
  for _ in range(50):
   try:self.request('/status');break
   except OSError:time.sleep(.2)
  value=self.request('/session',{'capabilities':{'alwaysMatch':{'browserName':'firefox','moz:firefoxOptions':{'args':['-headless'],'prefs':{'security.sandbox.content.level':0,'browser.shell.checkDefaultBrowser':False,'devtools.responsive.viewport.width':360,'devtools.responsive.viewport.height':780,'signon.rememberSignons':False}}}}});self.session=value['sessionId'];self.command('/timeouts',{'script':60000,'pageLoad':60000,'implicit':0})
 def request(self,path,data=None,method=None):
  q=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'},method=method or ('POST' if data is not None else 'GET'))
  try:
   with self.op.open(q,timeout=75) as r:value=json.load(r)['value']
  except urllib.error.HTTPError as e:
   item=json.loads(e.read()).get('value',{});raise RuntimeError(str(item.get('error'))+': '+str(item.get('message'))[:300])
  if isinstance(value,dict) and 'error' in value:raise RuntimeError(value['error']+': '+value.get('message','')[:300])
  return value
 def command(self,path,data=None,method=None):return self.request('/session/'+self.session+path,data,method)
 def js(self,script,*args):return self.command('/execute/sync',{'script':script,'args':list(args)})
 def wait(self,script,seconds=45):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   if self.js(script):return
   time.sleep(.25)
  raise RuntimeError('Browser condition timed out: '+script[:160])
 def screenshot(self,name):(self.evidence/('ui-'+name+'.png')).write_bytes(base64.b64decode(self.command('/screenshot')))
 def mobile(self):
  self.command('/moz/context',{'context':'chrome'});self.js("const { require }=ChromeUtils.importESModule('resource://devtools/shared/loader/Loader.sys.mjs'); const responsive=require('resource://devtools/client/responsive/manager.js'); responsive.openIfNeeded(window,window.gBrowser.selectedTab);return true;");self.command('/moz/context',{'context':'content'});self.mobile_active=True;self.wait('return innerWidth===360',30)
 def close(self):
  try:
   if self.session:self.command('',method='DELETE')
  except Exception:pass
  if self.process and self.process.poll() is None:
   os.killpg(self.process.pid,signal.SIGTERM)
   try:self.process.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(self.process.pid,signal.SIGKILL);self.process.wait()
  self.log.close()

def browser_acceptance():
 state=B/'private/state';record=ui.status(state);base=record['url'];creds=ui.credentials(state);evidence=B/'evidence';output={'checked_at':ui.now(),'passed':{},'failed':{},'skipped':{'physical_touch':'Real Firefox 360px viewport is tested; no physical Android touchscreen or native Windows execution is claimed.'}};browser=None
 def check(name,fn):
  try:output['passed'][name]=fn() or True;print('PASS',name,flush=True)
  except unittest.SkipTest as error:output['skipped'][name]=str(error);print('SKIP',name,str(error),flush=True)
  except Exception as error:output['failed'][name]=type(error).__name__+': '+str(error)[:800];print('FAIL',name,output['failed'][name],flush=True)
 def assert_(value,message='assertion failed'):
  if not value:raise AssertionError(message)
  return True
 try:
  browser=Browser(evidence);b=browser;b.command('/url',{'url':base});b.wait('return !!document.querySelector("#login-form")');b.screenshot('login-desktop');b.js('document.querySelector("#login-username").value=arguments[0];document.querySelector("#login-password").value=arguments[1];document.querySelector("#login-form").requestSubmit();return true;',creds['username'],creds['password']);b.wait('return document.querySelectorAll("[data-page]").length===8 && !!document.querySelector("#main h1")');check('login_and_eight_pages',lambda:assert_(b.js('return document.querySelectorAll("[data-page]").length===8 && !document.querySelector("#login-form")')))
  b.command('/window/rect',{'width':1440,'height':1000});b.screenshot('projects-desktop')
  def nav(page):
   title=b.js('const a=document.querySelector("a[data-page="+arguments[0]+"]");const t=a.lastElementChild.textContent;a.click();return t;',page);b.wait('return document.querySelector("#main h1")?.textContent==='+json.dumps(title))
  def layout():
   value=b.js('return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,bodyWidth:document.body.scrollWidth}');assert value['scrollWidth']<=value['width'],value;return value
  check('desktop_layout',layout)
  # Inspect the actual already-exported private capsule only; this does not execute its code.
  def inspect():
   nav('inside');button=b.js('return !!document.querySelector("button[data-action=verify]")')
   if not button:raise unittest.SkipTest('No capsule exists yet; actual capsule inspection is not claimed.')
   b.js('document.querySelector("button[data-action=verify]").click();return true;');b.wait('return !document.querySelector(".job-banner") && !!document.querySelector("a[data-download-capsule]")',120)
   q=b.js('return document.querySelector("a[data-download-capsule]").getAttribute("href")');assert q.startswith('/download/');b.screenshot('capsule-desktop');return {'capsule_available':True,'verified_download_link':q,'inspection_did_not_execute_project':True}
  check('inspect_capsule_and_real_download_control',inspect)
  def search():
   nav('inside');b.js('const e=document.querySelector("#entry-search");e.value="ZZ_no_entry_match_YY";e.dispatchEvent(new Event("input",{bubbles:true}));return true;');assert b.js('return document.querySelectorAll("[data-entry-path]").length')==0;b.js('const e=document.querySelector("#entry-search");e.value="";e.dispatchEvent(new Event("input",{bubbles:true}));return true;');return {'search_filters_rendered_entries':True}
  check('entry_search',search)
  nav('projects');b.mobile();check('real_mobile_360_viewport',lambda:assert_(b.js('return innerWidth===360')))
  def menu():
   b.js('document.querySelector("#menu").click();return true;');assert b.js('return document.querySelector("#sidebar").classList.contains("open")');b.screenshot('navigation-mobile');b.js('document.querySelector("a[data-page=send]").click();return true;');assert b.js('return !document.querySelector("#sidebar").classList.contains("open")');return {'open_close_and_navigation':True}
  check('mobile_navigation',menu)
  names={'projects':'My projects','send':'Send my laboratory','inside':'What is inside this capsule?','receive':'Receive and continue','letter':'Engineering letter','verification':'Verification results','returns':'Return improvements','history':'Transfer history'}
  for page,title in names.items():
   def show(page=page,title=title):
    b.js('location.hash=arguments[0];return true;',page);b.wait('return document.querySelector("#main h1")?.textContent==='+json.dumps(title));value=layout();assert value['width']==360;assert b.js('return !document.querySelector("#main pre:not(.letter)")');b.screenshot(page+'-mobile');return value
   check('mobile_page_'+page,show)
  def letter():
   nav('letter');text=b.js('return document.querySelector("#letter-content")?.textContent||""');return {'readable_engineering_letter':bool(text),'scope':'Actual capsule letter when available; no fabricated knowledge.'}
  check('engineering_letter_rendering',letter)
  def windows():
   nav('receive');text=b.js('return document.querySelector("#main").textContent');assert 'Windows execution not run' in text and 'Not Run' in text;return {'native_wsl_and_fresh_codex_not_inferred':True}
  check('windows_execution_honesty',windows)
  def label():
   nav('inside');return assert_(b.js('return Array.from(document.querySelectorAll("input,select")).every(e=>e.labels.length||e.getAttribute("aria-label"))'))
  check('accessible_filter_labels',label)
  def readiness_guard():
   nav('projects')
   b.js('window.__relayFetch=window.fetch;window.fetch=async function(input,options){const r=await window.__relayFetch(input,options);if(String(input)==="/api/data"){const d=await r.json();d.receipts=[{capsule_id:d.capsules[0]?.capsule_id,state:"READY_TO_CONTINUE",ready_to_continue:false,latest_acceptance_status:"FAILED",route:"LOCAL_LINUX",project_path:"synthetic guarded fixture"}];return new Response(JSON.stringify(d),{status:200,headers:{"Content-Type":"application/json"}});}return r;};document.querySelector("#update-view").click();return true;')
   try:
    b.wait('return document.querySelector("#main").textContent.includes("Acceptance needs attention")')
    assert b.js('return !Array.from(document.querySelectorAll(".stage.done")).some(e=>e.textContent.includes("Ready to continue"))')
   finally:
    b.js('window.fetch=window.__relayFetch;delete window.__relayFetch;return true;');b.command('/refresh',{});b.wait('return !!document.querySelector("#main h1") && !document.querySelector("#login-form")')
   return {'synthetic_later_failure_never_shows_ready':True,'source_and_destination_not_modified':True}
  check('readiness_requires_current_acceptance',readiness_guard)
  def actual_ready():
   nav('receive');b.wait('return !!document.querySelector(".stage-flow")');actual=next((r for r in ui.receipts(state) if r.get('ready_to_continue') is True),None)
   if not actual:raise unittest.SkipTest('No real ready receipt exists; do not fabricate a Ready screenshot')
   b.wait('return Array.from(document.querySelectorAll(".stage.done")).some(e=>e.textContent.includes("Ready to continue"))')
   assert b.js('return !document.querySelector("#main").textContent.includes("synthetic guarded fixture")')
   b.js('document.querySelector(".stage-flow").scrollIntoView({block:"center"});return true;');b.screenshot('receive-ready-mobile');return {'actual_receipt_ready':True,'route':actual['route'],'capsule_id':actual['capsule_id'],'fresh_browser_reload_after_fixture':True}
  check('actual_sealed_ready_receipt_display',actual_ready)
  nav('projects');b.screenshot('final-projects-mobile')
  # Complete authenticated download stream is checked without loading the file into memory.
  def download():
   op=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));url=base.rstrip('/')
   with op.open(urllib.request.Request(url+'/api/login',data=json.dumps({k:creds[k] for k in ['username','password']}).encode(),headers={'Content-Type':'application/json','Origin':url}),timeout=20) as f:auth=json.load(f)
   with op.open(url+'/api/data',timeout=20) as f:d=json.load(f)
   item=next((c for c in d['capsules'] if c.get('verified')),None)
   if not item:raise unittest.SkipTest('No verified private capsule exists yet')
   h=hashlib.sha256();size=0
   with op.open(url+'/download/'+item['id']+'.zip',timeout=40) as f:
    for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk);size+=len(chunk)
   assert h.hexdigest()==item['archive_sha256'] and size==item['size']
   with op.open(urllib.request.Request(url+'/api/logout',data=b'{}',headers={'Content-Type':'application/json','Origin':url,'X-CSRF-Token':auth['csrf']}),timeout=10) as f:f.read()
   return {'bytes_streamed':size,'sha256':h.hexdigest(),'actual_authenticated_route':url+'/download/'+item['id']+'.zip','transport_not_marked_complete':True}
  check('private_full_download_stream_and_digest',download)
 except Exception as error:output['failed']['browser_setup_or_workflow']=type(error).__name__+': '+str(error)[:1000]
 finally:
  if browser:browser.close()
  output['finished_at']=ui.now();output['source_hashes']={str(p.relative_to(B)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [B/'src/genesis_relay/ui.py',*sorted((B/'src/genesis_relay/web').glob('*'))] if p.is_file()};(evidence/'ui-browser-tests.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps({'passed':len(output['passed']),'failed':len(output['failed']),'skipped':len(output['skipped'])}),flush=True)
 return bool(output['failed'])

def software_browser_regression():
 """Target only the isolated-launch/kit-download fix; do not rerun science."""
 state=B/'private/state';info=ui.status(state);base=info['url'].rstrip('/');c=ui.credentials(state);browser=None;out={'checked_at':ui.now(),'scope':'Targeted source-bootstrap and visible software-kit regression. No capsule export, restoration or scientific execution.','passed':{},'failed':{}}
 try:
  if info['state']!='RUNNING':raise RuntimeError('Owned Relay UI is not running')
  record=ui.read(state/'private/ui/process.json');assert '-I' in record['identity']['command'].split('\0') and str(ui.CODE.parent) in record['identity']['command'].split('\0');out['passed']['owned_isolated_source_bootstrap']={'url':info['url'],'trusted_import_root':True,'isolated_flag':True}
  browser=Browser(B/'evidence');b=browser;b.command('/url',{'url':base+'/'});b.wait('return !!document.querySelector("#login-form")');b.js('document.querySelector("#login-username").value=arguments[0];document.querySelector("#login-password").value=arguments[1];document.querySelector("#login-form").requestSubmit();return true;',c['username'],c['password']);b.wait('return document.querySelectorAll("[data-page]").length===8');b.js('location.hash="receive";return true;');b.wait('return document.querySelector("#main h1")?.textContent==="Receive and continue"');b.wait('return Array.from(document.querySelectorAll("a[href]")).some(e=>e.getAttribute("href")?.startsWith("/software/")&&e.textContent==="Download Relay software kit")');assert b.js('return Array.from(document.querySelectorAll("a[href]")).some(e=>e.getAttribute("href")?.startsWith("/software/")&&e.textContent==="Download software checksums")');out['passed']['software_kit_and_checksum_controls_visible']=True
  b.mobile();b.js('Array.from(document.querySelectorAll("a")).find(e=>e.textContent==="Download Relay software kit").scrollIntoView({block:"center"});return true;');layout=b.js('return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth}');assert layout['width']==360 and layout['scrollWidth']<=360;out['passed']['software_controls_mobile_layout']=layout;b.screenshot('software-kit-mobile')
  op=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  with op.open(urllib.request.Request(base+'/api/login',data=json.dumps({k:c[k] for k in ['username','password']}).encode(),headers={'Content-Type':'application/json','Origin':base}),timeout=20) as r:auth=json.load(r)
  with op.open(base+'/api/data',timeout=20) as r:inventory=json.load(r)
  for name in ['genesis-relay-software-0.1.0.zip','SHA256SUMS']:
   asset=next(a for a in inventory['software'] if a['name']==name);h=hashlib.sha256();count=0
   with op.open(base+'/software/'+asset['id'],timeout=40) as r:
    for chunk in iter(lambda:r.read(1024*1024),b''):h.update(chunk);count+=len(chunk)
   assert h.hexdigest()==ui.file_digest(asset['path']) and count==asset['size'];out['passed']['authenticated_download_'+name]={'url':base+'/software/'+asset['id'],'bytes':count,'sha256':h.hexdigest(),'matches_current_owned_file':True}
  with op.open(urllib.request.Request(base+'/api/logout',data=b'{}',headers={'Content-Type':'application/json','Origin':base,'X-CSRF-Token':auth['csrf']}),timeout=10) as r:r.read()
 except Exception as error:out['failed']['targeted_software_regression']=type(error).__name__+': '+str(error)[:1000]
 finally:
  if browser:browser.close()
  out['finished_at']=ui.now();out['source_hashes']={str(p.relative_to(B)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [B/'src/genesis_relay/ui.py',B/'src/genesis_relay/web/app.js']};out['packaging_note']='This check proves the visible routes and byte identity to the current owned files. Final distribution/checksum consistency is verified by the packaging acceptance evidence.';(B/'evidence/ui-bootstrap-regression.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'passed':len(out['passed']),'failed':len(out['failed'])}),flush=True)
 return bool(out['failed'])

if __name__=='__main__':
 if '--software-browser' in sys.argv:raise SystemExit(software_browser_regression())
 if '--browser' in sys.argv:raise SystemExit(browser_acceptance())
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(UITests));record={'checked_at':ui.now(),'passed':result.testsRun-len(result.failures)-len(result.errors),'failed':len(result.failures)+len(result.errors),'scope':'Isolated temporary HTTP server, synthetic capsule stream, mocked fixed background action; source laboratory untouched.','failures':[str(t)+': '+s for t,s in result.failures+result.errors]};(B/'evidence/ui-unit-tests.json').write_text(json.dumps(record,indent=2)+'\n');raise SystemExit(not result.wasSuccessful())
