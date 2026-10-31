"""Evidence-indexed engineering letters and project-scoped environment knowledge.

Reads only the selected project and explicitly selected Sentinel generation. It
never loads Codex conversations/authentication or presents source observations as
destination verification.
"""
from __future__ import annotations
import datetime, hashlib, json, os, re, shutil, subprocess, sys
from pathlib import Path

TYPES={'OPERATOR_REQUIREMENT','OBSERVED_RESULT','HISTORICAL_REPORT','ENGINEERING_INFERENCE','UNTESTED_PROPOSAL','UNKNOWN'}
REQUIRED_PYTHON=['numpy','scipy','sympy','mpmath','pandas','networkx','matplotlib','rdkit']
SOURCE_DOCS=['README.md','AGENTS.md','ARCHITECTURE.md','SESSION-HANDOFF.md','FINAL-REPORT.md','TEST-RESULTS.json','SCIENTIFIC-CAPABILITIES.json','EXPERIMENTS.md','INSTALLATION.md','MATHEMATICAL-ENGINES.md','CHEMISTRY-ENGINES.md','BENCHMARKS.json']

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read_json(path,default=None):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):return default

def fingerprint(path):
    p=Path(path);h=hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return {'path':str(p),'sha256':h.hexdigest(),'bytes':p.stat().st_size}

def _safe_url(value):
    from urllib.parse import urlsplit,urlunsplit
    if not isinstance(value,str):return value
    try:
        u=urlsplit(value)
        if u.scheme and u.netloc:
            host=u.hostname or '';host+=':'+str(u.port) if u.port else ''
            return urlunsplit((u.scheme,host,u.path,'',''))
    except ValueError:pass
    return value

def environment_metadata(interpreter):
    """Isolated metadata collection, not a scientific import/verification."""
    interpreter=Path(interpreter).absolute()
    if not interpreter.is_file():return {'status':'UNKNOWN','reason':'source interpreter missing','interpreter':str(interpreter)}
    code='''import sys,json,importlib.metadata as m,sysconfig,platform
rows=[]
for d in m.distributions():
 name=d.metadata.get('Name')
 if not name:continue
 direct=d.read_text('direct_url.json')
 rows.append({'name':name,'version':d.version,'location':str(d.locate_file('')),'metadata_location':str(d._path),'installer':d.read_text('INSTALLER'),'direct_url':json.loads(direct) if direct else None})
print(json.dumps({'python':sys.version,'executable':sys.executable,'prefix':sys.prefix,'base_prefix':sys.base_prefix,'platform':platform.platform(),'machine':platform.machine(),'packages':sorted(rows,key=lambda x:x['name'].lower()),'system_library':sysconfig.get_config_var('LIBDIR')}))'''
    env=os.environ.copy();env.update({k:'1' for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']});env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
    try:
        result=subprocess.run([str(interpreter),'-I','-c',code],capture_output=True,text=True,env=env,timeout=30)
        if result.returncode:return {'status':'UNKNOWN','interpreter':str(interpreter),'reason':'metadata probe failed','returncode':result.returncode}
        if len(result.stdout)>8_000_000:return {'status':'UNKNOWN','interpreter':str(interpreter),'reason':'metadata output exceeded finite limit'}
        data=json.loads(result.stdout);data.update(status='OBSERVED_SOURCE_METADATA',interpreter=str(interpreter),observed_at=now())
        for row in data['packages']:
            if isinstance(row.get('direct_url'),dict) and 'url' in row['direct_url']:row['direct_url']['url']=_safe_url(row['direct_url']['url'])
        data['conda']={'applicable':False,'status':'NOT_APPLICABLE','records':[],'requested_dependency_export':None}
        for prefix in dict.fromkeys([data.get('prefix'),data.get('base_prefix')]):
            if not prefix or not (Path(prefix)/'conda-meta').is_dir():continue
            records=[]
            for path in sorted((Path(prefix)/'conda-meta').glob('*.json')):
                record=read_json(path,{})
                if isinstance(record,dict) and record.get('name'):records.append({key:_safe_url(record.get(key)) for key in ['name','version','build','subdir','channel','url']})
            data['conda']={'applicable':True,'status':'SOURCE_METADATA_ONLY','prefix':prefix,'records':records,'requested_dependency_export':None}
            command=next((str(p) for p in [Path(prefix)/'bin/conda',Path(prefix).parent.parent/'bin/conda'] if p.is_file()),shutil.which('conda'))
            if command:
                conda_env=env.copy();conda_env['CONDA_OFFLINE']='true'
                try:
                    exported=subprocess.run([command,'env','export','--from-history','--prefix',prefix],capture_output=True,text=True,env=conda_env,timeout=30)
                    if exported.returncode==0 and len(exported.stdout)<1_000_000:
                        text='\n'.join(line for line in exported.stdout.splitlines() if not line.startswith('prefix:'))+'\n'
                        text=re.sub(r'https?://[^\s\"\']+',lambda match:_safe_url(match.group(0)),text)
                        data['conda']['requested_dependency_export']=text
                    else:data['conda']['export_status']='UNAVAILABLE: local requested-dependency export failed or exceeded limit'
                except (OSError,subprocess.TimeoutExpired):data['conda']['export_status']='UNAVAILABLE: bounded local export did not complete'
            else:data['conda']['export_status']='UNAVAILABLE: no existing Conda executable selected'
            break
        return data
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:return {'status':'UNKNOWN','interpreter':str(interpreter),'reason':type(error).__name__}

def sentinel_snapshot(source_root,sentinel_root=None):
    """Export only source-project environment/capabilities; absent Sentinel is valid."""
    source=Path(source_root).absolute()
    if sentinel_root is None:return {'available':False,'status':'UNKNOWN','reason':'No Sentinel source selected; Relay remains standalone.'}
    root=Path(sentinel_root)
    try:generation=(root/'current').resolve(strict=True)
    except OSError:generation=root
    envs=read_json(generation/'ENVIRONMENTS.json',{}) or {};graph=read_json(generation/'CAPABILITY-GRAPH.json',{}) or {};projects=read_json(generation/'PROJECT-MAP.json',{}) or {}
    chosen=[e for e in envs.get('environments',[]) if str(e.get('prefix',''))==str(source/'.venv') or e.get('interpreter')==str(source/'.venv/bin/python')]
    ids={e.get('id') for e in chosen};native={'octave-cli','obabel','gnuplot','sqlite3'}
    caps=[c for c in graph.get('capabilities',[]) if c.get('environment_id') in ids or c.get('name') in native]
    selected=[p for p in projects.get('projects',[]) if p.get('path')==str(source)]
    return {'available':bool(chosen or caps or selected),'classification':'HISTORICAL_REPORT','warning':'Source-machine Sentinel evidence. Never merge it into a destination inventory as a current observation.','source_generation':graph.get('generation',envs.get('generation')),'observed_at':graph.get('observed_at'),'environments':chosen,'capabilities':caps,'projects':selected}

def _generic_capture(source,sources,sentinel_root,operator_note):
    """Do not project the first Science Lab profile onto unrelated projects."""
    project_name=source.name;claims=[]
    def claim(kind,text,refs):
        ident='claim-'+hashlib.sha256((kind+text).encode()).hexdigest()[:12]
        claims.append({'id':ident,'classification':kind,'claim':text,'sources':[sources[r] if r in sources else {'type':'SUPPLIED_OPERATOR_NOTE','source':'Current Relay mission'} if r=='operator-note' else {'path':r,'status':'UNKNOWN'} for r in refs]});return ident
    observed=claim('OBSERVED_RESULT','The selected project root is named '+project_name+'. Relevant source documents are fingerprinted; no specialized functional acceptance profile has been selected.',list(sources))
    requirement=claim('OPERATOR_REQUIREMENT',operator_note or 'Preserve the selected project, documented intent and evidence; reconstruct into a new workspace and verify requirements before continuing.',['operator-note'])
    unknown=claim('UNKNOWN','Project-specific purpose, dependencies, architecture, decisions and current functional status are known only where original documentation/evidence supplies them. Relay does not infer that this is a scientific laboratory.',['project-specific acceptance profile'])
    readme=source/'README.md';excerpt=''
    if readme.is_file():
        excerpt=readme.read_text(encoding='utf-8',errors='replace')[:2400]
        report=claim('HISTORICAL_REPORT','The source README is delivered as historical project documentation; its statements are not destination acceptance.',['README.md'])
    else:report=unknown
    def doc(title,text,ids):return '# '+title+'\n\n'+text+'\n\nEvidence: '+', '.join(ids)+'. See EVIDENCE-INDEX.json.\n'
    docs={
        'START-HERE.md':doc('Continue '+project_name,'What you created: a project snapshot and its available documented story.\n\nWhat you can do: inspect files and evidence, review omissions/dependencies and restore to a new workspace.\n\nHow to open it: inspect the trusted receiver plan; no application startup command is inferred.\n\nWhat is unfinished: project-specific environment reconstruction, acceptance and receiving-session qualification remain unknown until new receipts exist.',[observed,requirement,unknown]),
        'PROJECT-PURPOSE.md':doc('Documented project purpose','The original README excerpt below is preserved as historical documentation.\n\n'+excerpt if excerpt else 'No README purpose statement was available. Project purpose remains UNKNOWN.',[report,unknown]),
        'HUMAN-INTENT.md':doc('Documented human intent',operator_note or 'The supplied Relay mission asks for project preservation and evidence-backed continuation. No additional private conversation or undocumented project intent is inferred.',[requirement,unknown]),
        'ARCHITECTURE.md':doc('Project architecture','Read the archived original ARCHITECTURE.md where present. Relay has not inferred a scientific, web or database architecture for this generic project.',[observed,unknown]),
        'DECISIONS.md':doc('Documented decisions','Original project records are preserved. No undocumented reason, model thought or rationale is invented.',[unknown]),
        'CURRENT-STATE.md':doc('Current source and destination state','Available documents and exact snapshot bytes are source evidence. Successful extraction is not environment reconstruction or functional acceptance. No project-specific acceptance results have been obtained by this generic profile.',[observed,unknown]),
        'KNOWN-PROBLEMS.md':doc('Known problems and unknown prerequisites','Review the completeness manifest, exclusions, original handoff and project reports. An empty discovered dependency list means requirements are unresolved, not that the project has no dependencies.',[unknown]),
        'NEXT-STEPS.md':doc('Next bounded continuation mission','1. Inspect capsule integrity and completeness.\n2. Identify the actual project purpose and startup/test command from delivered source.\n3. Discover compatible destination prerequisites.\n4. Restore into a new workspace and run one small declared acceptance test.\n5. Record actual results and a new handoff; keep source evidence unchanged.',[requirement,unknown]),
    }
    index={'schema_version':1,'captured_at':now(),'source_root':str(source),'profile':'GENERIC_PROJECT','claim_types':sorted(TYPES),'claims':claims,'source_files':sources,'missing_context':['No specialized project acceptance profile or selected conversation export is available.']};docs['EVIDENCE-INDEX.json']=json.dumps(index,indent=2)+'\n'
    return {'documents':docs,'evidence_index':index,'dependencies':[],'environment':environment_metadata(source/'.venv/bin/python'),'sentinel_evidence':sentinel_snapshot(source,sentinel_root),'recipes':{},'historical_summary':{'profile':'GENERIC_PROJECT','functional_status':'UNKNOWN','not_destination_verification':True},'catalogue':[]}

def capture(source_root,sentinel_root=None,operator_note=None):
    source=Path(source_root).absolute();records=[];sources={}
    for name in SOURCE_DOCS:
        path=source/name
        if path.is_file():sources[name]=fingerprint(path)
    if not all((source/name).is_file() for name in ['engine.py','worker.py','server.py','catalogue.py']):return _generic_capture(source,sources,sentinel_root,operator_note)
    def claim(kind,text,refs):
        if kind not in TYPES:raise ValueError('Unknown claim classification')
        ident='claim-'+hashlib.sha256((kind+text).encode()).hexdigest()[:12]
        records.append({'id':ident,'classification':kind,'claim':text,'sources':[sources[r] if r in sources else {'type':'SUPPLIED_OPERATOR_NOTE','source':'Current Relay mission','record':'HUMAN-INTENT.md'} if r=='supplied Relay operator mission' else {'path':r,'status':'UNKNOWN'} for r in refs]});return ident
    registry=read_json(source/'SCIENTIFIC-CAPABILITIES.json',{}) or {};tests=read_json(source/'TEST-RESULTS.json',{}) or {};engines=registry.get('engines',[])
    catalogue=[]
    path=source/'catalogue.py'
    if path.is_file():
        # AST literals only: capture must never import arbitrary project code.
        import ast
        try:
            tree=ast.parse(path.read_text())
            for node in tree.body:
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='EXPERIMENTS' for t in node.targets):catalogue=ast.literal_eval(node.value)
            sources['catalogue.py']=fingerprint(path)
        except (OSError,SyntaxError,ValueError,TypeError):pass
    environment=environment_metadata(source/'.venv/bin/python');sentinel=sentinel_snapshot(source,sentinel_root)
    versions={str(p['name']).lower().replace('_','-'):p['version'] for p in environment.get('packages',[])}
    # Registry-only package versions remain historical when dist-info is absent.
    for engine in engines:
        name=str(engine.get('name','')).lower();version=engine.get('version')
        if name in REQUIRED_PYTHON and version is not None:versions.setdefault(name,str(version))
    dependencies=[]
    for name in REQUIRED_PYTHON:
        dependencies.append({'id':'python:'+name,'name':name,'relationship':'required','source_location':next((p['location'] for p in environment.get('packages',[]) if p['name'].lower().replace('_','-')==name),None),'source_version':versions.get(name),'evidence':'environments/source-environment.json; source engine.py imports; SCIENTIFIC-CAPABILITIES.json','interface':'Python import '+name,'destination_requirements':'Install a compatible native destination build; source ARM64 site-packages are not executable dependencies on Windows/x64.','source_metadata_only':True})
    for package in environment.get('packages',[]):
        direct=package.get('direct_url') or {}
        if direct.get('dir_info',{}).get('editable'):
            dependencies.append({'id':'editable:'+package['name'],'name':package['name'],'relationship':'required' if package['name'].lower().replace('_','-') in REQUIRED_PYTHON else 'development-only','source_location':direct.get('url'),'source_version':package['version'],'evidence':'environments/source-environment.json direct_url metadata','interface':'Local editable Python source','destination_requirements':'The referenced local source is not disposable cache. Account for it explicitly; unresolved required external source blocks a complete reconstruction.','source_metadata_only':True})
    for name,interface,scope in [('openbabel','obabel command','Required for molecular conversion experiments E/G; other supported workflows do not require it.'),('octave','octave-cli command','Optional Octave bridge experiment.'),('gnuplot','gnuplot command','Optional alternate plot renderer.')]:
        entry=next((e for e in engines if name in str(e.get('name','')).lower()),{})
        dependencies.append({'id':'engine:'+name,'name':name,'relationship':'optional','source_location':entry.get('executable') or entry.get('path') or entry.get('module_path'),'source_version':entry.get('version'),'evidence':'SCIENTIFIC-CAPABILITIES.json; source engine.py','interface':interface,'destination_requirements':scope+' Discover a compatible destination executable; missing capability blocks that experiment only.','source_metadata_only':True})
    dependencies.extend([{'id':'runtime:python','name':'Python','relationship':'required','source_location':environment.get('interpreter'),'source_version':environment.get('python'),'evidence':'environments/source-environment.json','interface':'Python interpreter','destination_requirements':'Separate native destination environment. WSL uses Linux x86_64 packages; native Windows requires compatibility adaptation for fcntl/resource/process groups.','source_metadata_only':True},{'id':'service:sqlite','name':'SQLite run registry','relationship':'required','source_location':'private/laboratory.sqlite3','source_version':None,'evidence':'source server.py and database backup receipt','interface':'Python sqlite3 / jobs table keyed by stable run IDs','destination_requirements':'Use captured database-aware backup and verify job/artifact relationships; never text merge databases.','source_metadata_only':False},{'id':'service:sentinel','name':'Sentinel source knowledge','relationship':'historical','source_location':str(sentinel_root) if sentinel_root else None,'evidence':'knowledge/sentinel-source-evidence.json','interface':'Project-filtered source records','destination_requirements':'Optional. Discover destination state independently.','source_metadata_only':True},{'id':'service:joomla','name':'Joomla','relationship':'historical','source_location':None,'evidence':'ARCHITECTURE.md','interface':'Independent neighboring source-machine service','destination_requirements':'Not a laboratory dependency; no Joomla data, credentials or unrelated source are included.','source_metadata_only':True}])
    purpose=claim('HISTORICAL_REPORT','GENESIS Science Lab is a local human scientific workbench: editable experiments, mathematical/molecular calculations, figures, reports and saved provenance.',['README.md','EXPERIMENTS.md'])
    intent=claim('OPERATOR_REQUIREMENT',operator_note or 'Preserve and reconstruct this laboratory with its source, saved results, history, purpose and a visible human interface; preserve independent machines and credentials.',['supplied Relay operator mission'])
    history=claim('HISTORICAL_REPORT',f"The captured registry records {len(engines)} scientific engine entries and the literal catalogue defines {len(catalogue)} experiments. These are source observations, not fixed acceptance counts or destination health guarantees.",['SCIENTIFIC-CAPABILITIES.json','catalogue.py'])
    passes=len(tests.get('passed',{})) if isinstance(tests.get('passed'),(dict,list)) else tests.get('passed',0);fails=len(tests.get('failed',{})) if isinstance(tests.get('failed'),(dict,list)) else tests.get('failed',0)
    checks=claim('HISTORICAL_REPORT',f"Captured laboratory verification reports {passes} passing and {fails} failing checks; its original timestamps and scope remain source evidence.",['TEST-RESULTS.json'])
    design=claim('ENGINEERING_INFERENCE','The observed one-worker, bounded-subprocess, fixed experiment interface limits contention and preserves separate per-run provenance. This rationale is inferred from documented limits and implementation, not hidden model reasoning.',['ARCHITECTURE.md','README.md'])
    limits=claim('HISTORICAL_REPORT','Scientific descriptors are computed predictions, not experimental property measurements. Source reports do not verify GPU, physical touchscreen use, Android reboot survival or native Windows reconstruction.',['CHEMISTRY-ENGINES.md','MATHEMATICAL-ENGINES.md','SESSION-HANDOFF.md'])
    unknown=claim('UNKNOWN','Selected project-relevant conversation exports, unavailable operator conversations and undocumented reasons are not present in this capsule; no missing intent is invented.',['unavailable conversation export'])
    proposal=claim('UNTESTED_PROPOSAL','Native Windows and WSL are distinct restoration routes. Probe actual destination dependencies and run numerical acceptance before marking either route ready.',['Relay restoration plan'])
    def section(title,body,ids):return '# '+title+'\n\n'+body+'\n\nEvidence: '+', '.join(ids)+'. See EVIDENCE-INDEX.json.\n'
    docs={
        'START-HERE.md':section('Continue GENESIS Science Lab','What you created: a local mathematics and chemistry workbench with saved scientific runs and reports.\n\nWhat you can do: inspect historical evidence, reconstruct a compatible local environment, run supported experiments and add new verified work without rewriting source evidence.\n\nHow to open it: first inspect the capsule and restoration plan using the trusted Relay receiver. Restore into a new workspace, reconstruct dependencies, then use the destination-owned laboratory controls and URL recorded by acceptance. Source URL/launchers are archived history, not a destination command.\n\nWhat is unfinished: destination execution, native Windows/WSL qualification, missing engines and fresh receiving Codex continuation remain unverified until destination receipts exist. Read PROJECT-PURPOSE.md, ARCHITECTURE.md, CURRENT-STATE.md, KNOWN-PROBLEMS.md and NEXT-STEPS.md.',[purpose,intent,limits,proposal]),
        'PROJECT-PURPOSE.md':section('Project purpose','A visible local scientific laboratory connects bounded numerical/symbolic and molecular engines with editable human inputs, graphics, downloadable reports, stable run IDs and preserved provenance.',[purpose]),
        'HUMAN-INTENT.md':section('Documented human intent',operator_note or 'The operator asks for full continuation, a human interface and evidence-backed reconstruction. The receiver must work from delivered files and its own credentials, preserve the immutable source snapshot, distinguish historical reports from new observations and return improvements without overwriting newer work.',[intent,unknown]),
        'ARCHITECTURE.md':section('Captured laboratory architecture','Browser → authenticated local standard-library HTTP service → one bounded scientific worker → Python/CLI engines → per-run artifacts and SQLite job registry. Source guidance and original architecture remain archived intact. Destination adaptations are recorded separately. The capsule does not make neighboring Joomla or the phone Sentinel installation a required service.',[purpose,design,limits]),
        'DECISIONS.md':section('Observable decisions and tradeoffs','Established techniques observed in source: SQLite persistence, SHA-256 artifact checksums, fixed request schemas, AST-limited expressions, process isolation, local authentication and explicit numerical tolerances. Project-specific composition: one visible laboratory combining these mechanisms with per-run engine/source provenance. A reusable restoration adapter changes paths/launchers only in the working copy. No claim is made about private model thoughts or undocumented design motives.',[design,unknown]),
        'CURRENT-STATE.md':section('Source state and receiving state',f'The captured source catalogue has {len(catalogue)} experiment definitions and the registry has {len(engines)} engine records. Its verification report records {passes} passes and {fails} failures. Read their source timestamps, run IDs and limitations. Source results/receipts remain unchanged. The receiving machine has not inherited those verification outcomes; its restoration and acceptance receipts determine current readiness.',[history,checks,limits]),
        'KNOWN-PROBLEMS.md':section('Known problems and missing context','Native Windows needs focused handling of fcntl, resource limits, Unix paths, process-group cancellation and shell launchers. Compatible scientific engines must be installed/discovered independently. Open Babel is needed for E/G conversion paths; missing optional bridge engines must block those experiments, not all laboratory use. Captured credentials are excluded and must be generated locally. Complete physical phone/Windows acceptance and undocumented conversations are not inferred.',[limits,unknown,proposal]),
        'NEXT-STEPS.md':section('Next small mission','1. Inspect/verify the capsule without executing project code.\n2. Choose NATIVE_WINDOWS_X64 or WSL_LINUX_X64 from actual destination probes; LOCAL_LINUX is only a roundtrip demonstration.\n3. Restore to a new directory and create a compatible environment; keep source evidence immutable.\n4. Run one matrix experiment and compare [[19,22],[43,50]] exactly, then record destination interpreter, versions, source capsule digest and a new handoff.\n5. Complete symbolic, molecule/rendering, plot/report, history and restart checks before READY_TO_CONTINUE.\n6. Preview a return change against the adaptation baseline; inspect conflicts and never text-merge database files.',[intent,proposal]),
    }
    index={'schema_version':1,'captured_at':now(),'source_root':str(source),'claim_types':sorted(TYPES),'claims':records,'source_files':sources,'missing_context':['No selected project conversation export was provided.'],'scientific_results_warning':'Historical calculations/structure-derived descriptors are not experimental measurements.'}
    docs['EVIDENCE-INDEX.json']=json.dumps(index,indent=2)+'\n'
    recipes={'python-source-exact.txt':'# Exact source distribution metadata; not a cross-platform installation lock.\n'+''.join(p['name']+'=='+p['version']+'\n' for p in environment.get('packages',[])),'python-destination-requested.txt':'# Destination-native requested packages; versions must be resolved and verified locally.\n'+'\n'.join(REQUIRED_PYTHON)+'\n','environment-portable.yml':'# A proposal for an existing compatible Conda installation, not a source ARM binary export.\nname: genesis-science-relay\nchannels:\n  - conda-forge\ndependencies:\n  - python>=3.10\n'+''.join('  - '+name+'\n' for name in REQUIRED_PYTHON)}
    return {'documents':docs,'evidence_index':index,'dependencies':dependencies,'environment':environment,'sentinel_evidence':sentinel,'recipes':recipes,'historical_summary':{'engine_records':len(engines),'catalogue_experiments':len(catalogue),'reported_passes':passes,'reported_failures':fails,'source_report_time':tests.get('checked_at_utc'),'not_destination_verification':True},'catalogue':catalogue}
