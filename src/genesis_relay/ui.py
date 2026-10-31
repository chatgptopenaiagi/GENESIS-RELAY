"""Authenticated, loopback-only human interface for private continuation capsules.

The UI never accepts arbitrary server file paths or program strings from a
browser. Source and local receiving roots come only from trusted startup options.
"""
from __future__ import annotations
import argparse,base64,contextlib,datetime,hashlib,hmac,html,json,mimetypes,os,re,secrets,signal,socket,subprocess,sys,threading,time,urllib.request
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote,urlsplit
from .common import module_command
CODE=Path(__file__).resolve().parent;LOCK=threading.RLock();ACTION_LOCK=threading.Lock();ACTIVE=None
ASSETS={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
DEFAULT_SOURCE=None

def workspace_root():
 # Editable checkout, frozen distribution, or the installed package itself.
 candidate=CODE.parents[1]
 if (candidate/'pyproject.toml').is_file() and (candidate/'src/genesis_relay').resolve()==CODE.resolve():return candidate
 if getattr(sys,'frozen',False):return Path(sys.executable).resolve().parent
 return CODE

def source_root(state,value=None):
 if value:return Path(value).expanduser().absolute()
 configured=read(Path(state)/'private/ui/config.json').get('source')
 if configured:return Path(configured).expanduser().absolute()
 from . import demo
 return Path(demo.prepare(state)['source_root'])
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def file_digest(path):
 digest=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):digest.update(block)
 return digest.hexdigest()
def root_dir(value=None):return Path(value or os.environ.get('GENESIS_RELAY_HOME') or Path.home()/'.local/state/genesis-relay').expanduser().absolute()
def read(path,default=None):
 try:return json.loads(Path(path).read_text())
 except (OSError,ValueError):return {} if default is None else default

def atomic(path,value,mode=0o600):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);temp=path.with_name('.'+path.name+'-'+secrets.token_hex(8)+'.partial')
 with temp.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 temp.chmod(mode);os.replace(temp,path)
def setup(state):
 state=Path(state);state.mkdir(parents=True,exist_ok=True,mode=0o700);state.chmod(0o700)
 for name in ['private/ui','ui-jobs','capsules','receiving','ui-evidence','outgoing']:(state/name).mkdir(parents=True,exist_ok=True,mode=0o700)

def credentials(state):
 setup(state);path=Path(state)/'private/ui/access.json'
 with LOCK:
  if not path.exists():
   pw=secrets.token_urlsafe(24);salt=secrets.token_hex(16);atomic(path,{'username':'genesis','password':pw,'salt':salt,'hash':hashlib.pbkdf2_hmac('sha256',pw.encode(),salt.encode(),120000).hex()})
  path.chmod(0o600);return read(path)
def valid(state,user,password):
 c=credentials(state)
 try:return isinstance(user,str) and isinstance(password,str) and len(password)<=256 and hmac.compare_digest(user.encode(),c['username'].encode()) and hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',password.encode(),c['salt'].encode(),120000).hex(),c['hash'])
 except (ValueError,KeyError):return False

@contextlib.contextmanager
def file_lock(path,seconds=15):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('a+b') as f:
  if os.name=='nt':
   import msvcrt
   if f.seek(0,2)==0:f.write(b'0');f.flush()
   def acquire():f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
   def release():f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
  else:
   import fcntl
   def acquire():fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   def release():fcntl.flock(f,fcntl.LOCK_UN)
  end=time.monotonic()+seconds
  while True:
   try:acquire();break
   except (OSError,BlockingIOError):
    if time.monotonic()>end:raise RuntimeError('Another Relay UI lifecycle operation is active.')
    time.sleep(.1)
  try:yield
  finally:release()

def identity(pid):
 try:
  pid=int(pid)
  if pid<=0:return {}
  if os.name=='nt':
   command='$p=Get-CimInstance Win32_Process -Filter "ProcessId = '+str(pid)+'"; if($p){$p | Select-Object ProcessId,CreationDate,CommandLine | ConvertTo-Json -Compress}'
   binary=__import__('shutil').which('pwsh') or __import__('shutil').which('powershell')
   if not binary:return {}
   result=subprocess.run([binary,'-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,timeout=7)
   item=json.loads(result.stdout);return {'pid':pid,'start':str(item['CreationDate']),'command':item['CommandLine']}
  p=Path('/proc')/str(pid);fields=(p/'stat').read_text().rsplit(')',1)[1].split();args=[x.decode(errors='replace') for x in (p/'cmdline').read_bytes().split(b'\0') if x]
  return {'pid':pid,'start':fields[19],'command':'\0'.join(args)} if args else {}
 except (OSError,ValueError,IndexError,KeyError,subprocess.SubprocessError):return {}
def owned(record):
 info=identity(record.get('pid',0));return bool(info and info==record.get('identity') and 'genesis_relay.ui' in info.get('command','') and 'serve' in info.get('command',''))
def live(record):
 if not owned(record):return False
 try:
  op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
  with op.open(record['url']+'api/session',timeout=3) as response:return response.status==200 and isinstance(json.load(response).get('authenticated'),bool)
 except (OSError,ValueError,KeyError):return False

def capsule_paths(state):
 state=Path(state);paths=[]
 for folder in [state/'capsules']:
  if folder.is_dir():paths.extend(p for p in folder.glob('*.zip') if p.is_file() and not p.is_symlink())
 # A receiver keeps an immutable copy in its own owned area. No arbitrary path is accepted from the browser.
 for folder in [state/'receiving/incoming',state/'incoming']:
  if folder.is_dir():paths.extend(p for p in folder.glob('*.zip') if p.is_file() and not p.is_symlink())
 if not paths:
  # A receiver can work from its unchanged kept capsule, without the sender's
  # directory or a second incoming copy. Only the documented owned layout is read.
  for folder in [state/'capsules',state/'receiving/capsules']:
   if folder.is_dir() and not folder.is_symlink():paths.extend(p for p in folder.glob('*/capsule.zip') if p.is_file() and not p.is_symlink() and not p.parent.is_symlink())
 return sorted(set(p.absolute() for p in paths),key=lambda p:p.stat().st_mtime,reverse=True)
def capsule_identifier(path):return hashlib.sha256(str(Path(path).absolute()).encode()).hexdigest()[:24]
def find_capsule(state,ident):
 if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{24}',ident):raise ValueError('Choose a known capsule from this Relay workspace.')
 path=next((p for p in capsule_paths(state) if capsule_identifier(p)==ident),None)
 if not path:raise ValueError('Capsule is not in this Relay workspace.')
 return path

def summary_of_capsule(path,verified=None):
 result={'id':capsule_identifier(path),'filename':path.name,'size':path.stat().st_size,'path':str(path),'stage':'AVAILABLE_TO_INSPECT','label':'Available to inspect','verified':False}
 if verified:
  metadata=verified.get('capsule',verified.get('metadata',{}));manifest=verified.get('manifest',{});completeness=verified.get('completeness',{});entries=manifest.get('entries',[]) if isinstance(manifest,dict) else []
  result.update(capsule_id=metadata.get('capsule_id'),project_name=metadata.get('project_name','Engineering project'),stage='VERIFIED_FOR_TRANSFER',label='Integrity verified · transport pending',verified=True,completeness=completeness,entry_count=len(entries),dependencies=metadata.get('dependencies',[]),mode=metadata.get('mode','full'),knowledge=verified.get('knowledge',{}),entries=[{k:x.get(k) for k in ['path','root_id','type','disposition','size','reason']} for x in entries],limitations=metadata.get('limitations',[]))
 return result

def cached_capsule(state,path):
 cache=Path(state)/'ui-evidence'/('capsule-'+capsule_identifier(path)+'.json');record=read(cache);signature=[path.stat().st_size,path.stat().st_mtime_ns]
 return record.get('summary') if record.get('signature')==signature else None
def remember_capsule(state,path,result):
 summary=summary_of_capsule(path,result);summary['archive_sha256']=file_digest(path);signature=[path.stat().st_size,path.stat().st_mtime_ns];atomic(Path(state)/'ui-evidence'/('capsule-'+summary['id']+'.json'),{'signature':signature,'summary':summary});return summary

def jobs(state):
 return sorted([read(p) for p in (Path(state)/'ui-jobs').glob('*.json')],key=lambda j:j.get('created_at',''),reverse=True)
def receipts(state):
 records=[]
 for folder in [Path(state)/'receiving/receipts',Path(state)/'receipts']:
  if folder.is_dir():
   for p in folder.glob('*.json'):
    item=read(p)
    if item and item.get('capsule_id') and item.get('project_path') and item.get('receipt_path'):item['receipt_name']=p.name;records.append(item)
 return records

SERVICE_CACHE={}
def owned_services(source,records):
 key=(str(source),tuple(r.get('project_path') for r in records));cached=SERVICE_CACHE.get(key)
 if cached and cached['until']>time.monotonic():return cached['items']
 candidates=[];source=Path(source)
 try:
  pid=int((source/'runtime/lab.pid').read_text());info=identity(pid)
  if str(source/'server.py') in info.get('command','').split('\0'):candidates.append(('Original laboratory','http://127.0.0.1:8090/'))
 except (OSError,ValueError):pass
 for record in records:
  project=Path(record['project_path']);service=read(project/'_relay/service.json');config=read(project/'_relay/ADAPTATION.json');old=service.get('identity',{});actual=identity(service.get('pid',0));port=config.get('port')
  if actual and actual.get('start')==old.get('start') and actual.get('command')=='\0'.join(old.get('args',[])) and str(project/'server.py') in old.get('args',[]) and isinstance(port,int) and port in range(8140,8160) and config.get('url')=='http://127.0.0.1:'+str(port)+'/':candidates.append(('Reconstructed laboratory',config['url']))
 items=[];op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 for name,url in candidates:
  try:
   with op.open(url,timeout=2) as response:code=response.status
  except urllib.error.HTTPError as error:code=error.code
  except OSError:continue
  if code in [200,401]:items.append({'name':name,'url':url,'owned':True,'observed_at':now(),'http':code,'scope':'Process identity plus local HTTP; scientific correctness is separate.'})
 SERVICE_CACHE[key]={'until':time.monotonic()+10,'items':items};return items

def software_assets():
 workspace=workspace_root();items=[]
 windows=workspace/'windows' if (workspace/'windows').is_dir() else CODE/'windows'
 for folder in [workspace/'dist',windows]:
  if folder.is_dir():
   for p in sorted(folder.iterdir()):
    if p.is_file() and not p.is_symlink() and (p.suffix in ['.whl','.ps1'] or p.name.endswith('.tar.gz') or (p.name.startswith('GENESIS-RELAY-') and p.name.endswith('.zip')) or p.name in {'genesis-relay-software-0.1.0.zip','SHA256SUMS','SHA256SUMS.txt'}):items.append({'id':hashlib.sha256(str(p).encode()).hexdigest()[:24],'name':p.name,'size':p.stat().st_size,'path':str(p)})
 return items

def destination_reports(records):
 items=[]
 for receipt in records:
  project=Path(receipt['project_path']);path=project/'_relay/ACCEPTANCE-LATEST.json'
  sealed=receipt.get('acceptance_receipt_path') or receipt.get('acceptance_path')
  if sealed:
   candidate=Path(sealed)
   if candidate.parent.resolve()==Path(receipt['receipt_path']).parent.resolve() and not candidate.is_symlink():path=candidate
  report=read(path)
  if not report:continue
  if report.get('project_path')!=str(project) or report.get('source_capsule_id')!=receipt.get('capsule_id') or report.get('source_capsule_sha256')!=receipt.get('archive_sha256') or report.get('route')!=receipt.get('route'):continue
  if not isinstance(report.get('started_at'),str) or report['started_at']<receipt.get('restored_at',receipt.get('received_at','')):continue
  # This is a recorded destination observation, not authority to execute code or
  # promote the receiver's independent persisted readiness state.
  items.append({k:report.get(k) for k in ['status','scope','route','started_at','finished_at','destination','passed','failed','skipped','receipt_path','project_path','new_run_ids']})
 return items

def data_view(state,source):
 state=Path(state);source=Path(source);items=[]
 for path in capsule_paths(state):items.append(cached_capsule(state,path) or summary_of_capsule(path))
 plan=read(state/'ui-evidence/plan.json');discovery=read(state/'ui-evidence/discovery.json')
 evidence=[]
 # Only trusted Relay root reports, never arbitrary path query parameters or source private files.
 workspace=workspace_root()
 for folder in [workspace,workspace/'evidence',state/'ui-evidence',state/'receiving/receipts',state/'receipts']:
  if folder.is_dir():
   for p in sorted(folder.glob('*')):
    if p.is_file() and not p.is_symlink() and p.suffix in ['.md','.json'] and p.stat().st_size<=4_000_000 and p.name not in ['access.json','sessions.json']:
     evidence.append({'id':hashlib.sha256(str(p).encode()).hexdigest()[:24],'title':p.name,'path':str(p)})
 registry=read(state/'ui-evidence/registry.json');evidence.extend(registry.get('reports',[]))
 returns=[read(p) for p in sorted((state/'ui-evidence').glob('return-created-*.json'))];received=receipts(state)
 from . import demo
 for record in received:record['is_demo_project']=demo.is_demo(record['project_path'])
 platform={'system':sys.platform,'machine':__import__('platform').machine(),'windows_native':'NOT_OBSERVED_ON_THIS_HOST','windows_wsl':'NOT_OBSERVED_ON_THIS_HOST','fresh_windows_codex':'NOT_RUN'}
 for record in received:
  if record.get('ready_to_continue') and record.get('is_demo_project'):
   if record.get('route')=='NATIVE_WINDOWS_X64' and os.name=='nt':platform['windows_native']='SYNTHETIC_DEMO_PASSED_ON_THIS_HOST'
   if record.get('route')=='WSL_LINUX_X64':platform['windows_wsl']='SYNTHETIC_DEMO_PASSED_ON_THIS_HOST'
 return {'source':{'name':source.name,'path':str(source),'available':source.is_dir(),'is_demo':demo.is_demo(source),'description':'Synthetic laboratory with invented data, saved results and a continuation task. No scientific stack or AI account is required.' if demo.is_demo(source) else 'Your selected project, its saved work and the engineering letter needed to continue elsewhere.'},'plan':plan,'discovery':discovery,'capsules':items,'jobs':jobs(state),'source_history':read(state/'registry.json',{}).get('history',[]),'receipts':received,'returns':returns,'destination_reports':destination_reports(received),'services':owned_services(source,received),'software':software_assets(),'reports':evidence,'active_job':ACTIVE,'platform':platform,'transfer_note':'A download is a local export, not a destination receipt or successful reconstruction.','ui':{'state_dir':str(state),'source':str(source)}}

def do_action(state,source,action,ident=None):
 state=Path(state);source=Path(source)
 config=read(state/'private/ui/config.json');sentinel=config.get('sentinel_root')
 if action=='discover':
  from . import discovery
  value=discovery.discover(source,mode='full');atomic(state/'ui-evidence/discovery.json',value);return {'message':'Project discovery completed. Review the selected roots and entry accounting.','result':value}
 if action=='plan':
  from . import capsule
  value=capsule.plan(source,mode='full',sentinel_root=sentinel);atomic(state/'ui-evidence/plan.json',value);return {'message':'Full-continuation plan is ready. No export or destination changes were made.','result':value}
 if action=='export':
  from . import capsule
  value=capsule.export(source,state_dir=state,mode='full',sentinel_root=sentinel);path=Path(value.get('archive') or value.get('path'));verification=capsule.verify(path);summary=remember_capsule(state,path,verification);return {'message':'Private capsule built and verified. Transport remains pending until a receiver records a receipt.','result':{**value,'ui_id':summary['id']}}
 if action in ['verify','inspect','receive_plan','restore','verify_restore','return_create','demo_accept','demo_return']:
  path=find_capsule(state,ident)
  if action in ['verify','inspect']:
   from . import capsule
   value=capsule.verify(path);summary=remember_capsule(state,path,value);return {'message':'Capsule integrity and manifests checked. Inspection did not execute capsule code.','result':{'capsule_id':summary.get('capsule_id'),'ui_id':summary['id'],'entry_count':summary.get('entry_count')}}
  from . import receiver
  destination=state/'receiving'
  if action in ['return_create','demo_return','demo_accept']:
   from . import capsule,returns,demo
   capsule_id=capsule.verify(path)['capsule']['capsule_id'];match=next((r for r in receipts(state) if r.get('capsule_id')==capsule_id),None)
   if not match:raise ValueError('Restore this capsule before creating a return letter.')
   receipt_path=Path(match.get('receipt_path') or destination/'receipts'/(capsule_id+'.json'))
   if action=='demo_accept':
    if not demo.is_demo(match['project_path']):raise ValueError('Demo acceptance is available only for the known synthetic demonstration; generic projects need reviewed tests.')
    value=demo.accept_demo(receipt_path);return {'message':'Synthetic demo acceptance completed. Read the recorded checks; this does not qualify arbitrary scientific applications.','result':value}
   output=state/'outgoing'/('return-'+secrets.token_hex(10)+'.zip')
   value=demo.change_and_return(receipt_path,output) if action=='demo_return' else returns.create_return(receipt_path,output);record={**value,'created_at':now(),'base_capsule_id':capsule_id};atomic(state/'ui-evidence'/('return-created-'+str(value['return_id'])+'.json'),record);return {'message':'Return capsule created from the recorded adaptation baseline. Apply it only after a three-way preview on the sender.','result':record}
  if action=='receive_plan':value=receiver.plan(path,destination,route='LOCAL_LINUX' if os.name!='nt' else 'NATIVE_WINDOWS_X64');message='Restoration plan prepared. No code executed and no dependencies installed.'
  elif action=='restore':
   from . import capsule,demo
   entries=capsule.verify(path)['manifest']['entries'];known={name:file_digest(demo.RESOURCE/name) for name in ['DEMO-PROJECT.json','experiment.py']}
   profile=all(any(e.get('path')==name and e.get('sha256')==digest and e.get('disposition')=='INCLUDED_EXACT' for e in entries) for name,digest in known.items())
   route='LOCAL_LINUX' if os.name!='nt' else 'NATIVE_WINDOWS_X64'
   value=demo.restore_demo(path,destination,route=route) if profile else receiver.restore(path,destination,route=route);message='Restored into a new Relay-owned directory. Run supported acceptance separately; extraction alone is not readiness.'
  else:
   matches=[r for r in receipts(state) if r.get('capsule_id')==__import__('genesis_relay.capsule',fromlist=['verify']).verify(path)['capsule']['capsule_id']]
   if not matches:raise ValueError('Restore this capsule before verifying its working copy.')
   value=receiver.verify_restoration(matches[0]);message='Restored-file checks completed; see the receipt for scientific acceptance scope.'
  atomic(state/'ui-evidence'/('receiver-'+action+'-'+ident+'.json'),value);return {'message':message,'result':value}
 raise ValueError('Unsupported Relay action.')

def worker(state,source,job):
 global ACTIVE
 try:
  job.update(status='running',started_at=now(),message='Working on this project only. Existing source and unrelated services are preserved.');atomic(Path(state)/'ui-jobs'/(job['id']+'.json'),job)
  try:value=do_action(state,source,job['action'],job.get('capsule_id'));job.update(status='succeeded',**value)
  except Exception as error:job.update(status='failed',message=str(error)[:1200],error_type=type(error).__name__)
  job['finished_at']=now();atomic(Path(state)/'ui-jobs'/(job['id']+'.json'),job)
 finally:ACTIVE=None;ACTION_LOCK.release()
def start_action(state,source,action,ident=None):
 global ACTIVE
 if action not in ['discover','plan','export','verify','inspect','receive_plan','restore','verify_restore','return_create','demo_accept','demo_return']:raise ValueError('Choose a supported Relay action.')
 if action in ['verify','inspect','receive_plan','restore','verify_restore','return_create','demo_accept','demo_return']:find_capsule(state,ident)
 if not ACTION_LOCK.acquire(blocking=False):raise RuntimeError('A Relay operation is already running. Wait until it finishes.')
 job={'id':secrets.token_hex(12),'action':action,'capsule_id':ident,'status':'queued','created_at':now(),'message':'Operation queued.'}
 try:ACTIVE=job['id'];atomic(Path(state)/'ui-jobs'/(job['id']+'.json'),job);threading.Thread(target=worker,args=(state,source,job),daemon=False).start();return job
 except BaseException:ACTIVE=None;ACTION_LOCK.release();raise

class Handler(BaseHTTPRequestHandler):
 server_version='GenesisRelayLocal'
 def setup(self):super().setup();self.connection.settimeout(20)
 def log_message(self,*args):pass
 @property
 def state(self):return self.server.relay_state
 @property
 def source(self):return self.server.relay_source
 @property
 def url(self):return self.server.relay_url
 def send(self,code,body,kind='application/json; charset=utf-8',extra=None):
  if not isinstance(body,bytes):body=(body if isinstance(body,str) else json.dumps(body,ensure_ascii=False,allow_nan=False)).encode()
  self.send_response(code)
  headers={'Content-Type':kind,'Content-Length':str(len(body)),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"};headers.update(extra or {})
  for name,value in headers.items():self.send_header(name,value)
  self.end_headers()
  try:self.wfile.write(body)
  except (BrokenPipeError,ConnectionResetError):pass
 def local(self):
  if self.client_address[0]!='127.0.0.1' or self.headers.get('Host') not in [urlsplit(self.url).netloc,'localhost:'+str(self.server.server_port)]:self.send(403,{'error':'Local Relay access only.'});return False
  path=unquote(urlsplit(self.path).path)
  if '..' in path.split('/') or '\\' in path:self.send(404,{'error':'Page not found.'});return False
  return True
 def session(self):
  try:c=SimpleCookie(self.headers.get('Cookie',''));token=c.get('genesis_relay');token=token.value if token else ''
  except Exception:return None
  if not token or len(token)>128:return None
  with LOCK:item=read(self.state/'private/ui/sessions.json').get(hashlib.sha256(token.encode()).hexdigest())
  return item if item and item.get('expires',0)>time.time() else None
 def require(self):
  s=self.session()
  if s:return s
  self.send(401,{'error':'Sign in to your private Relay workspace.'});return None
 def body(self):
  try:
   count=int(self.headers.get('Content-Length','0'))
   if not 0<count<=4096 or not self.headers.get('Content-Type','').startswith('application/json'):raise ValueError()
   value=json.loads(self.rfile.read(count),parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
   if not isinstance(value,dict):raise ValueError()
   return value
  except (ValueError,TypeError,UnicodeError):self.send(400,{'error':'Send a JSON object of at most 4096 bytes.'});return None
 def origin(self):
  if self.headers.get('Origin') not in [self.url.rstrip('/'),'http://localhost:'+str(self.server.server_port)]:self.send(403,{'error':'Origin rejected. Reload the local Relay page.'});return False
  return True
 def do_GET(self):
  if not self.local():return
  path=urlsplit(self.path).path
  if path in ASSETS:
   name,kind=ASSETS[path];return self.send(200,(CODE/'web'/name).read_bytes(),kind)
  if path=='/api/session':
   s=self.session();return self.send(200,{'authenticated':bool(s),'csrf':s.get('csrf') if s else None,'active_job':ACTIVE,'url':self.url})
  s=self.require()
  if not s:return
  if path=='/api/data':
   data=data_view(self.state,self.source);data['csrf']=s['csrf'];return self.send(200,data)
  if path.startswith('/api/jobs/'):
   ident=path.removeprefix('/api/jobs/')
   if not re.fullmatch('[a-f0-9]{24}',ident):return self.send(404,{'error':'Operation not found.'})
   job=read(self.state/'ui-jobs'/(ident+'.json'));return self.send(200 if job else 404,job or {'error':'Operation not found.'})
  if path.startswith('/download/') and path.endswith('.zip'):
   try:archive=find_capsule(self.state,path.removeprefix('/download/').removesuffix('.zip'));return self.download(archive)
   except ValueError as error:return self.send(404,{'error':str(error)})
  if path.startswith('/return-download/') and path.endswith('.zip'):
   ident=path.removeprefix('/return-download/').removesuffix('.zip')
   if not re.fullmatch('[A-Za-z0-9_-]{1,100}',ident):return self.send(404,{'error':'Return capsule not found.'})
   record=read(self.state/'ui-evidence'/('return-created-'+ident+'.json'));archive=Path(record.get('path','/nonexistent'))
   if archive.parent.resolve()!=(self.state/'outgoing').resolve() or archive.is_symlink() or not archive.is_file() or file_digest(archive)!=record.get('sha256'):return self.send(404,{'error':'Return capsule is absent or changed.'})
   return self.download(archive,{'verified':True,'archive_sha256':record['sha256']})
  if path.startswith('/software/'):
   ident=path.removeprefix('/software/');item=next((a for a in software_assets() if a['id']==ident),None)
   if not item:return self.send(404,{'error':'Software asset not found.'})
   p=Path(item['path']);return self.send(200,p.read_bytes(),'application/octet-stream',{'Content-Disposition':'attachment; filename="'+re.sub('[^A-Za-z0-9_.-]','_',p.name)+'"'})
  if path.startswith('/reports/'):
   ident=path.removeprefix('/reports/');report=next((r for r in data_view(self.state,self.source)['reports'] if r['id']==ident),None)
   if not report:return self.send(404,{'error':'Report not found.'})
   p=Path(report['path'])
   if p.is_symlink() or not p.is_file() or p.stat().st_size>4_000_000:return self.send(404,{'error':'Report not found.'})
   doc='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(report['title'])+' · Relay</title><link rel="stylesheet" href="/style.css"><body class="report-page"><main><a href="/">← Relay</a><h1>'+html.escape(report['title'])+'</h1><pre>'+html.escape(p.read_text(errors='replace'))+'</pre></main></body></html>'
   return self.send(200,doc,'text/html; charset=utf-8')
  return self.send(404,{'error':'Page not found.'})
 def download(self,path,cached=None):
  cached=cached or cached_capsule(self.state,path)
  if not cached or not cached.get('verified'):return self.send(409,{'error':'Verify this capsule in Relay before downloading it.'})
  digest=file_digest(path)
  if digest!=cached.get('archive_sha256'):return self.send(409,{'error':'Capsule bytes changed after verification. Verify again before downloading.'})
  size=path.stat().st_size;start=0;end=size-1;partial=False
  etag='"'+digest+'"';value=self.headers.get('Range')
  if self.headers.get('If-Range') and self.headers['If-Range']!=etag:value=None
  if value:
   match=re.fullmatch(r'bytes=(\d+)-(\d*)',value)
   if not match:return self.send(416,b'',extra={'Content-Range':'bytes */'+str(size)})
   start=int(match[1]);end=min(int(match[2]) if match[2] else size-1,size-1)
   if start>=size or start>end:return self.send(416,b'',extra={'Content-Range':'bytes */'+str(size)})
   partial=True
  self.send_response(206 if partial else 200)
  headers={'Content-Type':'application/zip','Content-Length':str(end-start+1),'Content-Disposition':'attachment; filename="'+re.sub('[^A-Za-z0-9_.-]','_',path.name)+'"','Accept-Ranges':'bytes','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','ETag':etag}
  if partial:headers['Content-Range']='bytes '+str(start)+'-'+str(end)+'/'+str(size)
  for k,v in headers.items():self.send_header(k,v)
  self.end_headers();sent=0
  try:
   with path.open('rb') as f:
    f.seek(start)
    while sent<end-start+1:
     chunk=f.read(min(1024*1024,end-start+1-sent))
     if not chunk:break
     self.wfile.write(chunk);sent+=len(chunk)
  except (BrokenPipeError,ConnectionResetError):pass
  finally:
   with LOCK:
    log=self.state/'ui-evidence/downloads.jsonl'
    with log.open('a') as f:f.write(json.dumps({'at':now(),'capsule_ui_id':capsule_identifier(path),'bytes_sent':sent,'range':[start,end],'complete_request_bytes':sent==end-start+1,'meaning':'HTTP download observation only; not a destination receipt or transport completion.'})+'\n')
 def do_POST(self):
  if not self.local() or not self.origin():return
  path=urlsplit(self.path).path;body=self.body()
  if body is None:return
  if path=='/api/login':
   fail=self.server.auth_failures
   if fail['until']>time.time():return self.send(429,{'error':'Wait 30 seconds before trying to sign in again.'})
   if set(body)!={'username','password'} or not valid(self.state,body.get('username'),body.get('password')):
    fail['count']+=1
    if fail['count']>=8:fail.update(count=0,until=time.time()+30)
    return self.send(401,{'error':'Username or password was not accepted.'})
   fail['count']=0;token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
   with LOCK:
    sessions={k:v for k,v in read(self.state/'private/ui/sessions.json').items() if v.get('expires',0)>time.time()};sessions=dict(list(sessions.items())[-31:]);sessions[hashlib.sha256(token.encode()).hexdigest()]={'csrf':csrf,'expires':time.time()+43200,'created_at':now()};atomic(self.state/'private/ui/sessions.json',sessions)
   return self.send(200,{'authenticated':True,'csrf':csrf},extra={'Set-Cookie':'genesis_relay='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200'})
  s=self.require()
  if not s:return
  if not hmac.compare_digest(self.headers.get('X-CSRF-Token','').encode(),s['csrf'].encode()):return self.send(403,{'error':'Security token rejected. Reload Relay.'})
  if path=='/api/logout':
   try:
    c=SimpleCookie(self.headers.get('Cookie',''));token=c.get('genesis_relay');key=hashlib.sha256(token.value.encode()).hexdigest() if token else ''
    with LOCK:sessions=read(self.state/'private/ui/sessions.json');sessions.pop(key,None);atomic(self.state/'private/ui/sessions.json',sessions)
   except Exception:pass
   return self.send(200,{'authenticated':False},extra={'Set-Cookie':'genesis_relay=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
  if path=='/api/action':
   if set(body)-{'action','capsule_id'} or not isinstance(body.get('action'),str):return self.send(400,{'error':'Choose a supported Relay action.'})
   try:return self.send(202,start_action(self.state,self.source,body['action'],body.get('capsule_id')))
   except ValueError as e:return self.send(400,{'error':str(e)})
   except RuntimeError as e:return self.send(409,{'error':str(e)})
  return self.send(404,{'error':'Action not found.'})

class Server(ThreadingHTTPServer):
 daemon_threads=True;allow_reuse_address=True;request_queue_size=8
 slots=threading.BoundedSemaphore(12)
 def process_request(self,request,client_address):
  if not self.slots.acquire(blocking=False):request.close();return
  try:super().process_request(request,client_address)
  except BaseException:self.slots.release();raise
 def process_request_thread(self,request,client_address):
  try:super().process_request_thread(request,client_address)
  finally:self.slots.release()

def serve(state,source,port):
 setup(state);credentials(state)
 with file_lock(Path(state)/'private/ui/server.lock',seconds=.5):
  for path in (Path(state)/'ui-jobs').glob('*.json'):
   item=read(path)
   if item.get('status') in ['queued','running']:item.update(status='failed',finished_at=now(),message='Relay UI restarted before this action completed. Inspect preserved partial/core state before retrying.');atomic(path,item)
  server=Server(('127.0.0.1',port),Handler);server.relay_state=Path(state);server.relay_source=Path(source);server.relay_url='http://127.0.0.1:'+str(port)+'/';server.auth_failures={'count':0,'until':0}
  def shutdown(signum,frame):raise SystemExit(0)
  signal.signal(signal.SIGTERM,shutdown)
  if hasattr(signal,'SIGINT'):signal.signal(signal.SIGINT,shutdown)
  try:server.serve_forever()
  finally:server.server_close()

def status(state):
 record=read(Path(state)/'private/ui/process.json');return {'url':record.get('url'),'state':'RUNNING' if live(record) else 'UNKNOWN' if owned(record) else 'STOPPED','owned':owned(record),'source':record.get('source'),'observed_at':now(),'state_dir':str(state)}
def start(state,source,preferred=8120,sentinel_root=None):
 setup(state);record=read(Path(state)/'private/ui/process.json')
 config=read(Path(state)/'private/ui/config.json')
 if live(record) and record.get('source')!=str(source):raise RuntimeError('The running UI uses a different source. Restart explicitly to switch projects.')
 if sentinel_root is not None:
  sentinel_root=Path(sentinel_root).expanduser().absolute()
  if not sentinel_root.is_dir():raise RuntimeError('Configured Sentinel root does not exist.')
  atomic(Path(state)/'private/ui/config.json',{'source':str(source),'sentinel_root':str(sentinel_root)})
 elif not config:atomic(Path(state)/'private/ui/config.json',{'source':str(source),'sentinel_root':None})
 if live(record):return status(state)
 if owned(record):raise RuntimeError('Owned Relay UI is not ready; inspect private/ui/server.log. No duplicate started.')
 port=None
 for candidate in range(preferred,min(preferred+20,65536)):
  with socket.socket() as sock:
   sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
   try:sock.bind(('127.0.0.1',candidate));port=candidate;break
   except OSError:continue
 if port is None:raise RuntimeError('No free local Relay port; no existing service was stopped.')
 credentials(state);log=Path(state)/'private/ui/server.log';env=os.environ.copy()
 kwargs={'start_new_session':True} if os.name!='nt' else {'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP}
 # -I intentionally ignores cwd/PYTHONPATH. The already-loaded trusted package
 # supplies its own absolute import root for both source and wheel installations.
 argv=module_command('genesis_relay.ui','serve','--state-dir',str(state),'--source',str(source),'--port',str(port))
 with log.open('ab') as out:log.chmod(0o600);child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=out,stderr=out,env=env,**kwargs)
 record={'pid':child.pid,'url':'http://127.0.0.1:'+str(port)+'/','source':str(source),'started_at':now()}
 for _ in range(40):
  info=identity(child.pid)
  if 'genesis_relay.ui' in info.get('command','') and 'serve' in info.get('command',''):record['identity']=info;break
  if child.poll() is not None:break
  time.sleep(.1)
 atomic(Path(state)/'private/ui/process.json',record)
 for _ in range(40):
  if live(record):return status(state)
  if child.poll() is not None:break
  time.sleep(.25)
 raise RuntimeError('Relay UI startup failed; inspect private/ui/server.log.')
def stop(state):
 record=read(Path(state)/'private/ui/process.json')
 if owned(record):
  if any(j.get('status') in ['queued','running'] for j in jobs(state)):raise RuntimeError('A Relay operation is active; wait before stopping its UI.')
  if os.name=='nt':os.kill(record['pid'],signal.SIGTERM)
  else:os.killpg(record['pid'],signal.SIGTERM)
  for _ in range(40):
   if not owned(record):break
   time.sleep(.15)
  if owned(record):raise RuntimeError('Owned Relay UI is still stopping; no force kill sent.')
 elif identity(record.get('pid',0)):raise RuntimeError('Recorded PID now belongs to another process. Nothing stopped.')
 return status(state)
def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['start','stop','restart','status','access','serve']);parser.add_argument('--state-dir');parser.add_argument('--source');parser.add_argument('--sentinel-root');parser.add_argument('--port',type=int,default=8120);args=parser.parse_args(argv)
 if not 1024<=args.port<=65516:parser.error('Choose a nonprivileged port with room for fallback.')
 state=root_dir(args.state_dir);source=source_root(state,args.source) if args.command in ['start','restart','serve'] else None
 if args.command=='serve':serve(state,source,args.port);return 0
 setup(state)
 with file_lock(state/'private/ui/lifecycle.lock'):
  if args.command=='access':
   if not sys.stdout.isatty():raise SystemExit('Access requires an operator terminal; credentials are not written to logs.')
   record=status(state);c=credentials(state);print((record.get('url') or 'Start Relay UI first')+'\nUsername: '+c['username']+'\nPassword: '+c['password']);return 0
  try:
   if args.command=='start':result=start(state,source,args.port,args.sentinel_root)
   elif args.command=='restart':stop(state);result=start(state,source,args.port,args.sentinel_root)
   else:result=globals()[args.command](state)
   print(json.dumps(result,indent=2));return 0
  except RuntimeError as error:raise SystemExit(str(error))
if __name__=='__main__':raise SystemExit(main())
