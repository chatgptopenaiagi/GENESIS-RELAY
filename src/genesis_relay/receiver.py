"""Trusted, non-executing capsule receipt and new-directory materialization.

The immutable received ZIP is source evidence. Only its separate working copy is
adapted. Inspect/Plan never execute capsule code or install a dependency.
"""
from __future__ import annotations
import contextlib,datetime,hashlib,json,os,platform,re,shutil,sqlite3,subprocess,sys,tempfile,time,uuid,zipfile
from pathlib import Path,PurePosixPath

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def atomic(path,value):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_name('.'+p.name+'.'+uuid.uuid4().hex+'.partial')
 raw=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode() if not isinstance(value,(str,bytes)) else value.encode() if isinstance(value,str) else value
 try:
  with temp.open('xb') as f:temp.chmod(0o600);f.write(raw);f.flush();os.fsync(f.fileno())
  os.replace(temp,p)
 finally:temp.unlink(missing_ok=True)
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
@contextlib.contextmanager
def lock(root,seconds=10):
 root=Path(root);root.mkdir(parents=True,exist_ok=True,mode=0o700)
 with (root/'receiver.lock').open('a+b') as f:
  if os.name=='nt':
   import msvcrt
   if f.tell()==0:f.write(b'0');f.flush()
   end=time.monotonic()+seconds
   while True:
    try:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1);break
    except OSError:
     if time.monotonic()>end:raise RuntimeError('Another Relay receiver is active')
     time.sleep(.05)
   try:yield
   finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
  else:
   import fcntl
   end=time.monotonic()+seconds
   while True:
    try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);break
    except BlockingIOError:
     if time.monotonic()>end:raise RuntimeError('Another Relay receiver is active')
     time.sleep(.05)
   try:yield
   finally:fcntl.flock(f,fcntl.LOCK_UN)
def _verified(path):
 from . import capsule
 result=capsule.verify(Path(path))
 if not isinstance(result,dict):raise ValueError('Verifier did not return capsule data')
 meta=result.get('capsule',result.get('metadata',{}));manifest=result.get('manifest',{})
 entries=manifest.get('entries',[]) if isinstance(manifest,dict) else manifest
 if not isinstance(meta,dict) or not isinstance(entries,list):raise ValueError('Unsupported verified capsule schema')
 ident=meta.get('capsule_id','')
 if not isinstance(ident,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,100}',ident):raise ValueError('Unsafe capsule identity')
 return result,meta,entries

def _parts(path):
 if not isinstance(path,str) or '\0' in path or path.startswith('/') or not path:raise ValueError('Unsafe logical source path')
 parts=path.split('/')
 if any(p in ('','..','.') for p in parts):raise ValueError('Unsafe logical source path')
 return parts
_RESERVED={'CON','PRN','AUX','NUL','CLOCK$',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}
def windows_issue(path):
 parts=_parts(path)
 if len(path)>220:return 'long Windows working path'
 for p in parts:
  if any(ord(c)<32 for c in p) or any(c in p for c in '<>:"\\|?*'):return 'unsupported Windows filename/drive/ADS form'
  if p.endswith((' ','.')) or p.split('.')[0].upper() in _RESERVED:return 'reserved or trailing-dot Windows name'
 return None

def _safe_slug(value):
 name=re.sub('[^A-Za-z0-9_.-]+','-',str(value)).strip('.-')[:70]
 return name or 'project'

def destination_capabilities(python=None):
 # This is a destination observation, never copied source inventory.
 selected=str(python or (shutil.which('python3') or shutil.which('python') or '') if getattr(sys,'frozen',False) else python or sys.executable);same=not getattr(sys,'frozen',False) and Path(selected).resolve()==Path(sys.executable).resolve()
 return {'observed_at':now(),'system':platform.system(),'machine':platform.machine(),'receiver_executable':sys.executable,'receiver_runtime_inclusive':bool(getattr(sys,'frozen',False)),'receiver_python':sys.executable if not getattr(sys,'frozen',False) else None,'receiver_python_version':platform.python_version(),'python':selected,'python_version':platform.python_version() if same else None,'selected_interpreter_probe':'CURRENT_RECEIVER' if same else 'NOT_RUN; probe explicitly before environment reconstruction','git':shutil.which('git'),'pwsh':shutil.which('pwsh'),'wsl':shutil.which('wsl') if os.name=='nt' else None,'codex':shutil.which('codex'),'source_inventory_is_destination_inventory':False}

def inspect(capsule_path):
 result,meta,entries=_verified(capsule_path)
 dispositions={};types={};total=0
 for e in entries:
  dispositions[e.get('disposition','UNKNOWN')]=dispositions.get(e.get('disposition','UNKNOWN'),0)+1;types[e.get('type','unknown')]=types.get(e.get('type','unknown'),0)+1
  total+=e.get('size',0) if isinstance(e.get('size'),int) else 0
 return {'capsule':meta,'capsule_id':meta['capsule_id'],'archive_sha256':result.get('archive_sha256') or digest(capsule_path),'completeness':result.get('completeness',{}),'entries':len(entries),'dispositions':dispositions,'entry_types':types,'accounted_source_bytes':total,'knowledge':result.get('knowledge',{}),'inspection_executes_code':False,'transport_complete':False}

def _mapping(entries,meta,route):
 primary=(meta.get('roots') or [{'id':'project'}])[0].get('id','project');used={};mapping=[];is_windows=route in ['NATIVE_WINDOWS_X64','WSL_LINUX_X64']
 for index,e in enumerate(entries):
  path=e.get('path','');parts=_parts(path);root_id=str(e.get('root_id','project'));prefix='' if root_id==primary else '_relay/references/'+_safe_slug(root_id)+'/'
  target=prefix+path;reason=None
  if root_id==primary:
   checked=[part.casefold() for part in parts] if is_windows else parts;checked_path='/'.join(checked)
   if checked[0] in ['_relay','.relay-return-history'] or checked_path=='.relay-reconstruction.json' or checked[-1].endswith('.relay-partial'):
    target='_relay/source-tree/'+path;reason='Source entry collides with receiver-owned metadata/temporary namespace; preserved inertly with an explicit path mapping'
   elif checked[-1] in (['agents.md','agents.override.md'] if is_windows else ['AGENTS.md','AGENTS.override.md']) or checked_path==('start-here.md' if is_windows else 'START-HERE.md'):
    target='_relay/source-guidance/'+path;reason='Source guidance preserved separately; destination guidance is generated explicitly'
  if e.get('type')=='symlink':
   target='_relay/symlinks/'+hashlib.sha256((root_id+'\0'+path).encode()).hexdigest()[:24]+'.txt';reason='Source symlink preserved as inert target bytes; no link activated'
  windows_reason=windows_issue(target) if is_windows else None
  if windows_reason:reason=windows_reason;target=''
  if len(target)>3000:reason='destination path exceeds supported materialization limit'
  comparison=target.casefold() if is_windows else target
  needs_hash=not target or len(target)>3000 or comparison in used
  if comparison in used:reason='case-insensitive or duplicate logical path collision'
  if needs_hash:
   short=hashlib.sha256((root_id+'\0'+path).encode()).hexdigest()[:24]
   target='_relay/unmaterializable/'+short+('.link.txt' if e.get('type')=='symlink' else '.source')
   comparison=target.casefold() if is_windows else target
  if comparison in used:raise ValueError('Unresolvable materialization collision')
  used[comparison]=index
  mapping.append({'root_id':root_id,'source_path':path,'destination_path':target,'type':e.get('type'),'disposition':e.get('disposition'),'sha256':e.get('sha256'),'object':e.get('object'),'size':e.get('size',0),'mode':e.get('mode',0o644),'mtime_ns':e.get('mtime_ns'),'target':e.get('target'),'mapping_reason':reason})
 return mapping

def default_route():
 return 'NATIVE_WINDOWS_X64' if os.name=='nt' else 'LOCAL_LINUX'

def plan(capsule_path,destination_root,route=None,python=None):
 route=route or default_route()
 if route not in ['LOCAL_LINUX','NATIVE_WINDOWS_X64','WSL_LINUX_X64']:raise ValueError('Unknown restoration route')
 result,meta,entries=_verified(capsule_path);root=Path(destination_root).expanduser().absolute()
 if root.is_symlink():raise ValueError('Destination root must not be a symlink')
 mapping=_mapping(entries,meta,route);caps=destination_capabilities(python);blocked=[]
 if route=='NATIVE_WINDOWS_X64' and (os.name!='nt' or caps['machine'].lower() not in ['amd64','x86_64']):blocked.append('Native Windows x64 execution is not available in this process')
 if route=='WSL_LINUX_X64' and not (platform.system()=='Linux' and 'microsoft' in platform.release().lower() and caps['machine'].lower() in ['amd64','x86_64']):blocked.append('Run the WSL route inside an actual WSL Linux x64 environment')
 if route=='LOCAL_LINUX' and platform.system()!='Linux':blocked.append('LOCAL_LINUX requires an actual Linux runtime')
 bytes_needed=sum(e.get('size',0) for e in entries if e.get('disposition') in ['INCLUDED_EXACT','INCLUDED_TRANSFORMED'] and e.get('type')=='file')+Path(capsule_path).stat().st_size
 existing=root
 while not existing.exists() and existing!=existing.parent:existing=existing.parent
 free=shutil.disk_usage(existing).free
 if free<bytes_needed+16*1024*1024:blocked.append('Insufficient destination storage for immutable capsule plus working copy')
 project=root/'projects'/_safe_slug(meta.get('project_name',meta.get('project_id','project')))/meta['capsule_id']
 return {'capsule_id':meta['capsule_id'],'archive_sha256':result.get('archive_sha256') or digest(capsule_path),'route':route,'destination_root':str(root),'project_path':str(project),'evidence_path':str(root/'capsules'/meta['capsule_id']),'receipt_path':str(root/'receipts'/(meta['capsule_id']+'.json')),'required_bytes_estimate':bytes_needed,'free_bytes_observed':free,'destination_capabilities':caps,'mapping':mapping,'path_mappings':[m for m in mapping if m['mapping_reason']],'blocked_prerequisites':blocked,'dependencies':meta.get('dependencies',[]),'dependency_plan':[{'id':d.get('id'),'name':d.get('name'),'relationship':d.get('relationship'),'source_version':d.get('source_version'),'destination_status':'NOT_PROBED','next_action':'Probe the chosen destination interpreter/engine; install only compatible project-scoped dependencies after explicit plan review.'} for d in meta.get('dependencies',[]) if isinstance(d,dict)],'required_downloads':'UNRESOLVED until actual destination dependency probes; source versions are requirements/evidence, not current destination installations.','environment_reconstruction':'Required packages are discovered/rebuilt by an explicit trusted adapter; capsule scripts are never executed by restoration.','state':'RESTORATION_PLANNED','plan_executes_code':False,'completeness':result.get('completeness',{})}

def _within(root,path):
 root=Path(root).resolve();p=Path(path)
 try:p.resolve().relative_to(root)
 except ValueError:raise ValueError('Destination escapes its owned project')
 # Refuse existing symlink ancestors even when they happen to point inside.
 current=p
 while current!=root:
  if current.is_symlink():raise ValueError('Destination includes an unexpected symlink')
  if current.parent==current:raise ValueError('Destination ancestry is invalid')
  current=current.parent
 return p

def _transition(receipt,state):
 order=['RECEIVED','INTEGRITY_VERIFIED','RESTORATION_PLANNED','RESTORED','ACCEPTANCE_PASSED','READY_TO_CONTINUE']
 old=receipt.get('state')
 if old in order and order.index(state)<order.index(old):return
 receipt['state']=state;receipt.setdefault('history',[]).append({'state':state,'at':now()});atomic(receipt['receipt_path'],receipt)

def _write_object(z,object_name,target,expected):
 if not isinstance(object_name,str) or not re.fullmatch('objects/[a-f0-9]{64}',object_name):raise ValueError('Unsafe payload object reference')
 target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists():
  if target.is_file() and digest(target)==expected:return
  raise ValueError('Refusing to overwrite a changed destination file')
 temp=target.with_name('.'+target.name+'.relay-partial');h=hashlib.sha256()
 try:
  if temp.exists():
   if temp.is_symlink() or temp.stat().st_size>z.getinfo(object_name).file_size:raise ValueError('Unexpected object partial file')
   with z.open(object_name) as source,temp.open('rb') as old:
    for block in iter(lambda:old.read(1024*1024),b''):
     if source.read(len(block))!=block:raise ValueError('Object partial prefix differs; no overwrite')
     h.update(block)
    with temp.open('ab') as out:
     for block in iter(lambda:source.read(1024*1024),b''):out.write(block);h.update(block)
     out.flush();os.fsync(out.fileno())
  else:
   with z.open(object_name) as source,temp.open('xb') as out:
    for block in iter(lambda:source.read(1024*1024),b''):out.write(block);h.update(block)
    out.flush();os.fsync(out.fileno())
  if h.hexdigest()!=expected:raise ValueError('Object changed after verification')
  os.replace(temp,target)
 except BaseException:
  # Partial object belongs to this reconstruction; retain it for bounded resume.
  raise

def restore(capsule_path,destination_root,route=None,python=None):
 route=route or default_route()
 capsule_path=Path(capsule_path).absolute();p=plan(capsule_path,destination_root,route,python)
 if p['blocked_prerequisites']:raise RuntimeError('; '.join(p['blocked_prerequisites']))
 root=Path(p['destination_root']);root.mkdir(parents=True,exist_ok=True,mode=0o700)
 for directory in ['capsules','projects','receipts']:(root/directory).mkdir(exist_ok=True,mode=0o700)
 with lock(root):
  receipt_path=Path(p['receipt_path']);existing=read(receipt_path) if receipt_path.exists() else None
  if existing and existing.get('archive_sha256')!=p['archive_sha256']:raise ValueError('Capsule identity already received with different content')
  if existing and existing.get('state') in ['RESTORED','ACCEPTANCE_PASSED','READY_TO_CONTINUE']:
   if not Path(existing['project_path']).is_dir():raise ValueError('Existing receipt workspace is missing; no automatic duplicate restoration')
   return dict(existing,duplicate_receipt=True)
  if existing:p=existing
  else:p.update(state='DRAFT',schema_version=1,received_at=now(),source_archive_name=capsule_path.name,history=[],restore_nonce=uuid.uuid4().hex,transport='LOCAL_ROUNDTRIP_ONLY' if route=='LOCAL_LINUX' else 'DESTINATION_RECEIPT',failures=[])
  atomic(receipt_path,p)
  evidence=Path(p['evidence_path']);project=Path(p['project_path']);partial=project.with_name(project.name+'.partial')
  try:
   evidence.mkdir(parents=True,exist_ok=True,mode=0o700);kept=evidence/'capsule.zip'
   if kept.exists():
    if digest(kept)!=p['archive_sha256']:raise ValueError('Immutable received capsule changed')
   else:
    temp=evidence/'capsule.zip.partial'
    if temp.exists():
     # Resume only a matching prefix of this receipt's expected capsule.
     if temp.stat().st_size>capsule_path.stat().st_size:raise ValueError('Partial transfer exceeds expected archive size')
     with capsule_path.open('rb') as src,temp.open('rb') as old:
      for block in iter(lambda:old.read(1024*1024),b''):
       if src.read(len(block))!=block:raise ValueError('Partial transfer prefix differs; retain it for review')
      with temp.open('ab') as dst:shutil.copyfileobj(src,dst,1024*1024);dst.flush();os.fsync(dst.fileno())
    else:
     with capsule_path.open('rb') as src,temp.open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024);dst.flush();os.fsync(dst.fileno())
    if digest(temp)!=p['archive_sha256']:raise ValueError('Interrupted or changed capsule transfer')
    os.replace(temp,kept);kept.chmod(0o444)
   p['capsule_path']=str(kept);_transition(p,'RECEIVED');verified,meta,entries=_verified(kept);_transition(p,'INTEGRITY_VERIFIED');_transition(p,'RESTORATION_PLANNED')
   for name,value in [('CAPSULE.json',meta),('FILE-MANIFEST.json',verified['manifest']),('COMPLETENESS.json',verified.get('completeness',{}))]:
    target=evidence/name
    if not target.exists():atomic(target,value);target.chmod(0o444)
   if project.exists():
    marker=project/'_relay/RECONSTRUCTION.json'
    owned=read(marker) if marker.is_file() else {}
    if owned.get('restore_nonce')!=p.get('restore_nonce') or owned.get('archive_sha256')!=p['archive_sha256']:raise ValueError('Destination workspace exists without owned reconstruction identity; refusing overwrite')
    if not p.get('adaptation_baseline_path'):record_adaptation(p,{'stage':'materialization recovery','note':'Completed rename recovered without overwriting working files.'});p=read(receipt_path)
    _transition(p,'RESTORED');return p
   partial.parent.mkdir(parents=True,exist_ok=True)
   if partial.exists():
    marker=partial/'.relay-reconstruction.json'
    if not marker.is_file() or read(marker).get('archive_sha256')!=p['archive_sha256']:raise ValueError('Unowned partial reconstruction exists')
   else:partial.mkdir(mode=0o700);atomic(partial/'.relay-reconstruction.json',{'capsule_id':p['capsule_id'],'archive_sha256':p['archive_sha256'],'restore_nonce':p['restore_nonce']})
   with zipfile.ZipFile(kept) as z:
    for item in p['mapping']:
     if item['disposition'] not in ['INCLUDED_EXACT','INCLUDED_TRANSFORMED']:continue
     target=_within(partial,partial.joinpath(*PurePosixPath(item['destination_path']).parts))
     if item['type'] in ['directory','dir']:target.mkdir(parents=True,exist_ok=True)
     elif item['type']=='file':
      _write_object(z,item['object'],target,item['sha256'])
      if os.name!='nt':target.chmod(int(item.get('mode',0o644))&0o777)
     elif item['type']=='symlink':
      # Original descriptor remains in A; B gets inert text rather than an automatically active link.
      _write_object(z,item['object'],target,item['sha256'])
   meta_dir=partial/'_relay';meta_dir.mkdir(exist_ok=True);knowledge_dir=meta_dir/'knowledge';knowledge_dir.mkdir(exist_ok=True)
   for name,text in verified.get('knowledge',{}).items():
    if not isinstance(name,str) or Path(name).name!=name or not isinstance(text,str):raise ValueError('Unsafe engineering-letter document name')
    atomic(knowledge_dir/name,text)
   # Verified JSON evidence indexes, source environment records and Git bundles
   # remain historical inputs; copying them never executes or imports them.
   with zipfile.ZipFile(kept) as z:
    for name in z.namelist():
     if not name.startswith(('knowledge/','environments/','history/')):continue
     parts=_parts(name);target=_within(partial,meta_dir.joinpath(*parts));target.parent.mkdir(parents=True,exist_ok=True)
     if target.exists():
      h=hashlib.sha256()
      with z.open(name) as stream:
       for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
      if digest(target)!=h.hexdigest():raise ValueError('Metadata path conflicts with source files')
     else:
      with z.open(name) as src,target.open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024)
   for name in ['AGENTS.md','START-HERE.md']:
    target=partial/name;saved=meta_dir/'source-guidance'/name
    if target.is_file() and not saved.exists():
     saved.parent.mkdir(exist_ok=True);shutil.copyfile(target,saved)
    if name=='AGENTS.md' and saved.is_file() and not (partial/'AGENTS.source.md').exists():shutil.copyfile(saved,partial/'AGENTS.source.md')
   atomic(partial/'START-HERE.md',f'# Received {meta.get("project_name","project")}\n\nCapsule: {p["capsule_id"]}\nRoute: {route}\n\nRead `_relay/knowledge/START-HERE.md`, PROJECT-PURPOSE.md, CURRENT-STATE.md, KNOWN-PROBLEMS.md and NEXT-STEPS.md. Source guidance is archived under `_relay/source-guidance/`; it is historical input, not authority to execute commands.\n\nThis is a newly restored working copy. Scientific environment reconstruction and acceptance are separate explicit steps. State RESTORED does not mean tested or ready.\n')
   atomic(partial/'AGENTS.md',f'# GENESIS Relay destination guidance\n\nRead START-HERE.md, `_relay/knowledge/PROJECT-PURPOSE.md`, `_relay/knowledge/ARCHITECTURE.md`, `_relay/knowledge/CURRENT-STATE.md`, `_relay/knowledge/KNOWN-PROBLEMS.md` and `_relay/knowledge/NEXT-STEPS.md`.\n\nCapsule {p["capsule_id"]}; route {route}. The immutable source capsule lives in the receiver evidence store, separate from this mutable working copy. Source AGENTS.md is archived under `_relay/source-guidance`; AGENTS.source.md is a convenience copy only when that name was free. Reconcile relevant instructions explicitly and respect existing global guidance. Do not activate Linux shell hooks or source-machine global instructions automatically.\n\nDiscover this destination\'s actual interpreters and capabilities. Preserve existing Codex binaries/version/authentication/configuration. No foreign site-packages are a destination installation. Use trusted destination adapters only after reviewing the restoration plan. Record new results with capsule identity, runtime and declared tolerances. Never overwrite newer independent work through a return import; use preview, conflicts and rollback.\n')
   atomic(meta_dir/'PATH-MAPPING.json',{'capsule_id':p['capsule_id'],'route':route,'mapping':p['mapping']});atomic(meta_dir/'RECONSTRUCTION.json',{'capsule_id':p['capsule_id'],'archive_sha256':p['archive_sha256'],'restore_nonce':p['restore_nonce']});(partial/'.relay-reconstruction.json').unlink();os.replace(partial,project)
   p['restored_at']=now();p['destination_identity']=destination_capabilities(python);record_adaptation(p,{'stage':'materialization','note':'No scientific acceptance or dependency installation claimed.'});p=read(receipt_path);_transition(p,'RESTORED');return p
  except Exception as error:
   p.setdefault('failures',[]).append({'at':now(),'stage':p.get('state','RESTORATION_PLANNED'),'type':type(error).__name__,'error':str(error)[:700]});atomic(receipt_path,p);raise

def working_inventory(project):
 project=Path(project);entries={}
 for folder,dirs,files in os.walk(project,followlinks=False):
  dirs[:]=sorted(d for d in dirs if d not in {'.venv','.relay-venv','venv','__pycache__','.git','.relay-return-history'} and not (Path(folder)/d).is_symlink())
  for name in sorted(files):
   path=Path(folder)/name;rel=path.relative_to(project).as_posix()
   if rel.startswith('_relay/') or path.is_symlink():continue
   entries[rel]={'sha256':digest(path),'size':path.stat().st_size,'mode':path.stat().st_mode&0o777}
 return entries

def record_adaptation(receipt,details=None):
 p=read(receipt) if isinstance(receipt,(str,Path)) else dict(receipt);project=Path(p['project_path']);baseline={'capsule_id':p['capsule_id'],'archive_sha256':p['archive_sha256'],'created_at':now(),'route':p['route'],'project_path':str(project),'files':working_inventory(project),'details':details or {}}
 path=project/'_relay/adaptation-baseline.json';atomic(path,baseline);p['adaptation_baseline_path']=str(path);p['adaptation_baseline_sha256']=digest(path);p['adaptations']=details or {};atomic(p['receipt_path'],p);return baseline

def verify_restoration(receipt_or_path):
 p=read(receipt_or_path) if isinstance(receipt_or_path,(str,Path)) else dict(receipt_or_path);verified,meta,entries=_verified(p['capsule_path']);checks={'received_capsule_hash':digest(p['capsule_path'])==p['archive_sha256'],'capsule_identity':meta['capsule_id']==p['capsule_id'],'workspace_exists':Path(p['project_path']).is_dir()};problems=[];baseline=read(p['adaptation_baseline_path']) if p.get('adaptation_baseline_path') else None
 if baseline:
  current=working_inventory(p['project_path']);checks['adaptation_baseline_retained']=digest(p['adaptation_baseline_path'])==p['adaptation_baseline_sha256'];checks['baseline_files_present']=all(name in current for name in baseline['files'])
  # Later edits are legitimate work, but shown separately from restored baseline verification.
  changed=[name for name,x in baseline['files'].items() if name not in current or current[name]['sha256']!=x['sha256']]
 else:changed=[];checks['adaptation_baseline_retained']=False
 for item in p['mapping']:
  if item['type']=='file' and item['source_path'].lower().endswith(('.sqlite','.sqlite3','.db')) and item['disposition'] in ['INCLUDED_EXACT','INCLUDED_TRANSFORMED']:
   database=Path(p['project_path'])/item['destination_path']
   if database.is_file():
    with database.open('rb') as probe:
     if probe.read(16)!=b'SQLite format 3\x00':continue
   try:
    conn=sqlite3.connect('file:'+database.as_posix()+'?mode=ro',uri=True);okay=conn.execute('pragma quick_check').fetchone()[0]=='ok';conn.close();checks['database:'+item['source_path']]=okay
   except sqlite3.Error as error:checks['database:'+item['source_path']]=False;problems.append(type(error).__name__)
 result={'checked_at':now(),'capsule_id':p['capsule_id'],'route':p['route'],'state':'RESTORED','status':'PASSED' if all(checks.values()) else 'FAILED','checks':checks,'working_changes_since_adaptation':changed,'problems':problems,'scientific_acceptance':'NOT_RUN by integrity verification; use trusted acceptance adapter','transport':p['transport']};atomic(Path(p['receipt_path']).with_name(p['capsule_id']+'-verification.json'),result);return result

def open_project(receipt_or_path):
 p=read(receipt_or_path) if isinstance(receipt_or_path,(str,Path)) else receipt_or_path;path=Path(p['project_path']);command=shutil.which('explorer.exe') if os.name=='nt' else shutil.which('xdg-open')
 if not command:raise RuntimeError('No native folder-opening command is available; project: '+str(path))
 subprocess.Popen([command,str(path)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);return {'opened':str(path)}
def launch_codex(receipt_or_path):
 p=read(receipt_or_path) if isinstance(receipt_or_path,(str,Path)) else receipt_or_path;exe=shutil.which('codex')
 if not exe:raise RuntimeError('An existing Codex executable was not found; no installation attempted')
 path=Path(p['project_path']);return subprocess.call([exe,'-C',str(path)],cwd=path)

def record_acceptance(receipt,acceptance):
 """Record a trusted adapter result without rewriting historical source evidence.

A milestone cannot be inferred from extracted files or a caller's status word.
The saved result, capsule binding, project/route and actual execution platform
must agree. Later failure invalidates current readiness without erasing history.
 """
 original=read(receipt) if isinstance(receipt,(str,Path)) else dict(receipt)
 result=read(acceptance) if isinstance(acceptance,(str,Path)) else dict(acceptance)
 receipt_path=Path(original['receipt_path']);root=receipt_path.parent.parent
 with lock(root):
  p=read(receipt_path);project=Path(p['project_path']).resolve();source_path=Path(result.get('receipt_path','')).absolute()
  try:source_path.resolve().relative_to(project/'_relay/verification')
  except ValueError:raise ValueError('Acceptance must be a saved project-local trusted-adapter verification receipt')
  if not source_path.is_file() or source_path.is_symlink() or read(source_path)!=result:raise ValueError('Acceptance result differs from its saved verification record')
  if result.get('route')!=p['route'] or result.get('source_capsule_id')!=p['capsule_id'] or result.get('source_capsule_sha256')!=p['archive_sha256']:raise ValueError('Acceptance is bound to another capsule or restoration route')
  if Path(result.get('project_path','')).resolve()!=project:raise ValueError('Acceptance belongs to another working project')
  _verified(p['capsule_path'])
  if digest(p['capsule_path'])!=p['archive_sha256']:raise ValueError('Immutable source capsule changed')
  if p['route']=='LOCAL_LINUX' and platform.system()!='Linux':raise ValueError('LOCAL_LINUX acceptance needs actual Linux execution')
  if p['route']=='NATIVE_WINDOWS_X64' and not (os.name=='nt' and platform.machine().lower() in ['amd64','x86_64']):raise ValueError('Native Windows acceptance was not executed here')
  if p['route']=='WSL_LINUX_X64' and not (platform.system()=='Linux' and 'microsoft' in platform.release().lower() and platform.machine().lower() in ['amd64','x86_64']):raise ValueError('WSL Linux x64 acceptance was not executed here')
  passed=result.get('passed',{});failed=result.get('failed',{});skipped=result.get('skipped',{})
  if not isinstance(passed,(dict,list)) or not isinstance(failed,(dict,list)) or not isinstance(skipped,(dict,list)):raise ValueError('Acceptance needs separate passed/failed/skipped collections')
  copy=receipt_path.with_name(p['capsule_id']+'-acceptance-'+uuid.uuid4().hex[:12]+'.json');atomic(copy,result);copy.chmod(0o444)
  summary={'at':now(),'status':result.get('status','UNKNOWN'),'passed':len(passed),'failed':len(failed),'skipped':len(skipped),'receipt_path':str(copy),'sha256':digest(copy),'source_receipt_path':str(source_path)}
  p.setdefault('acceptance_history',[]).append(summary);p.update(acceptance_path=str(copy),acceptance_receipt_path=str(copy),acceptance_sha256=summary['sha256'],latest_acceptance_status=summary['status'],ready_to_continue=False)
  qualified=result.get('status')=='ACCEPTANCE_PASSED' and bool(passed) and not failed and not skipped and all(value is not False for value in (passed.values() if isinstance(passed,dict) else passed))
  if qualified:
   p['readiness_scope']='LOCAL_ROUNDTRIP_ONLY' if p['route']=='LOCAL_LINUX' else p['route'];_transition(p,'ACCEPTANCE_PASSED');p['ready_to_continue']=True;_transition(p,'READY_TO_CONTINUE')
  else:
   p.setdefault('failures',[]).append({'at':now(),'stage':'ACCEPTANCE','status':summary['status'],'failed':failed,'skipped':skipped,'acceptance_path':str(copy)});p.setdefault('history',[]).append({'state':p.get('state','RESTORED'),'at':now(),'acceptance_status':summary['status'],'readiness_invalidated':True});atomic(receipt_path,p)
  return p
