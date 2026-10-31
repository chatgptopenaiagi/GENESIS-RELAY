"""Explicit working-copy Science Lab adaptation and destination acceptance.

This module never mutates source evidence or a source installation. It uses
existing compatible scientific packages through a new project-owned venv, keeps
new login credentials local, and qualifies LOCAL_LINUX separately from Windows.
"""
from __future__ import annotations
import base64,datetime,difflib,hashlib,json,os,platform,secrets,shlex,shutil,signal,socket,sqlite3,subprocess,sys,time,urllib.error,urllib.request,uuid
from pathlib import Path

SOURCE_PROTECTED=Path('/root/GENESIS-SCIENCE-LAB')
THREADS={k:'1' for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']}
REQUIRED=['numpy','scipy','sympy','mpmath','pandas','networkx','matplotlib','rdkit']

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def load(path,default=None):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):return {} if default is None else default

def write(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name('.'+p.name+'-'+uuid.uuid4().hex+'.partial');tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');tmp.chmod(0o600);os.replace(tmp,p)
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()
def project_root(path):
    p=Path(path).absolute()
    if p.resolve()==SOURCE_PROTECTED.resolve():raise ValueError('Relay laboratory adapters refuse the original source installation')
    if '_relay' not in p.parts and not (p/'_relay').is_dir():
        # The trusted receiver creates its own project-owned provenance directory.
        raise ValueError('Use a new Relay receiver working copy with _relay provenance')
    for name in ['server.py','worker.py','engine.py','catalogue.py']:
        if not (p/name).is_file():raise ValueError('Working laboratory source is incomplete: '+name)
    return p

def identity(pid):
    if sys.platform!='linux':return {}
    try:
        p=Path('/proc')/str(int(pid));tail=(p/'stat').read_text().rsplit(')',1)[1].split();args=[v.decode(errors='replace') for v in (p/'cmdline').read_bytes().split(b'\0') if v]
        if not args:return {}
        return {'pid':int(pid),'start':tail[19],'args':args,'cwd':str((p/'cwd').resolve())}
    except (OSError,ValueError,IndexError):return {}

def owned(record,project):
    actual=identity(record.get('pid',0));return bool(actual and actual==record.get('identity') and str(Path(project)/'server.py') in actual['args'] and actual['cwd']==str(Path(project).resolve()))

def choose_port():
    for port in range(8140,8160):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            try:sock.bind(('127.0.0.1',port));return port
            except OSError:pass
    raise RuntimeError('No free Relay laboratory port in 8140..8159; no existing process was stopped')

def _replace_once(text,before,after):
    if text.count(before)!=1:raise ValueError('Unknown laboratory source revision; expected one adaptation anchor: '+before[:90])
    return text.replace(before,after,1)

def dependency_probe(python):
    code="import importlib,json,sys,platform; names="+repr(REQUIRED)+"; found={}; missing=[]\nfor name in names:\n try:\n  m=importlib.import_module(name); found[name]=str(getattr(m,'__version__','unknown'))\n except Exception as e:missing.append({'name':name,'error':type(e).__name__})\nprint(json.dumps({'interpreter':sys.executable,'prefix':sys.prefix,'base_prefix':sys.base_prefix,'machine':platform.machine(),'platform':platform.system(),'versions':found,'missing':missing}))"
    env=os.environ.copy();env.update(THREADS);env.update(MPLBACKEND='Agg');env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
    try:
        result=subprocess.run([str(python),'-I','-c',code],capture_output=True,text=True,env=env,timeout=90)
        if result.returncode or len(result.stdout)>100000:raise RuntimeError('Dependency import probe failed')
        return json.loads(result.stdout)
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:return {'interpreter':str(python),'missing':[{'name':'probe','error':type(error).__name__}]}

def adapt_project(project_path,python=None,route='LOCAL_LINUX',capsule_id=None,capsule_sha256=None):
    project=project_root(project_path);python=Path(python or sys.executable).absolute();record=project/'_relay/ADAPTATION.json'
    if route not in ['LOCAL_LINUX','WSL_LINUX_X64','NATIVE_WINDOWS_X64']:raise ValueError('Choose an explicit supported route')
    if route=='NATIVE_WINDOWS_X64':
        return {'status':'BLOCKED','route':route,'reason':'Native Windows execution is not qualified: source service uses fcntl/resource and Unix process groups. Use the explicit Windows plan/recipes; do not treat Linux parsing as native acceptance.','project_path':str(project)}
    if platform.system()!='Linux':return {'status':'BLOCKED','route':route,'reason':'Linux source service requires a Linux execution environment','project_path':str(project)}
    is_wsl='microsoft' in platform.release().lower() or bool(os.environ.get('WSL_INTEROP'))
    if route=='WSL_LINUX_X64' and (not is_wsl or platform.machine().lower() not in ['x86_64','amd64']):return {'status':'BLOCKED','route':route,'reason':'WSL_LINUX_X64 must execute on actual WSL x64, not be inferred from a Linux-only test.','project_path':str(project)}
    existing=load(record)
    if existing.get('status')=='ADAPTED':
        if existing.get('route')!=route:raise ValueError('Working copy is already adapted to another route')
        if sha(project/'server.py')!=existing.get('server_after_sha256'):raise ValueError('Adapted server was edited; preserve and review changes before adapting again')
        install_destination_controls(project);install_destination_registry(project)
        return load(record)
    if not python.is_file() or not os.access(python,os.X_OK):raise ValueError('Choose an existing absolute destination Python interpreter')
    venv=project/'.relay-venv';owner=venv/'RELAY-ENVIRONMENT.json'
    if venv.exists() and not owner.is_file():raise ValueError('An unowned destination environment exists; it was not overwritten')
    env=os.environ.copy();env.update(THREADS);env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
    if not venv.exists():
        subprocess.run([str(python),'-m','venv','--without-pip','--system-site-packages',str(venv)],check=True,capture_output=True,text=True,timeout=90,env=env)
        write(owner,{'created_at':now(),'base_interpreter':str(python),'route':route,'method':'new project-owned venv; existing destination system-site packages explicitly reused; no source ARM binary environment copied'})
    executable=venv/'bin/python';dependencies=dependency_probe(executable);write(project/'_relay/DESTINATION-ENVIRONMENT.json',dependencies)
    if dependencies.get('missing'):return {'status':'BLOCKED','route':route,'project_path':str(project),'missing_dependencies':dependencies['missing'],'environment':str(executable),'reason':'Required imports are missing or incompatible. No packages were installed or modified in unrelated environments.'}
    source=(project/'server.py').read_text(encoding='utf-8');updated=source;port=choose_port()
    updated=_replace_once(updated,'BASE=Path(__file__).resolve().parent;os.chdir(BASE);os.umask(0o077)','BASE=Path(__file__).resolve().parent;os.chdir(BASE);os.umask(0o077)\nRELAY_CONTEXT=json.loads((BASE/\'_relay/ADAPTATION.json\').read_text())\nRELAY_PORT='+str(port))
    updated=_replace_once(updated,"str(BASE/'.venv/bin/python')",'sys.executable')
    updated=updated.replace("'127.0.0.1:8090'","'127.0.0.1:'+str(RELAY_PORT)").replace("'localhost:8090'","'localhost:'+str(RELAY_PORT)")
    updated=updated.replace("'http://127.0.0.1:8090'","'http://127.0.0.1:'+str(RELAY_PORT)").replace("'http://localhost:8090'","'http://localhost:'+str(RELAY_PORT)")
    updated=_replace_once(updated,"ThreadingHTTPServer(('127.0.0.1',8090),Handler)","ThreadingHTTPServer(('127.0.0.1',RELAY_PORT),Handler)")
    updated=_replace_once(updated,"'user_agent':self.headers.get('User-Agent','')[:160]","'user_agent':self.headers.get('User-Agent','')[:160],'relay':{key:RELAY_CONTEXT.get(key) for key in ['capsule_id','capsule_sha256','route','destination_id']}")
    compile(updated,str(project/'server.py'),'exec')
    config={'schema_version':1,'status':'ADAPTED','adapted_at':now(),'project_path':str(project),'interpreter':str(executable),'base_interpreter':str(python),'environment_method':'New destination venv using existing compatible destination system-site packages. This is not an offline-ready Windows environment.','route':route,'is_wsl':is_wsl,'destination_id':platform.node()+'-'+platform.machine(),'platform':platform.system(),'machine':platform.machine(),'capsule_id':capsule_id,'capsule_sha256':capsule_sha256,'url':f'http://127.0.0.1:{port}/','port':port,'server_before_sha256':hashlib.sha256(source.encode()).hexdigest(),'server_after_sha256':hashlib.sha256(updated.encode()).hexdigest(),'kernel_hashes':{name:sha(project/name) for name in ['engine.py','worker.py','catalogue.py']},'adaptations':['Source evidence left unchanged.','Working server: destination-local port, host/origin allowlist and sys.executable worker interpreter.','New result execution_context carries destination identity and source capsule reference.','New destination credentials generated by the original laboratory authentication mechanism.'],'limitations':['LOCAL_LINUX proves only a relocated Linux reconstruction.','Native Windows and WSL qualification require actual execution on those routes.','Scientific operation acceptance has not yet run.']}
    write(record,config);(project/'server.py').write_text(updated,encoding='utf-8');(project/'_relay/adaptations').mkdir(exist_ok=True)
    (project/'_relay/adaptations/server.py.diff').write_text(''.join(difflib.unified_diff(source.splitlines(True),updated.splitlines(True),fromfile='source-evidence/server.py',tofile='working-copy/server.py')),encoding='utf-8')
    (project/'_relay/OPEN-LAB.md').write_text('# Destination laboratory\n\nStart only after reviewing the restoration and dependency plan.\n\nInterpreter: `'+str(executable)+'`\n\nCommand: `"'+str(executable)+'" "'+str(project/'server.py')+'"`\n\nURL: '+config['url']+'\n\nUse destination `private/access.json` only in the local operator terminal. Source credentials were excluded. This working copy has focused Linux adaptations; native Windows has not been accepted.\n',encoding='utf-8')
    install_destination_controls(project);install_destination_registry(project)
    return load(record)

def _config(project):
    project=project_root(project);config=load(project/'_relay/ADAPTATION.json')
    if config.get('status')!='ADAPTED' or config.get('project_path')!=str(project):raise ValueError('Run the explicit destination adaptation first')
    if config.get('port') not in range(8140,8160) or config.get('url')!=f"http://127.0.0.1:{config.get('port')}/":raise ValueError('Invalid owned laboratory URL')
    return project,config

def _opener():return urllib.request.build_opener(urllib.request.ProxyHandler({}))
def _request(project,path,body=None,csrf=None,timeout=20):
    project,config=_config(project);credentials=load(project/'private/access.json');secret='Basic '+base64.b64encode((credentials['username']+':'+credentials['password']).encode()).decode();headers={'Authorization':secret,'User-Agent':'GENESIS-Relay-destination-acceptance'}
    if body is not None:headers.update({'Content-Type':'application/json','Origin':config['url'].rstrip('/'),'X-CSRF-Token':csrf or ''})
    request=urllib.request.Request(config['url'].rstrip('/')+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    with _opener().open(request,timeout=timeout) as response:
        if response.headers.get_content_type()=='application/json':return json.load(response)
        return response.read()

def status(project_path):
    project,config=_config(project_path);record=load(project/'_relay/service.json');is_owned=owned(record,project)
    result={'status':'STOPPED','url':config['url'],'owned':is_owned,'project_path':str(project),'observed_at':now()}
    if is_owned:
        try:_request(project,'/api/catalogue');result['status']='RUNNING'
        except (OSError,ValueError,KeyError):result['status']='UNKNOWN'
    elif identity(record.get('pid',0)):result['status']='UNKNOWN'
    return result

def install_destination_controls(project_path):
    """Replace working-only source launchers with owned destination controls.

    Safe to call on an existing adaptation before/during acceptance: no service,
    kernel or database is changed. Familiar names can never reuse source port8090.
    """
    project,config=_config(project_path);archive=project/'_relay/source-launchers';archive.mkdir(parents=True,exist_ok=True)
    previous=config.get('destination_controls',{}).get('files',{});files={};changes=[]
    trusted_python=str(Path(sys.executable).absolute());trusted_module=str(Path(__file__).with_name('lab_cli.py').resolve())
    controls={'START-LAB.sh':'start','STOP-LAB.sh':'stop','STATUS-LAB.sh':'status','SHOW-ACCESS.sh':'access','START-SERVICES.sh':'start','STOP-SERVICES.sh':'stop','STATUS.sh':'status'}
    marker=b'# GENESIS_RELAY_DESTINATION_CONTROL\n'
    def replace(name,data,mode):
        target=project/name
        if target.is_symlink():raise ValueError('Refusing an unowned control symlink: '+name)
        old=target.read_bytes() if target.exists() else None;before=hashlib.sha256(old).hexdigest() if old is not None else None
        expected=previous.get(name,{}).get('installed_sha256')
        if expected and before!=expected and old!=data:raise ValueError('Destination control was modified; preserved for review: '+name)
        source=archive/name
        if old is not None and not source.exists() and not old.startswith(b'#!/bin/sh\n'+marker) and b'GENESIS_RELAY_DESTINATION_CLIENT' not in old:
            source.parent.mkdir(parents=True,exist_ok=True)
            with source.open('xb') as output:output.write(old)
            source.chmod(0o600)
        target.parent.mkdir(parents=True,exist_ok=True)
        if old!=data:
            temp=target.with_name('.'+target.name+'-'+uuid.uuid4().hex+'.partial')
            with temp.open('xb') as output:output.write(data);output.flush();os.fsync(output.fileno())
            temp.chmod(mode);os.replace(temp,target);changes.append(name)
        else:target.chmod(mode)
        files[name]={'source_archive':str(source.relative_to(project)) if source.exists() else None,'source_sha256':sha(source) if source.exists() else None,'installed_sha256':hashlib.sha256(data).hexdigest(),'mode':oct(mode)}
    for name,action in controls.items():
        argv=[trusted_python,trusted_module,action,'--project',str(project)]
        data=b'#!/bin/sh\n'+marker+('exec '+shlex.join(argv)+' "$@"\n').encode();replace(name,data,0o700)
    client=project/'tools/lab-client.py'
    if client.is_file():
        raw=client.read_bytes();text=raw.decode('utf-8')
        if 'GENESIS_RELAY_DESTINATION_CLIENT' not in text:
            text=_replace_once(text,'B=Path(__file__).resolve().parent.parent',"B=Path(__file__).resolve().parent.parent\n# GENESIS_RELAY_DESTINATION_CLIENT\nLAB_URL=json.loads((B/'_relay/ADAPTATION.json').read_text())['url'].rstrip('/')")
            if "'http://127.0.0.1:8090'" not in text:raise ValueError('Unknown source client URL; explicit adaptation required')
            text=text.replace("'http://127.0.0.1:8090'",'LAB_URL')
        if 'GENESIS_RELAY_DESTINATION_URL_GUARD' not in text:
            anchor="LAB_URL=json.loads((B/'_relay/ADAPTATION.json').read_text())['url'].rstrip('/')"
            text=_replace_once(text,anchor,anchor+"\n# GENESIS_RELAY_DESTINATION_URL_GUARD\nif LAB_URL not in {'http://127.0.0.1:'+str(port) for port in range(8140,8160)}:raise SystemExit('Destination client requires its owned loopback laboratory URL')")
        compile(text,str(client),'exec');replace('tools/lab-client.py',text.encode('utf-8'),client.stat().st_mode&0o777)
    result={'schema_version':1,'launcher_interpreter':trusted_python,'launcher_module':trusted_module,'files':files,'archived_source_launchers':[value['source_archive'] for value in files.values() if value['source_archive']],'scope':'Mutable destination controls only; immutable source evidence and scientific kernels unchanged.'}
    config['destination_controls']=result;write(project/'_relay/ADAPTATION.json',config);write(project/'_relay/destination-controls.json',result)
    (project/'_relay/OPEN-LAB.md').write_text('# Destination laboratory controls\n\nFrom the restored working directory:\n\n```bash\n./START-LAB.sh\n./STATUS-LAB.sh\n./SHOW-ACCESS.sh\n./STOP-LAB.sh\n```\n\nThese trusted Relay wrappers use the owned destination service and never the source-phone port. The access helper prints destination-local credentials only in an operator terminal.\n\nActual laboratory URL: '+config['url']+'\n\nScientific interpreter: `'+config['interpreter']+'`\n\nTrusted control module: `'+trusted_module+'`\n\nOriginal launchers/client remain inert under `_relay/source-launchers/`. Linux/WSL reconstruction is distinct from unverified native Windows.\n',encoding='utf-8')
    return {**result,'changed_files':changes}

def install_destination_registry(project_path):
    """Expose destination import observations, never inherited source green badges."""
    project,config=_config(project_path);old_config=config.get('destination_registry',{});changed=[]
    archive=project/'_relay/source-registries/SCIENTIFIC-CAPABILITIES.json';target=project/'SCIENTIFIC-CAPABILITIES.json';probe_path=project/'_relay/DESTINATION-ENVIRONMENT.json';probe=load(probe_path);versions=probe.get('versions',{});missing={row.get('name') for row in probe.get('missing',[])}
    if target.is_symlink():raise ValueError('Refusing an unowned capability-registry symlink')
    if archive.is_symlink():raise ValueError('Refusing an unowned source-registry archive symlink')
    if target.exists() and not archive.exists():
        if load(target).get('registry_scope')!='DESTINATION_IMPORT_OBSERVATION':
            archive.parent.mkdir(parents=True,exist_ok=True)
            with archive.open('xb') as output:output.write(target.read_bytes())
            archive.chmod(0o600)
    if old_config.get('registry_sha256') and target.exists() and sha(target)!=old_config['registry_sha256']:raise ValueError('Destination registry was modified; preserved for review')
    engines=[]
    for name in REQUIRED:
        imported=name in versions and name not in missing
        engines.append({'id':'destination:python:'+name,'name':name,'version':versions.get(name),'state':'IMPORTABLE' if imported else 'UNKNOWN','status':'IMPORTABLE' if imported else 'UNKNOWN','interpreter':config['interpreter'],'observed_at':config.get('adapted_at'),'supported_operations':[],'verified_functions':[],'verification_scope':'Destination import observed; named operations are qualified only by separate Relay acceptance.' if imported else 'No successful destination import observation.','known_limitations':['Import success is not verification of all functions or experiments.','Source registry/versions remain archived as historical evidence.']})
    for name,command in [('Open Babel','obabel'),('GNU Octave','octave-cli'),('Gnuplot','gnuplot')]:
        path=shutil.which(command);engines.append({'id':'destination:cli:'+command,'name':name,'version':None,'state':'INSTALLED' if path else 'UNAVAILABLE','status':'INSTALLED' if path else 'UNAVAILABLE','executable':path,'observed_at':config.get('adapted_at'),'supported_operations':[],'verified_functions':[],'verification_scope':'Executable location observed; no functional claim is made by this registry.','known_limitations':['Read Relay acceptance for the exact operation/version evidence actually obtained.']})
    registry={'schema_version':1,'registry_scope':'DESTINATION_IMPORT_OBSERVATION','checked_at_utc':config.get('adapted_at'),'python':config['interpreter'],'laboratory_url':config['url'],'source_capsule_id':config.get('capsule_id'),'source_capsule_sha256':config.get('capsule_sha256'),'route':config['route'],'source_registry_archive':str(archive.relative_to(project)) if archive.exists() else None,'destination_probe':str(probe_path.relative_to(project)),'engines':engines,'qualification':'Import/location observations only. No engine inherits FUNCTIONALLY_VERIFIED from source-machine history. Read _relay/ACCEPTANCE-LATEST.json and additional verification receipts for named operations.'}
    raw=(json.dumps(registry,indent=2,ensure_ascii=False)+'\n').encode()
    if not target.exists() or target.read_bytes()!=raw:
        temp=target.with_name('.'+target.name+'-'+uuid.uuid4().hex+'.partial');temp.write_bytes(raw);temp.chmod(0o600);os.replace(temp,target);changed.append('SCIENTIFIC-CAPABILITIES.json')
    web=project/'web/app.js';web_archive=project/'_relay/source-web/app.js';web_sha=None
    if web.is_file():
        if web.is_symlink() or web_archive.is_symlink():raise ValueError('Refusing an unowned web-adaptation symlink')
        before=web.read_bytes();text=before.decode('utf-8')
        if old_config.get('web_sha256') and sha(web)!=old_config['web_sha256']:raise ValueError('Destination engine view was modified; preserved for review')
        if 'GENESIS_RELAY_DESTINATION_ENGINES' not in text:
            original="el('p','Verified: '+(e.verified_functions||[]).join(', '))"
            replacement="el('p','Destination status: '+(e.state||'UNKNOWN')+' · '+(e.verification_scope||'Not qualified'))"
            text=_replace_once(text,original,replacement)
            text=_replace_once(text,"async function engines(){try{const d=await api('/api/engines');$('#engine-list').replaceChildren();","async function engines(){/* GENESIS_RELAY_DESTINATION_ENGINES */try{const d=await api('/api/engines');$('#engine-list').replaceChildren();$('#engine-list').append(el('p','Destination import check; named operation evidence is in Relay acceptance. Source registry is archived historical evidence.','notice'));")
            text=text.replace("e.name+' · '+e.version","e.name+' · '+(e.version||'version not observed')")
            if not web_archive.exists():
                web_archive.parent.mkdir(parents=True,exist_ok=True)
                with web_archive.open('xb') as output:output.write(before)
                web_archive.chmod(0o600)
            temp=web.with_name('.app.js-'+uuid.uuid4().hex+'.partial');temp.write_text(text,encoding='utf-8');temp.chmod(web.stat().st_mode&0o777);os.replace(temp,web);changed.append('web/app.js')
        web_sha=sha(web)
    result={'registry_sha256':sha(target),'web_sha256':web_sha,'source_registry_archive':str(archive.relative_to(project)) if archive.exists() else None,'source_web_archive':str(web_archive.relative_to(project)) if web_archive.exists() else None,'destination_probe_sha256':sha(probe_path) if probe_path.is_file() else None,'qualification':'IMPORTABLE/location-only; no inherited functional pass.'};config['destination_registry']=result;write(project/'_relay/ADAPTATION.json',config)
    (project/'_relay/DESTINATION-CAPABILITIES.md').write_text('# Destination capability observations\n\nRegistry scope: destination imports and executable locations only.\n\nInterpreter: `'+config['interpreter']+'`\n\nSource registry: `'+(result['source_registry_archive'] or 'not available')+'` (historical).\n\nNo engine is marked functionally verified by import success. Exact named experiment, database and restart results remain in Relay verification receipts.\n',encoding='utf-8')
    return {**result,'changed_files':changed}

def start(project_path):
    project,config=_config(project_path);record=load(project/'_relay/service.json')
    if owned(record,project):
        _request(project,'/api/catalogue');return {'status':'RUNNING','url':config['url'],'owned':True,'pid':record['pid']}
    with socket.socket() as sock:
        # Match HTTPServer's owned bind policy: TIME_WAIT is not an unrelated
        # listener. A real live listener still prevents this bind/listen owner.
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:sock.bind(('127.0.0.1',config['port']))
        except OSError:raise RuntimeError('Destination port is occupied without matching owned identity; no process was changed')
    log=project/'_relay/service.log'
    with log.open('ab') as output:
        log.chmod(0o600);env=os.environ.copy();env.update(THREADS);env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
        process=subprocess.Popen([config['interpreter'],str(project/'server.py')],cwd=project,stdin=subprocess.DEVNULL,stdout=output,stderr=output,start_new_session=True,env=env)
    record={'pid':process.pid,'started_at':now(),'url':config['url']}
    for _ in range(40):
        actual=identity(process.pid)
        if str(project/'server.py') in actual.get('args',[]):record['identity']=actual;break
        if process.poll() is not None:break
        time.sleep(.1)
    write(project/'_relay/service.json',record)
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        if process.poll() is not None:break
        try:
            if owned(record,project) and _request(project,'/api/catalogue'):return {'status':'RUNNING','url':config['url'],'owned':True,'pid':process.pid}
        except (OSError,KeyError,ValueError):time.sleep(.25)
    raise RuntimeError('Owned relocated laboratory did not become ready; inspect destination _relay/service.log')

def stop(project_path):
    project,config=_config(project_path);record=load(project/'_relay/service.json')
    if not owned(record,project):
        if identity(record.get('pid',0)):raise RuntimeError('Recorded PID belongs to another process; nothing was stopped')
        return {'status':'STOPPED','owned':False,'url':config['url']}
    if _request(project,'/api/jobs').get('active'):raise RuntimeError('A destination experiment is active; stop refused')
    os.kill(record['pid'],signal.SIGTERM)
    deadline=time.monotonic()+12
    while time.monotonic()<deadline:
        if not owned(record,project):return {'status':'STOPPED','owned':True,'url':config['url']}
        time.sleep(.1)
    raise RuntimeError('Owned destination laboratory did not stop; no unrelated process was signalled')

def verify_restart(project_path):
    """Independent real restart/persistence proof without recomputing experiments."""
    project,config=_config(project_path);before=_database(project);files={str(path.relative_to(project)):sha(path) for path in (project/'results').rglob('*') if path.is_file()}
    out={'checked_at':now(),'scope':'LOCAL_ROUNDTRIP_ONLY' if config['route']=='LOCAL_LINUX' else config['route'],'project_path':str(project),'source_capsule_id':config.get('capsule_id'),'checks':{},'failures':[]}
    try:
        first=start(project);stop(project);second=start(project);after=_database(project)
        out['checks']={'owned_service_restarted':first['pid']!=second['pid'],'all_historical_and_new_rows_preserved':before['rows']==after['rows'],'all_result_files_preserved':all(sha(project/name)==digest for name,digest in files.items()),'database_integrity_ok':before['integrity_ok'] and after['integrity_ok'],'database_artifact_relationships':not before['missing_artifacts'] and not after['missing_artifacts']}
        out.update(url=second['url'],result_files=len(files),database_rows=len(after['rows']))
    except (OSError,ValueError,RuntimeError,KeyError) as error:out['failures'].append(type(error).__name__+': '+str(error)[:600])
    out['status']='PASSED' if out['checks'] and all(out['checks'].values()) and not out['failures'] else 'FAILED'
    target=project/'_relay/verification'/('restart-persistence-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:6]+'.json');out['receipt_path']=str(target);write(target,out);return out

def _database(project):
    path=Path(project)/'private/laboratory.sqlite3'
    with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as connection:
        connection.row_factory=sqlite3.Row;check=connection.execute('pragma integrity_check').fetchall();rows=[dict(row) for row in connection.execute('select * from jobs order by id')]
    missing=[]
    for row in rows:
        if row['status']!='succeeded':continue
        result=load(Path(project)/'results'/row['id']/'result.json')
        if not result:missing.append({'id':row['id'],'artifact':'result.json'});continue
        for name in result.get('artifacts',[]):
            if Path(name).name!=name or not (Path(project)/'results'/row['id']/name).is_file():missing.append({'id':row['id'],'artifact':name})
    return {'integrity_ok':all(row[0]=='ok' for row in check),'rows':rows,'missing_artifacts':missing}

def acceptance(project_path,receipt_path=None):
    project,config=_config(project_path);receipt=load(receipt_path) if receipt_path else {}
    if receipt:
        config['capsule_id']=receipt.get('capsule_id',config.get('capsule_id'));config['capsule_sha256']=receipt.get('archive_sha256') or receipt.get('capsule_sha256') or receipt.get('sha256') or config.get('capsule_sha256');write(project/'_relay/ADAPTATION.json',config)
    verification=project/'_relay/verification';verification.mkdir(exist_ok=True);stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:6]
    out={'schema_version':1,'started_at':now(),'scope':'LOCAL_ROUNDTRIP_ONLY' if config['route']=='LOCAL_LINUX' else config['route'],'route':config['route'],'project_path':str(project),'source_capsule_id':config.get('capsule_id'),'source_capsule_sha256':config.get('capsule_sha256'),'destination':{'system':platform.system(),'machine':platform.machine(),'interpreter':config['interpreter']},'passed':{},'failed':{},'skipped':{},'new_run_ids':[],'historical_source_receipts_unchanged':True}
    before=_database(project);before_rows={row['id']:row for row in before['rows']};out['history_before']={'rows':len(before_rows),'integrity_ok':before['integrity_ok'],'missing_artifacts':before['missing_artifacts']}
    def check(name,fn):
        try:out['passed'][name]=fn() or True
        except Exception as error:out['failed'][name]=type(error).__name__+': '+str(error)[:700]
    def initial():
        service=start(project);catalogue=_request(project,'/api/catalogue');assert isinstance(catalogue.get('experiments'),list) and not catalogue.get('active');return {'url':service['url'],'authenticated_http':True,'experiments':len(catalogue['experiments'])}
    check('destination_service_start',initial)
    if 'destination_service_start' in out['passed']:
        if not before['integrity_ok'] or before['missing_artifacts']:out['failed']['source_database_artifact_consistency']='Captured source database or artifact relationships are inconsistent'
        else:out['passed']['source_database_artifact_consistency']={'source_rows':len(before_rows),'missing_artifacts':0}
        def experiment(identifier,inputs):
            catalogue=_request(project,'/api/catalogue');job=_request(project,'/api/run',{'experiment':identifier,'inputs':inputs},catalogue['csrf']);run_id=job['id'];out['new_run_ids'].append(run_id);deadline=time.monotonic()+150
            while time.monotonic()<deadline:
                result=_request(project,'/api/jobs/'+run_id)
                if result['status']!='running':break
                time.sleep(.5)
            assert result['status']=='succeeded',result.get('message','experiment did not finish')
            computed=result['result'];assert computed['checks'] and all(computed['checks'].values()),computed['checks'];folder=project/'results'/run_id;assert (folder/'report.md').is_file() and (folder/'report.html').is_file();assert computed.get('execution_context',{}).get('relay',{}).get('route')==config['route'];return computed
        def matrix():
            result=experiment('A',{'a':[[1,2],[3,4]],'b':[[5,6],[7,8]]});values=result['values'];answer=values.get('product') or values.get('numpy_product');assert answer==[[19,22],[43,50]],values;return {'run_id':result['id'],'expected_product':[[19,22],[43,50]],'checks':result['checks'],'versions':result['versions']}
        check('matrix_multiplication',matrix)
        def symbolic():
            result=experiment('B',{'expression':'x**3','point':2});assert result['values']['derivative']=='3*x**2';assert abs(result['values']['symbolic_derivative_value']-12)<1e-12;return {'run_id':result['id'],'derivative':'3*x**2','tolerance':{'symbolic_value_absolute':1e-12,'finite_difference_relative':1e-5},'checks':result['checks']}
        check('symbolic_differentiation',symbolic)
        if shutil.which('obabel'):
            def molecule():
                result=experiment('E',{'smiles':'CCO'});folder=project/'results'/result['id'];assert (folder/'structure.png').stat().st_size>100 and '<svg' in (folder/'structure.svg').read_text();assert result['values']['formula']=='C2H6O';return {'run_id':result['id'],'benign_smiles':'CCO','formula':'C2H6O','checks':result['checks'],'classification':'Structure-derived descriptor computation, not an experimental measurement.'}
            check('molecule_descriptors_and_rendering',molecule)
        else:out['skipped']['molecule_descriptors_and_rendering']='Open Babel executable missing; this E/G conversion workflow is not verified.'
        def plot():
            result=experiment('C',{'expression':'sin(x)','lower':0,'upper':3.141592653589793});assert abs(result['values']['integral']-2)<1e-8;folder=project/'results'/result['id'];assert (folder/'plot.png').is_file() and (folder/'plot.svg').is_file();return {'run_id':result['id'],'integral':result['values']['integral'],'absolute_tolerance':1e-8,'plot_and_reports_saved':True,'checks':result['checks']}
        check('plot_and_report',plot)
        def persistence():
            files={str(p.relative_to(project)):sha(p) for run_id in out['new_run_ids'] for p in (project/'results'/run_id).iterdir() if p.is_file()};old_pid=load(project/'_relay/service.json')['pid'];stop(project);service=start(project);assert service['pid']!=old_pid;after=_database(project);new_rows={row['id']:row for row in after['rows']};assert all(new_rows.get(key)==value for key,value in before_rows.items());assert all(sha(project/name)==digest for name,digest in files.items());assert not after['missing_artifacts'];assert after['integrity_ok'];assert all(new_rows[run_id]['status']=='succeeded' for run_id in out['new_run_ids']);return {'owned_service_restarted':True,'old_source_rows_preserved':len(before_rows),'new_runs_preserved':len(out['new_run_ids']),'result_files_preserved':len(files),'database_integrity_ok':True,'missing_artifacts':0,'url':service['url']}
        check('restart_and_persistence',persistence)
    out['finished_at']=now();out['status']='ACCEPTANCE_PASSED' if not out['failed'] and not out['skipped'] else 'FAILED' if out['failed'] else 'PARTIAL';out['ready_to_continue']=out['status']=='ACCEPTANCE_PASSED';out['receipt_path']=str(verification/('acceptance-'+stamp+'.json'));write(out['receipt_path'],out);write(project/'_relay/ACCEPTANCE-LATEST.json',out)
    (project/'_relay/DESTINATION-HANDOFF.md').write_text('# Receiving laboratory handoff\n\nScope: '+out['scope']+'\n\nResult: '+out['status']+'\n\nActual interpreter: `'+config['interpreter']+'`\n\nOwned laboratory URL: '+config['url']+'\n\nRead _relay/ACCEPTANCE-LATEST.json for fresh experiment IDs, versions, tolerances and persistence evidence. Source historical reports remain source evidence. Next small mission: execute one matrix experiment through the authenticated local API, preserve its result/provenance and write a new handoff; do not modify immutable source evidence or global Codex configuration. Windows native/WSL/fresh Windows Codex remain unverified unless separately executed.\n',encoding='utf-8')
    return out
