"""Return continuation protocol: hash-based three-way preview, selection, rollback.

Databases are snapshots for separate record reconciliation, never text patches.
No change is applied merely by receiving or inspecting a return capsule.
"""
from __future__ import annotations
import base64,datetime,hashlib,json,os,re,shutil,sqlite3,stat,tempfile,uuid,zipfile
from pathlib import Path
from . import receiver as r
FORMAT='genesis-relay-return';VERSION='1.0';MAX_ENTRIES=20000;MAX_EXPANDED=2*1024**3
_SECRET_PATTERNS=[re.compile(p) for p in [rb'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',rb'\bgh[pousr]_[A-Za-z0-9]{25,}',rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{30,}']]
def _canonical(obj):return (json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
def _private_path(path):
 parts=Path(path).parts;name=Path(path).name.lower()
 return name.startswith('.env.') or name=='.envrc' or any(x in {'.codex','.ssh','.relay-venv','.venv','venv','__pycache__','runtime','logs'} for x in parts) or name in {'access.json','auth.json','sessions.json','jupyter-secret.json','mobile-panel.json','service.json','service.log','.env','id_rsa','id_ed25519'} or name.endswith(('.key','.pem','.p12','.pfx','-wal','-shm','-journal'))
def _secret(path,values=()):
 carry=b''
 with Path(path).open('rb') as f:
  for data in iter(lambda:f.read(1024*1024),b''):
   raw=carry+data
   if any(p.search(raw) for p in _SECRET_PATTERNS) or any(value in raw for value in values):return True
   carry=raw[-512:]
 if Path(path).suffix.lower()=='.json' and Path(path).stat().st_size<2_000_000:
  try:
   def visit(v):
    if isinstance(v,dict):
     for k,x in v.items():
      if re.fullmatch('(?i)(password|api[_-]?key|access[_-]?token|refresh[_-]?token|secret|csrf)',str(k)) and isinstance(x,str) and len(x)>4:return True
      if visit(x):return True
    elif isinstance(v,list):return any(visit(x) for x in v)
    return False
   return visit(r.read(path))
  except (ValueError,UnicodeError):pass
 return False

def _stable_copy(source,target):
 source=Path(source);before=source.stat();h=hashlib.sha256()
 with source.open('rb') as src,target.open('xb') as dst:
  for block in iter(lambda:src.read(1024*1024),b''):h.update(block);dst.write(block)
  dst.flush();os.fsync(dst.fileno())
 after=source.stat()
 if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):raise RuntimeError('File changed during return capture: '+str(source.name))
 return h.hexdigest()

def _database_copy(source,target):
 conn=sqlite3.connect('file:'+Path(source).as_posix()+'?mode=ro',uri=True)
 try:
  if conn.execute("select 1 from sqlite_master where type='table' and name='jobs'").fetchone() and conn.execute("select 1 from jobs where status='running' limit 1").fetchone():raise RuntimeError('A laboratory job is running; wait before making a return snapshot')
  dst=sqlite3.connect(target)
  try:conn.backup(dst);assert dst.execute('pragma integrity_check').fetchone()[0]=='ok'
  finally:dst.close()
 finally:conn.close()
 return r.digest(target)

def create_return(base_receipt,output,parent_return=None):
 receipt=r.read(base_receipt) if isinstance(base_receipt,(str,Path)) else dict(base_receipt);project=Path(receipt['project_path']).resolve();baseline_path=Path(receipt['adaptation_baseline_path']);baseline=r.read(baseline_path)
 if r.digest(baseline_path)!=receipt['adaptation_baseline_sha256']:raise ValueError('Adaptation baseline changed; cannot establish common base')
 output=Path(output).absolute()
 try:output.relative_to(project);raise ValueError('Return output must be outside the working project')
 except ValueError as error:
  if str(error).startswith('Return output'):raise
 values=[]
 for credential in [project/'private/access.json',project/'private/jupyter-secret.json']:
  try:
   data=r.read(credential)
   for key in ['password','token','secret','csrf']:
    if isinstance(data.get(key),str) and len(data[key])>=8:values.append(data[key].encode())
   if data.get('username') and data.get('password'):values.append(base64.b64encode((str(data['username'])+':'+str(data['password'])).encode()))
  except (OSError,ValueError):pass
 current=r.working_inventory(project);base=baseline['files'];manifest=[];source_map={m['destination_path']:m for m in receipt.get('mapping',[]) if m.get('root_id','project')=='project'};ident='return-'+uuid.uuid4().hex
 with tempfile.TemporaryDirectory(prefix='relay-return-') as tmp:
  objects=Path(tmp);seen=set()
  for name in sorted(set(current)|set(base)):
   before=base.get(name);after=current.get(name)
   if before and after and before['sha256']==after['sha256'] and before.get('mode')==after.get('mode'):continue
   r._parts(name);mapping=source_map.get(name,{});source_name=mapping.get('source_path',name);r._parts(source_name)
   item={'path':source_name,'working_path':name,'base_sha256':before['sha256'] if before else None,'source_base_sha256':mapping.get('sha256',before['sha256'] if before else None),'new_sha256':None,'operation':'DELETE' if after is None else 'ADD' if before is None else 'UPDATE','mode':after.get('mode',0o644) if after else None,'size':after.get('size',0) if after else 0,'reason':None}
   if _private_path(name):item.update(operation='EXCLUDED_WITH_REASON',reason='Credential, installed environment, ephemeral runtime or service log; not returned')
   elif after is not None:
    source=project/name
    if _secret(source,values):item.update(operation='EXCLUDED_WITH_REASON',reason='Possible secret detected; excluded without changing the original')
    else:
     staged=objects/uuid.uuid4().hex
     with source.open('rb') as probe:is_database=probe.read(16)==b'SQLite format 3\x00'
     digest=_database_copy(source,staged) if is_database else _stable_copy(source,staged)
     item.update(new_sha256=digest,object='objects/'+digest,size=staged.stat().st_size)
     if is_database:item.update(operation='DATABASE_SNAPSHOT',reason='Separate SQLite backup; record reconciliation required; never text merged')
     final=objects/digest
     if not final.exists():os.replace(staged,final)
     else:staged.unlink()
     seen.add(digest)
   manifest.append(item)
  # New destination verification/adaptation/handoff records travel as separate
  # additions, never as replacement source-machine configuration.
  records=project/'_relay'
  if records.is_dir():
   ignored={'knowledge','environments','history','source-guidance','source-tree','symlinks','references','unmaterializable'}
   for folder,dirs,files in os.walk(records,followlinks=False):
    dirs[:]=sorted(d for d in dirs if d not in ignored and not (Path(folder)/d).is_symlink())
    for name in sorted(files):
     record=Path(folder)/name;rel=record.relative_to(records).as_posix()
     if rel in ['PATH-MAPPING.json','RECONSTRUCTION.json','adaptation-baseline.json'] or record.is_symlink():continue
     path='_relay-returned/'+ident+'/'+rel
     item={'path':path,'working_path':'_relay/'+rel,'base_sha256':None,'source_base_sha256':None,'new_sha256':None,'operation':'ADD','mode':record.stat().st_mode&0o777,'size':record.stat().st_size,'reason':'Destination-local verification, adaptation or continuation record; preserved separately from original source configuration.'}
     if _private_path(rel) or _secret(record,values):item.update(operation='EXCLUDED_WITH_REASON',reason='Possible secret/private runtime data excluded from destination records')
     else:
      staged=objects/uuid.uuid4().hex;digest=_stable_copy(record,staged);item.update(new_sha256=digest,object='objects/'+digest);final=objects/digest
      if final.exists():staged.unlink()
      else:os.replace(staged,final)
      seen.add(digest)
     manifest.append(item)
  after_capture=r.working_inventory(project)
  if any(name not in after_capture or after_capture[name]['sha256']!=data['sha256'] for name,data in current.items() if not _private_path(name)):raise RuntimeError('Working copy changed during return capture; retry after project-scoped quiescence')
  metadata={'format':FORMAT,'format_version':VERSION,'return_id':ident,'parent_return':parent_return,'base_capsule_id':receipt['capsule_id'],'base_archive_sha256':receipt['archive_sha256'],'adaptation_baseline_sha256':receipt['adaptation_baseline_sha256'],'route':receipt['route'],'created_at':r.now(),'destination_identity':r.destination_capabilities(),'entry_count':len(manifest),'privacy':'Private continuation data; not authorized for public upload.','database_policy':'Manual/logical reconciliation only; no ordinary file apply.'}
  letter=('# GENESIS Relay return letter\n\nBase capsule: '+receipt['capsule_id']+'\nReturn: '+ident+'\nRoute: '+receipt['route']+'\n\nThis return preserves observed changed/new files and destination records. It does not establish transport, recipient acceptance or the author of the checksum reference.\n\n'+''.join('- '+op+': '+str(sum(e['operation']==op for e in manifest))+'\n' for op in sorted({e['operation'] for e in manifest}))+'\nUse a three-way preview before selected application. Review platform adaptations and guidance separately. Database snapshots require logical/record reconciliation and are never ordinary text patches. Preserve independent source work and use rollback receipts.\n').encode()
  docs={'RETURN.json':_canonical(metadata),'RETURN-MANIFEST.json':_canonical({'entries':manifest}),'RETURN-LETTER.md':letter};checks={name:hashlib.sha256(raw).hexdigest() for name,raw in docs.items()}
  checks.update({'objects/'+digest:digest for digest in seen});output.parent.mkdir(parents=True,exist_ok=True,mode=0o700);partial=output.with_name(output.name+'.partial')
  if output.exists() or partial.exists():raise ValueError('Return output or partial already exists; never overwrite a previous capsule')
  try:
   with zipfile.ZipFile(partial,'w',compression=zipfile.ZIP_DEFLATED,allowZip64=True) as z:
    partial.chmod(0o600)
    for name,raw in docs.items():z.writestr(name,raw)
    for digest in sorted(seen):z.write(objects/digest,'objects/'+digest)
    z.writestr('SHA256SUMS.txt',''.join(h+'  '+name+'\n' for name,h in sorted(checks.items())))
   verified=verify_return(partial);os.replace(partial,output);output.chmod(0o600)
  except Exception:raise # Retain the owned .partial for diagnosis; never replace last valid output.
 external=output.with_name(output.name+'.sha256');r.atomic(external,r.digest(output)+'  '+output.name+'\n')
 return {'return_id':ident,'path':str(output),'sha256':r.digest(output),'base_capsule_id':receipt['capsule_id'],'entries':len(manifest),'operations':{op:sum(e['operation']==op for e in manifest) for op in sorted({e['operation'] for e in manifest})},'state':'VERIFIED_FOR_TRANSFER','transport_complete':False,'checksum_path':str(external)}

def verify_return(path):
 archive_path=Path(path)
 with zipfile.ZipFile(archive_path) as z:
  infos=z.infolist()
  if len(infos)>MAX_ENTRIES:raise ValueError('Return exceeds entry limit')
  names=[];seen=set();size=0
  for info in infos:
   name=info.filename
   if name in seen or name.casefold() in {x.casefold() for x in seen}:raise ValueError('Duplicate return archive entry')
   if not (name in ['RETURN.json','RETURN-MANIFEST.json','RETURN-LETTER.md','SHA256SUMS.txt'] or re.fullmatch('objects/[a-f0-9]{64}',name)):raise ValueError('Unsafe/unrecognized return archive path')
   if stat.S_ISLNK(info.external_attr>>16) or info.is_dir():raise ValueError('Return links/directories are not permitted')
   if info.file_size>512*1024**2:raise ValueError('Return member exceeds expansion limit')
   size+=info.file_size
   if size>MAX_EXPANDED:raise ValueError('Return expanded size exceeds cap')
   if info.compress_size and info.file_size/info.compress_size>1000:raise ValueError('Suspicious return expansion ratio')
   seen.add(name);names.append(name)
  if not {'RETURN.json','RETURN-MANIFEST.json','SHA256SUMS.txt'}<=seen:raise ValueError('Incomplete return capsule')
  if z.getinfo('RETURN.json').file_size>1_000_000 or z.getinfo('RETURN-MANIFEST.json').file_size>8_000_000 or z.getinfo('SHA256SUMS.txt').file_size>2_000_000:raise ValueError('Return metadata exceeds cap')
  metadata=json.loads(z.read('RETURN.json'));manifest=json.loads(z.read('RETURN-MANIFEST.json'));major=str(metadata.get('format_version','')).split('.')[0]
  if metadata.get('format')!=FORMAT or not isinstance(metadata.get('format_version'),str) or major!='1':raise ValueError('Unsupported return format major version')
  if not re.fullmatch('return-[a-f0-9]{32}',str(metadata.get('return_id',''))):raise ValueError('Invalid return identity')
  checks={}
  for line in z.read('SHA256SUMS.txt').decode().splitlines():
   h,name=line.split('  ',1)
   if name in checks or not re.fullmatch('[a-f0-9]{64}',h):raise ValueError('Invalid return checksum entry')
   checks[name]=h
  if set(checks)!=seen-{'SHA256SUMS.txt'}:raise ValueError('Return checksum member set differs')
  for name,expected in checks.items():
   h=hashlib.sha256()
   with z.open(name) as f:
    for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
   if h.hexdigest()!=expected:raise ValueError('Return payload hash mismatch')
  entries=manifest.get('entries');paths=set();objects=set()
  if not isinstance(entries,list) or metadata.get('entry_count')!=len(entries):raise ValueError('Return manifest entry count differs')
  for item in entries:
   path=item.get('path');r._parts(path)
   if path in paths:raise ValueError('Duplicate returned logical path')
   paths.add(path)
   if item.get('operation') not in ['ADD','UPDATE','DELETE','DATABASE_SNAPSHOT','EXCLUDED_WITH_REASON']:raise ValueError('Unknown return operation')
   for key in ['base_sha256','source_base_sha256','new_sha256']:
    if item.get(key) is not None and not re.fullmatch('[a-f0-9]{64}',str(item[key])):raise ValueError('Invalid return base/result hash')
   obj=item.get('object');operation=item['operation']
   if operation in ['ADD','UPDATE','DATABASE_SNAPSHOT'] and (not obj or not item.get('new_sha256')):raise ValueError('Returned file is missing its payload')
   if operation=='ADD' and item.get('base_sha256') is not None:raise ValueError('Added file cannot have an adaptation base')
   if operation in ['UPDATE','DELETE'] and item.get('base_sha256') is None:raise ValueError('Changed/deleted file needs a common-base hash')
   if operation in ['DELETE','EXCLUDED_WITH_REASON'] and (obj is not None or item.get('new_sha256') is not None):raise ValueError('Non-payload return operation has unexpected bytes')
   if isinstance(item.get('size'),bool) or not isinstance(item.get('size'),int) or item['size']<0:raise ValueError('Invalid return size')
   mode=item.get('mode')
   if mode is not None and (isinstance(mode,bool) or not isinstance(mode,int) or not 0<=mode<=0o777):raise ValueError('Invalid return file mode')
   if obj:
    if obj!='objects/'+str(item.get('new_sha256')) or checks.get(obj)!=item['new_sha256']:raise ValueError('Return object differs from manifest')
    if z.getinfo(obj).file_size!=item['size']:raise ValueError('Return object size differs')
    objects.add(obj)
  if objects!={name for name in seen if name.startswith('objects/')}:raise ValueError('Unreferenced/missing return objects')
 return {'metadata':metadata,'manifest':manifest,'sha256':r.digest(archive_path),'status':'PASSED'}

def preview_return(return_path,current_project):
 verified=verify_return(return_path);root=Path(current_project).absolute()
 if not root.is_dir() or root.is_symlink():raise ValueError('Select an existing independent project directory')
 ident=verified['metadata']['return_id'];history=root/'.relay-return-history'/ident/'receipt.json'
 prior=r.read(history) if history.exists() else None;rows=[]
 for item in verified['manifest']['entries']:
  path=item['path'];target=r._within(root,root.joinpath(*path.split('/')));current=r.digest(target) if target.is_file() and not target.is_symlink() else None
  op=item['operation'];base=item.get('base_sha256');source_base=item.get('source_base_sha256');new=item.get('new_sha256')
  if prior:decision='ALREADY_PROCESSED'
  elif op=='EXCLUDED_WITH_REASON':decision='EXCLUDED'
  elif op=='DATABASE_SNAPSHOT':decision='DATABASE_RECONCILIATION_REQUIRED'
  elif Path(path).name in ['AGENTS.md','AGENTS.override.md']:decision='GUIDANCE_REVIEW_REQUIRED'
  elif new is not None and current==new:decision='ALREADY_PRESENT'
  elif target.exists() and not target.is_file():decision='CONFLICT'
  elif source_base!=base and base is not None:decision='PLATFORM_ADAPTATION_REVIEW'
  elif op=='ADD':decision='APPLICABLE' if not target.exists() else 'CONFLICT'
  elif op=='DELETE':decision='ALREADY_PRESENT' if not target.exists() else 'DELETE_REQUIRES_SELECTION' if current==base else 'CONFLICT'
  else:decision='APPLICABLE' if current==base else 'CONFLICT'
  rows.append({**item,'current_sha256':current,'decision':decision})
 return {'schema_version':1,'return_id':ident,'return_path':str(Path(return_path).absolute()),'return_sha256':verified['sha256'],'current_project':str(root),'base_capsule_id':verified['metadata']['base_capsule_id'],'adaptation_baseline_sha256':verified['metadata']['adaptation_baseline_sha256'],'created_at':r.now(),'entries':rows,'conflicts':[x['path'] for x in rows if x['decision'] in ['CONFLICT','PLATFORM_ADAPTATION_REVIEW','GUIDANCE_REVIEW_REQUIRED']],'database_reconciliation':[x['path'] for x in rows if x['decision']=='DATABASE_RECONCILIATION_REQUIRED'],'duplicate':bool(prior),'prior_state':prior.get('state') if prior else None,'preview_only':True}

def apply_return(plan,selected=None):
 plan=r.read(plan) if isinstance(plan,(str,Path)) else dict(plan);root=Path(plan['current_project']);verified=verify_return(plan['return_path'])
 if verified['sha256']!=plan['return_sha256']:raise ValueError('Return changed since preview')
 current=preview_return(plan['return_path'],root);ident=plan['return_id'];history=root/'.relay-return-history'/ident;receipt_path=history/'receipt.json'
 with r.lock(root/'.relay-return-history'):
  if receipt_path.exists():
   prior=r.read(receipt_path);return dict(prior,duplicate_import=True,recovery_required=prior.get('state')=='APPLYING')
  selected_set=set(selected) if selected is not None else {e['path'] for e in plan['entries'] if e['decision']=='APPLICABLE'}
  lookup={e['path']:e for e in current['entries']};old={e['path']:e for e in plan['entries']};changes=[]
  for name in sorted(selected_set):
   if name not in lookup:raise ValueError('Selected path was not in return preview')
   row=lookup[name]
   if row['decision'] not in ['APPLICABLE','DELETE_REQUIRES_SELECTION']:raise ValueError('Selected change needs separate conflict/database/guidance review: '+name)
   if row['current_sha256']!=old[name]['current_sha256']:raise ValueError('Independent work changed after preview: '+name)
   target=r._within(root,root.joinpath(*name.split('/')))
   if _private_path(name):raise ValueError('Refusing credential/runtime application')
   changes.append({**row,'before_existed':target.is_file(),'before_mode':target.stat().st_mode&0o777 if target.is_file() else None})
  history.mkdir(parents=True,exist_ok=False,mode=0o700);backups=history/'before';backups.mkdir(mode=0o700);receipt={'return_id':ident,'base_capsule_id':plan['base_capsule_id'],'return_sha256':verified['sha256'],'project_path':str(root),'receipt_path':str(receipt_path),'state':'APPLYING','created_at':r.now(),'changes':changes,'applied':[],'failures':[]}
  for index,row in enumerate(changes):
   target=root/row['path']
   if row['before_existed']:
    backup=backups/str(index);_stable_copy(target,backup);row['backup']=str(backup)
  r.atomic(receipt_path,receipt)
  try:
   with zipfile.ZipFile(plan['return_path']) as z:
    for row in changes:
     target=r._within(root,root.joinpath(*row['path'].split('/')));existing=r.digest(target) if target.is_file() else None
     if existing!=row['current_sha256']:raise ValueError('Independent work changed during application')
     receipt['in_progress']=row['path'];r.atomic(receipt_path,receipt)
     if row['operation']=='DELETE':target.unlink()
     else:
      target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_name('.'+target.name+'.return-partial')
      with z.open(row['object']) as src,temp.open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024);dst.flush();os.fsync(dst.fileno())
      if r.digest(temp)!=row['new_sha256']:raise ValueError('Returned bytes changed during application')
      os.replace(temp,target)
      if os.name!='nt':target.chmod(int(row.get('mode',0o644))&0o777)
     receipt['applied'].append(row['path']);receipt['in_progress']=None;r.atomic(receipt_path,receipt)
   receipt.update(state='APPLIED',finished_at=r.now());r.atomic(receipt_path,receipt);return receipt
  except Exception as error:
   receipt['failures'].append({'at':r.now(),'type':type(error).__name__,'error':str(error)[:500]});r.atomic(receipt_path,receipt);raise

def rollback_return(receipt):
 p=r.read(receipt) if isinstance(receipt,(str,Path)) else dict(receipt);root=Path(p['project_path']);conflicts=[]
 with r.lock(root/'.relay-return-history'):
  stored=r.read(p['receipt_path'])
  if stored['state']=='ROLLED_BACK':return dict(stored,duplicate_rollback=True)
  for row in reversed(stored['changes']):
   if row['path'] not in stored['applied'] and row['path']!=stored.get('in_progress'):continue
   target=r._within(root,root.joinpath(*row['path'].split('/')));current=r.digest(target) if target.is_file() else None;expected=None if row['operation']=='DELETE' else row['new_sha256']
   if row['path']==stored.get('in_progress') and current==row['current_sha256']:continue
   if current!=expected:conflicts.append(row['path']);continue
   if row['before_existed']:
    backup=Path(row['backup'])
    if r.digest(backup)!=row['current_sha256']:raise ValueError('Rollback backup changed')
    temp=target.with_name('.'+target.name+'.rollback-partial');shutil.copyfile(backup,temp);os.replace(temp,target)
    if os.name!='nt':target.chmod(row['before_mode'])
   else:target.unlink()
  stored['rollback_conflicts']=conflicts;stored['state']='ROLLBACK_CONFLICT' if conflicts else 'ROLLED_BACK';stored['rolled_back_at']=r.now();r.atomic(stored['receipt_path'],stored);return stored
