"""Version-one private continuation capsules: stable snapshot and strict ZIP reader."""
import base64,contextlib,hashlib,io,json,os,platform,re,shutil,sqlite3,stat,tempfile,time,unicodedata,uuid,zipfile
from pathlib import Path,PurePosixPath
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
from urllib.error import HTTPError,URLError
from .common import atomic,canonical,load,lock,now,run,sha
from . import discovery,state
FORMAT='genesis-relay';VERSION='1.0';MAX_BYTES=8*1024**3;MAX_ENTRIES=100000
class CapsuleError(ValueError):pass
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args):return None

def _identity(pid):
 try:
  base=Path('/proc')/str(int(pid));fields=(base/'stat').read_text().rsplit(')',1)[1].split();args=[x.decode(errors='replace') for x in (base/'cmdline').read_bytes().split(b'\0') if x];return {'pid':int(pid),'start':fields[19],'args':args}
 except (OSError,ValueError,IndexError):return None

def _source_identity(root):
 try:
  record=_identity(int((root/'runtime/lab.pid').read_text()));args=record['args']
  return record if str(root/'server.py') in args else None
 except (OSError,ValueError,TypeError):return None

@contextlib.contextmanager
def _export_writer(home,cid):
 manager=lock(home/'export.lock',timeout=2)
 try:manager.__enter__()
 except BaseException as error:
  state.record(home,cid,failure=type(error).__name__+': '+str(error));raise
 try:yield
 finally:manager.__exit__(None,None,None)

def _http_code(port):
 try:
  with build_opener(ProxyHandler({}),NoRedirect()).open(f'http://127.0.0.1:{port}/',timeout=3) as r:return r.status
 except HTTPError as e:return e.code
 except OSError:return None

@contextlib.contextmanager
def quiescence(root,enabled=True,journal=None):
 profile=(root/'catalogue.py').is_file() and (root/'START-LAB.sh').is_file() and (root/'STOP-LAB.sh').is_file();proof={'method':'stable file capture and SQLite backup','original_running':False,'source_stopped':False,'source_restarted':False}
 if not profile or not enabled:
  if profile and not enabled:proof['limitation']='Application quiescence disabled explicitly; active applications are not a multi-file transaction.'
  yield proof;return
 if os.name!='posix' or not Path('/proc').exists():raise CapsuleError('Source service ownership cannot be verified on this exporter platform')
 owner=_source_identity(root);code=_http_code(8090)
 if code is not None and not owner:raise CapsuleError('Science port has a listener without matching source identity; nothing stopped')
 if not owner:
  proof.update(method='Source already stopped; SQLite backup and stable artifact snapshot');yield proof;return
 credentials=load(root/'private/access.json',{});auth='Basic '+base64.b64encode((credentials.get('username','')+':'+credentials.get('password','')).encode()).decode()
 try:
  req=Request('http://127.0.0.1:8090/api/jobs',headers={'Authorization':auth})
  with build_opener(ProxyHandler({}),NoRedirect()).open(req,timeout=10) as f:jobs=json.load(f)
 except Exception:raise CapsuleError('Could not verify idle owned laboratory; no process stopped') from None
 if jobs.get('active'):raise CapsuleError('A scientific job is active; wait for it to finish before export')
 if _source_identity(root)!=owner:raise CapsuleError('Source process identity changed; nothing stopped')
 proof.update(method='Verified idle project-scoped quiescence + SQLite backup API + stable artifact capture',original_running=True,source_identity=owner)
 if journal:
  atomic(journal,{'source_root':str(root),'original_running':True,'needs_restart':True,'start_helper_sha256':sha(root/'START-LAB.sh'),'at':now(),'checkpoint':'BEFORE_SOURCE_STOP'})
 try:
  code,out,err=run([root/'STOP-LAB.sh'],timeout=25,cwd=root)
  if code or _source_identity(root) or _http_code(8090) is not None:raise CapsuleError('Owned laboratory did not stop cleanly; capture not attempted')
  proof['source_stopped']=True
  if journal:
   checkpoint=load(journal);checkpoint.update(checkpoint='SOURCE_STOPPED_FOR_CAPTURE',at=now());atomic(journal,checkpoint)
  yield proof
 finally:
  # Reuse only this project's owned helper; never signal an unrelated listener.
  if proof['original_running'] and not _source_identity(root):
   if _http_code(8090) is not None:raise CapsuleError('Source restart blocked by a new listener; inspect source service status')
   code,out,err=run([root/'START-LAB.sh'],timeout=40,cwd=root)
   proof['source_restarted']=code==0 and bool(_source_identity(root)) and _http_code(8090)==401
   if not proof['source_restarted']:raise CapsuleError('Source laboratory restart did not verify; inspect its existing private log')
  if journal:
   checkpoint=load(journal);checkpoint.update(needs_restart=False,checkpoint='SOURCE_RUNNING_AGAIN',at=now());atomic(journal,checkpoint)

def recover_checkpoints(state_dir=None,apply=False):
 home=state.state_dir(state_dir);results=[]
 with lock(home/'export.lock',timeout=2):
  for path in sorted(home.glob('source-checkpoint-*.json')):
   item=load(path,{})
   if not item.get('needs_restart'):continue
   root=Path(item.get('source_root','/nonexistent'));result={'checkpoint':str(path),'source_root':str(root),'action':'REVIEW_SOURCE_RESTART','applied':False}
   if not (root/'START-LAB.sh').is_file() or sha(root/'START-LAB.sh')!=item.get('start_helper_sha256'):result['blocked']='Source helper changed or missing; no execution authority granted'
   elif apply:
    if not _source_identity(root):
     if _http_code(8090) is not None:result['blocked']='A listener exists without source ownership; nothing changed'
     else:
      code,out,err=run([root/'START-LAB.sh'],timeout=40,cwd=root)
      if code or not _source_identity(root) or _http_code(8090)!=401:result['blocked']='Restart did not verify'
    if not result.get('blocked'):
     item.update(needs_restart=False,checkpoint='SOURCE_RUNNING_RECOVERED',at=now());atomic(path,item);result['applied']=True
   results.append(result)
 return {'checkpoints':results,'apply_requested':apply,'scope':'Recover an interrupted known source-service checkpoint only; never stop a process or overwrite a capsule.'}

def plan(source_root,mode='full',sentinel_root=None):
 data=discovery.discover(source_root,mode=mode);data['snapshot_method']=data['consistency_method'];data['required_free_bytes']=2*data['payload_estimated_bytes']+32*1024**2;data['free_bytes']=shutil.disk_usage(Path(source_root)).free;data['offline_ready']=False;data['transport']='PRIVATE_LOCAL_EXPORT_ONLY';return data

def _signature(path):
 s=path.lstat();return (s.st_ino,s.st_size,s.st_mtime_ns,stat.S_IMODE(s.st_mode))

def _copy_stable(path,folder,retries=3):
 for attempt in range(retries):
  before=_signature(path);temp=folder/('.copy-'+uuid.uuid4().hex);h=hashlib.sha256()
  try:
   fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
   with os.fdopen(fd,'rb') as inp,temp.open('xb') as out:
    observed=os.fstat(inp.fileno())
    if (observed.st_ino,observed.st_size,observed.st_mtime_ns,stat.S_IMODE(observed.st_mode))!=before:raise CapsuleError('File changed before reading')
    for chunk in iter(lambda:inp.read(1024*1024),b''):h.update(chunk);out.write(chunk)
    out.flush();os.fsync(out.fileno())
   if before==_signature(path) and sha(path)==h.hexdigest():
    digest=h.hexdigest();dest=folder/digest
    if dest.exists():temp.unlink()
    else:os.replace(temp,dest)
    return digest,before
  except (OSError,CapsuleError):pass
  finally:
   if temp.exists():temp.unlink()
  time.sleep(.05)
 raise CapsuleError('File kept changing during bounded capture: '+path.name)

def _sqlite_backup(source,destination):
 start=time.monotonic();src=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=3);dst=sqlite3.connect(destination)
 def progress(status,remaining,total):
  if time.monotonic()-start>30:raise CapsuleError('SQLite backup exceeded time limit')
 try:
  src.backup(dst,pages=128,progress=progress,sleep=.01);dst.execute('PRAGMA journal_mode=DELETE');dst.commit();okay=dst.execute('PRAGMA integrity_check').fetchone()[0]
  if okay!='ok':raise CapsuleError('SQLite backup integrity failed')
  tables=dst.execute("select name from sqlite_master where type='table' order by name").fetchall();return {'integrity_check':'ok','tables':[x[0] for x in tables],'method':'sqlite3.Connection.backup'}
 finally:src.close();dst.close()

def _relationships(root,db,entries):
 if not (root/'catalogue.py').is_file():return {'scope':'SQLite transaction snapshot; application-specific artifact graph not supplied'}
 con=sqlite3.connect(db);con.row_factory=sqlite3.Row
 try:rows=[dict(r) for r in con.execute('select * from jobs order by id')]
 finally:con.close()
 included={e['path']:e for e in entries if e['disposition'].startswith('INCLUDED')};missing=[];refs=0
 for row in rows:
  if row['status']=='running':raise CapsuleError('Database snapshot contains an active job')
  if row['status']!='succeeded':continue
  if not re.fullmatch('[a-f0-9]{32}',row['id']):raise CapsuleError('Invalid source run identity')
  rel='results/'+row['id']+'/result.json';data=load(root/rel)
  if not data:missing.append(rel);continue
  for name in data.get('artifacts',[]):
   if not isinstance(name,str) or Path(name).name!=name or '/' in name or '\\' in name:raise CapsuleError('Unsafe stored artifact relation')
   artifact='results/'+row['id']+'/'+name;refs+=1
   if artifact not in included or not (root/artifact).is_file():missing.append(artifact)
 if missing:raise CapsuleError('Database references missing/excluded artifacts: '+str(missing[:4]))
 return {'jobs':len(rows),'succeeded':sum(r['status']=='succeeded' for r in rows),'failed':sum(r['status']=='failed' for r in rows),'cancelled':sum(r['status']=='cancelled' for r in rows),'artifact_references_checked':refs,'missing':[],'stable_run_ids_preserved':True}

def _git(root,work,values):
 output={};info={'method':'versioned manifest','repository':False,'complete':True}
 code,name,err=run(['git','-C',root,'rev-parse','--show-toplevel']) if shutil.which('git') else (1,'','')
 if code or Path(name.strip()).resolve()!=root:return output,info
 info.update(repository=True,method='git bundle plus patches and exact working snapshot');info['shallow']=run(['git','-C',root,'rev-parse','--is-shallow-repository'])[1].strip()=='true';info['complete']=not info['shallow'];info['status']=run(['git','-C',root,'status','--porcelain=v1','--untracked-files=all'])[1]
 info['refs']=run(['git','-C',root,'show-ref'])[1];info['submodules']=run(['git','-C',root,'submodule','status','--recursive'])[1]
 code,remotes,err=run(['git','-C',root,'remote','-v']);info['remotes']=re.sub(r'(https?://)[^/@\s]+@',r'\1[credentials-omitted]@',remotes)
 fsck=run(['git','-C',root,'fsck','--full','--no-reflogs'],timeout=60)
 if fsck[0]:info.update(complete=False,problem='Missing or corrupt Git history objects')
 for args,name in [(['diff','--binary'],'unstaged.patch'),(['diff','--cached','--binary'],'staged.patch')]:
  code,text,err=run(['git','-C',root,*args]);path=work/name;path.write_text(text);output['history/'+name]=path
 # Scan every reachable blob before bundling; compressed bundle patterns alone are insufficient.
 code,text,err=run(['git','-C',root,'rev-list','--objects','--all'],timeout=60);safe=code==0
 all_objects=text.splitlines()+[line.split(' ',1)[0] for line in info.get('refs','').splitlines()]
 visited=set()
 for line in all_objects:
  oid=line.split(' ',1)[0]
  if not re.fullmatch('[a-f0-9]{40,64}',oid) or oid in visited:continue
  visited.add(oid)
  code,kind,err=run(['git','-C',root,'cat-file','-t',oid])
  if kind.strip() not in ['blob','commit','tag']:continue
  path=work/'history-blob';fd=path.open('wb')
  import subprocess
  try:
   p=subprocess.run(['git','-C',str(root),'cat-file',kind.strip(),oid],stdout=fd,stderr=subprocess.DEVNULL,timeout=20)
  finally:fd.close()
  if p.returncode or discovery.secret_match(path,values):safe=False;break
  path.unlink(missing_ok=True)
 if not safe:info.update(complete=False,problem='Selected history contains an exposed secret or could not be read; bundle excluded')
 elif info.get('refs'):
  bundle=work/'project.bundle';code,out,err=run(['git','-C',root,'bundle','create',bundle,'--all'],timeout=90)
  valid=code==0 and run(['git','-C',root,'bundle','verify',bundle],timeout=60)[0]==0
  if valid:output['history/project.bundle']=bundle;info['bundle_verified']=True
  else:info.update(complete=False,problem='Git bundle verification failed')
 else:info['no_commits']=True
 if 'filter=lfs' in ((root/'.gitattributes').read_text(errors='replace') if (root/'.gitattributes').is_file() else ''):info.update(complete=False,lfs='LFS object completeness is not established; resolve separately')
 if info.get('submodules'):info.update(complete=False,submodule_note='Submodule commits recorded; separate repository capsules required')
 # Patches are also private inputs; never emit a known-secret patch.
 for name,path in list(output.items()):
  if path.suffix=='.patch' and discovery.secret_match(path,values):del output[name];info.update(complete=False,problem='Secret-bearing working patch excluded')
 return output,info

def export(source_root,output=None,*,state_dir=None,mode='full',sentinel_root=None,quiesce=True,parent_capsule=None):
 root=Path(source_root).expanduser().resolve();home=state.state_dir(state_dir);capsules=home/'capsules'
 cid='relay-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:10];final=Path(output).absolute() if output else capsules/(cid+'.zip')
 if home.resolve().is_relative_to(root) or final.resolve().is_relative_to(root):raise CapsuleError('State and output must be outside the selected project root')
 if final.exists() or final.is_symlink():raise CapsuleError('Export never overwrites an existing capsule')
 home.mkdir(parents=True,exist_ok=True,mode=0o700);capsules.mkdir(exist_ok=True,mode=0o700)
 final.parent.mkdir(parents=True,exist_ok=True);partial=final.with_name(final.name+'.partial');work=home/('.snapshot-'+cid);work.mkdir(mode=0o700);objects=work/'objects';objects.mkdir();start=now();state.record(home,cid,'DRAFT',source_root=str(root),mode=mode,archive=str(final));snapshot_proof={}
 with _export_writer(home,cid):
  try:
   with quiescence(root,quiesce,journal=home/('source-checkpoint-'+cid+'.json')) as snapshot_proof:
    inventory=plan(root,mode=mode,sentinel_root=sentinel_root)
    if inventory['errors']:raise CapsuleError('Unreadable project entries block complete snapshot')
    if shutil.disk_usage(final.parent).free<inventory['required_free_bytes']:raise CapsuleError('Insufficient storage for staged objects plus partial archive')
    entries=inventory['entries'];signatures={};dbs=[]
    for e in entries:
     if not e['disposition'].startswith('INCLUDED'):continue
     path=root/e['path']
     if e['type']=='directory':continue
     if e['type']=='symlink':
      raw=e['target'].encode('utf-8',errors='surrogateescape');digest=hashlib.sha256(raw).hexdigest();atomic(objects/digest,raw);e.update(object='objects/'+digest,sha256=digest,size=len(raw),representation='inert symlink target bytes; never archive link');continue
     if e['disposition']=='INCLUDED_TRANSFORMED':
      temp=work/('database-'+uuid.uuid4().hex+'.sqlite3');db_info=_sqlite_backup(path,temp);digest=sha(temp);dest=objects/digest
      if dest.exists():temp.unlink()
      else:os.replace(temp,dest)
      e.update(object='objects/'+digest,sha256=digest,source_sha256=sha(path),source_size=e['size'],size=dest.stat().st_size,snapshot_method=db_info);dbs.append((dest,db_info,e));continue
     digest,before=_copy_stable(path,objects);e.update(object='objects/'+digest,sha256=digest);signatures[e['path']]=before
    # Detect added/removed/changed included source entries while objects were copied.
    after=discovery.discover(root,mode=mode);expected={e['path'] for e in entries if e['disposition'].startswith('INCLUDED')};observed={e['path'] for e in after['entries'] if e['disposition'].startswith('INCLUDED')}
    if expected!=observed:raise CapsuleError('Project entry set changed during snapshot')
    for rel,before in signatures.items():
     if _signature(root/rel)!=before:raise CapsuleError('Source changed after capture: '+rel)
    relationships=[]
    for db,proof,e in dbs:relationships.append(_relationships(root,db,entries) if e['path']=='private/laboratory.sqlite3' else proof)
    from .knowledge import capture
    knowledge=capture(root,sentinel_root=sentinel_root);documents=knowledge.get('documents',{})
    history,git=_git(root,work,discovery.active_secrets(root));counts={d:sum(e['disposition']==d for e in entries) for d in sorted(discovery.DISPOSITIONS)};complete=mode=='full' and not inventory['errors'] and git['complete'] and not any(e.get('required_secret_exclusion') for e in entries)
    completeness={'mode':mode,'all_entries_accounted':len(entries)==sum(counts.values()),'entries':len(entries),'files':sum(e['type']=='file' for e in entries),'counts':counts,'source_bytes_accounted':inventory['bytes_total'],'payload_file_bytes':sum(e.get('size',0) for e in entries if e['disposition'].startswith('INCLUDED')),'unresolved_required_files':inventory['errors'],'full_non_secret_project_complete':complete,'qualification':'Secret access files, generated runtime/cache and source-platform installed dependencies are explicitly excluded/referenced, not portable binaries.','git':git,'databases':relationships,'offline_ready':False,'snapshot_consistent':True}
    state.record(home,cid,'SNAPSHOTTED',completeness=completeness)
    payloads={}
    for p in objects.iterdir():payloads['objects/'+p.name]=p
    def add_json(name,value):p=work/('metadata-'+uuid.uuid4().hex+'.json');atomic(p,value);payloads[name]=p
    add_json('FILE-MANIFEST.json',{'schema_version':'1.0','entries':entries});add_json('COMPLETENESS.json',completeness)
    for name,text in documents.items():
     if Path(name).name!=name:raise CapsuleError('Knowledge document names must be basenames')
     p=work/('letter-'+name);atomic(p,text);payloads['knowledge/'+name]=p
     if name=='START-HERE.md':payloads[name]=p
    add_json('environments/SOURCE-ENVIRONMENT.json',knowledge.get('environment',{}));add_json('environments/DEPENDENCIES.json',knowledge.get('dependencies',[]));add_json('knowledge/SENTINEL-SOURCE-EVIDENCE.json',knowledge.get('sentinel_evidence',{}));add_json('history/GIT-STATE.json',git)
    for name,text in knowledge.get('recipes',{}).items():
     if Path(name).name!=name:raise CapsuleError('Environment recipe name must be a basename')
     recipe=work/('recipe-'+name);atomic(recipe,text);payloads['environments/'+name]=recipe
    payloads.update(history)
    # All payloads are scanned after transforms and generated knowledge too.
    known=discovery.active_secrets(root)
    for name,path in payloads.items():
     if discovery.secret_match(path,known):raise CapsuleError('Secret detection blocked payload: '+name)
    metadata={'format':FORMAT,'format_version':VERSION,'capsule_id':cid,'project_id':inventory['project_id'],'project_name':inventory['project_name'],'mode':mode,'roots':[{'id':'project','name':root.name}],'source_platform':{'system':platform.system(),'architecture':platform.machine()},'capture_interval':{'start_utc':start,'end_utc':now()},'parent_capsule':parent_capsule,'state':'VERIFIED_FOR_TRANSFER','transport_status':'LOCAL_ARCHIVE_ONLY_NO_DESTINATION_RECEIPT','supported_restoration_routes':['LOCAL_LINUX','NATIVE_WINDOWS_X64','WSL_LINUX_X64'],'route_qualification':'Routes are implemented plans; native Windows, WSL and Linux qualification belongs only to actual destination acceptance receipts.','dependencies':knowledge.get('dependencies',[]),'snapshot':dict(snapshot_proof),'payloads':{name:{'sha256':sha(path),'size':path.stat().st_size} for name,path in sorted(payloads.items())},'digest_definition':'SHA256SUMS.txt covers every other ZIP member. CAPSULE.payloads covers all members except CAPSULE.json and SHA256SUMS.txt. Final archive SHA-256 is external.','limitations':['Hashes prove integrity against a retained reference, not sender authenticity.','Source environment metadata is historical remote evidence on a receiver.','No destination execution or actual transfer is established by a local download.']}
    meta_path=work/'CAPSULE.json';atomic(meta_path,metadata);payloads['CAPSULE.json']=meta_path;checks=''.join(sha(path)+'  '+name+'\n' for name,path in sorted(payloads.items()));check_path=work/'SHA256SUMS.txt';atomic(check_path,checks);payloads['SHA256SUMS.txt']=check_path
    with zipfile.ZipFile(partial,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
     for name,path in sorted(payloads.items()):z.write(path,name)
    verify(partial);digest=sha(partial);os.replace(partial,final);final.chmod(0o600);atomic(str(final)+'.sha256',digest+'  '+final.name+'\n')
   # Context exit restarted the original service; retain that new observation separately.
   record={'capsule_id':cid,'archive':str(final),'path':str(final),'sha256':digest,'size':final.stat().st_size,'completeness':completeness,'state':'VERIFIED_FOR_TRANSFER','source_service_checkpoint':snapshot_proof,'scope':'PRIVATE_FULL_CONTINUATION' if mode=='full' else 'PRIVATE_LIGHTWEIGHT'}
   state.record(home,cid,'VERIFIED_FOR_TRANSFER',**{k:v for k,v in record.items() if k not in ['capsule_id','state']});atomic(home/('export-'+cid+'.json'),record);shutil.rmtree(work);return record
  except BaseException as error:
   state.record(home,cid,failure=type(error).__name__+': '+str(error),partial_archive=str(partial),snapshot_work=str(work));raise

def _safe_member(name):
 if not name or len(name)>400 or '\\' in name or ':' in name or name.startswith('/') or any(p in ('','.','..') for p in name.split('/')):raise CapsuleError('Unsafe ZIP member path')
 for p in name.split('/'):
  if p.rstrip(' .')!=p or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?',p):raise CapsuleError('Unsupported Windows ZIP member name')

def verify(path,*,max_bytes=MAX_BYTES,max_entries=MAX_ENTRIES):
 path=Path(path)
 if not path.is_file():raise CapsuleError('Capsule archive does not exist')
 with zipfile.ZipFile(path) as z:
  infos=z.infolist()
  if len(infos)>max_entries:raise CapsuleError('Excessive archive entry count')
  seen=set();total=0
  for info in infos:
   _safe_member(info.filename);key=unicodedata.normalize('NFC',info.filename).casefold()
   if key in seen:raise CapsuleError('Duplicate/case-colliding ZIP entries')
   seen.add(key);mode=(info.external_attr>>16)&0o170000
   if mode not in [0,stat.S_IFREG] or info.is_dir():raise CapsuleError('ZIP links/directories/special entries are not capsule payload files')
   if info.compress_type not in [zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED] or info.flag_bits&1:raise CapsuleError('Unsupported/encrypted compression')
   total+=info.file_size
   if total>max_bytes or info.file_size>max_bytes:raise CapsuleError('Archive expansion exceeds configured limit')
   if info.file_size>1048576 and info.file_size>max(info.compress_size,1)*1000:raise CapsuleError('Suspicious archive expansion ratio')
  names={i.filename for i in infos};required={'CAPSULE.json','FILE-MANIFEST.json','COMPLETENESS.json','SHA256SUMS.txt','START-HERE.md'}
  if not required<=names:raise CapsuleError('Missing required capsule members')
  def read_json(name):
   if z.getinfo(name).file_size>32*1024**2:raise CapsuleError('Metadata exceeds finite limit')
   def unique(pairs):
    value={}
    for key,item in pairs:
     if key in value:raise CapsuleError('Duplicate JSON object key')
     value[key]=item
    return value
   try:return json.loads(z.read(name),object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
   except (ValueError,UnicodeError):raise CapsuleError('Invalid capsule JSON') from None
  meta=read_json('CAPSULE.json')
  if not isinstance(meta,dict) or meta.get('format')!=FORMAT or not isinstance(meta.get('format_version'),str) or meta['format_version'].split('.')[0]!='1':raise CapsuleError('Unsupported capsule format major version')
  if not re.fullmatch('[A-Za-z0-9_-]{1,100}',str(meta.get('capsule_id',''))):raise CapsuleError('Invalid capsule identity')
  payloads=meta.get('payloads')
  if not isinstance(payloads,dict) or set(payloads)!=names-{'CAPSULE.json','SHA256SUMS.txt'}:raise CapsuleError('Manifest/member set mismatch')
  if z.getinfo('SHA256SUMS.txt').file_size>16*1024**2:raise CapsuleError('Checksum manifest exceeds limit')
  checks={}
  try:
   for line in z.read('SHA256SUMS.txt').decode('utf-8').splitlines():
    digest,name=line.split('  ',1)
    if not re.fullmatch('[a-f0-9]{64}',digest) or name in checks:raise CapsuleError('Invalid/duplicate checksum entry')
    checks[name]=digest
  except ValueError:raise CapsuleError('Malformed checksum manifest') from None
  if set(checks)!=names-{'SHA256SUMS.txt'}:raise CapsuleError('Checksum/member set mismatch')
  for name in checks:
   h=hashlib.sha256();actual=0
   with z.open(name) as f:
    for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk);actual+=len(chunk)
   if actual!=z.getinfo(name).file_size or h.hexdigest()!=checks[name]:raise CapsuleError('Payload digest mismatch: '+name)
   if name in payloads and (payloads[name].get('sha256')!=h.hexdigest() or payloads[name].get('size')!=actual):raise CapsuleError('Capsule payload claim mismatch')
  manifest=read_json('FILE-MANIFEST.json');complete=read_json('COMPLETENESS.json')
  if not isinstance(manifest,dict) or not isinstance(manifest.get('entries'),list):raise CapsuleError('Invalid file manifest schema')
  if len(manifest['entries'])>max_entries:raise CapsuleError('Excessive logical entry count')
  roots=meta.get('roots')
  if not isinstance(roots,list) or not roots or any(not isinstance(r,dict) or not isinstance(r.get('id'),str) for r in roots):raise CapsuleError('Invalid root schema')
  root_ids={r['id'] for r in roots}
  logical=set()
  for e in manifest['entries']:
   if not isinstance(e,dict) or e.get('disposition') not in discovery.DISPOSITIONS:raise CapsuleError('Invalid file disposition')
   if e.get('root_id') not in root_ids or e.get('type') not in ['file','directory','symlink','special','unknown']:raise CapsuleError('Invalid entry type/root')
   rel=e.get('path')
   if not isinstance(rel,str) or rel.startswith('/') or any(p in ('','.','..') for p in rel.split('/')):raise CapsuleError('Unsafe logical project path')
   key=(e.get('root_id'),rel)
   if key in logical:raise CapsuleError('Duplicate logical file entry')
   logical.add(key)
   if e['disposition'].startswith('INCLUDED') and e.get('type') in ['file','symlink']:
    obj=e.get('object','');digest=e.get('sha256')
    if not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest) or obj!='objects/'+digest or obj not in payloads or payloads[obj]['sha256']!=digest or e.get('size')!=payloads[obj]['size']:raise CapsuleError('Missing/mismatched file object')
  if not isinstance(complete,dict) or complete.get('entries')!=len(manifest['entries']) or not complete.get('all_entries_accounted'):raise CapsuleError('Completeness count mismatch')
  counts={d:sum(e['disposition']==d for e in manifest['entries']) for d in discovery.DISPOSITIONS}
  if complete.get('counts')!=counts:raise CapsuleError('Completeness disposition mismatch')
  knowledge={name.removeprefix('knowledge/'):z.read(name).decode('utf-8',errors='replace') for name in names if name.startswith('knowledge/') and name.endswith('.md') and z.getinfo(name).file_size<=2000000}
  return {'capsule':meta,'metadata':meta,'manifest':manifest,'completeness':complete,'knowledge':knowledge,'archive_sha256':sha(path),'verified':True,'members':len(names),'expanded_bytes':total,'authenticity':'NOT_ESTABLISHED_BY_HASHES'}

inspect=verify
