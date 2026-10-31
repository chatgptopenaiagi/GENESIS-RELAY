"""Trusted, portable synthetic laboratory and actual continuation demonstration.

This is a known synthetic profile, not an arbitrary capsule-code executor.
"""
from __future__ import annotations
import argparse,contextlib,csv,hashlib,json,os,platform,shutil,sqlite3,sys,tempfile,uuid
from pathlib import Path
from . import capsule,receiver,returns,state
from .common import atomic,load,now,sha,lock

RESOURCE=Path(__file__).with_name('demo_project')
DEMO_FORMAT='genesis-relay-synthetic-demo'
NOTE='DEMO-RETURN-NOTE.md'

def is_demo(project):
    value=load(Path(project)/'DEMO-PROJECT.json',{})
    return value.get('format')==DEMO_FORMAT and value.get('version')==1

def create(root):
    """Materialize a new known example. Never overwrite an existing project."""
    root=Path(root).expanduser().absolute()
    if root.exists():
        if not root.is_dir() or root.is_symlink() or not is_demo(root):raise ValueError('Demo target exists without owned synthetic project identity; nothing overwritten')
        return {'source_root':str(root),'project_name':root.name,'synthetic':True,'created':False}
    root.parent.mkdir(parents=True,exist_ok=True)
    staging=root.with_name(root.name+'.demo-partial')
    if staging.exists():raise ValueError('Existing partial demo requires inspection before retry')
    staging.mkdir(mode=0o700)
    for p in RESOURCE.iterdir():
        if p.is_file() and not p.name.endswith('.pyc'):(staging/p.name).write_bytes(p.read_bytes())
    (staging/'data').mkdir();(staging/'data/observations.csv').write_text('id,value\nsample-a,2\nsample-b,4\nsample-c,6\n',encoding='utf-8',newline='')
    (staging/'private').mkdir();(staging/'results/source-run').mkdir(parents=True)
    report={'id':'source-run','classification':'SYNTHETIC_SOURCE_RESULT','data':'INVENTED_ONLY','observations':3,'mean':4.0,'expected_mean':4.0,'absolute_tolerance':1e-12,'passed':True,'artifact':'results/source-run/report.json'}
    atomic(staging/'results/source-run/report.json',report);atomic(staging/'results/source-run/report.md','# Synthetic source result\n\n(2 + 4 + 6) / 3 = 4. This is historical source evidence, not destination acceptance.\n')
    with sqlite3.connect(staging/'private/observations.sqlite3') as db:
        db.execute('create table observations(id text primary key,value real not null)');db.executemany('insert into observations values (?,?)',[('sample-a',2),('sample-b',4),('sample-c',6)])
        db.execute('create table runs(id text primary key,result_path text not null,mean real not null,stage text not null)');db.execute('insert into runs values (?,?,?,?)',('source-run','results/source-run/report.json',4.0,'SOURCE_HISTORICAL'))
    os.replace(staging,root)
    return {'source_root':str(root),'project_name':root.name,'synthetic':True,'created':True,'dependencies':'Python standard library only','expected_mean':4.0}

def prepare(state_dir=None):
    return create(state.state_dir(state_dir)/'demo/source')

def export_demo(root=None,state_dir=None,output=None):
    project=Path(root) if root is not None else Path(prepare(state_dir)['source_root'])
    if not is_demo(project):raise ValueError('Select the synthetic demo root, not an arbitrary project')
    _validate_profile(project)
    return capsule.export(project,output,state_dir=state_dir,quiesce=False)

def restoration_route():
    if os.name=='nt' and platform.machine().lower() in ['amd64','x86_64']:return 'NATIVE_WINDOWS_X64'
    if platform.system()=='Linux':return 'LOCAL_LINUX'
    raise ValueError('This demo restoration is qualified for actual Linux or Windows x64 only')

def restore_demo(capsule_path,destination,route=None):
    rec=receiver.restore(capsule_path,destination,route or restoration_route())
    if not is_demo(rec['project_path']):raise ValueError('Restored project is not the known synthetic demonstration; use generic Inspect/Plan instead')
    project=Path(rec['project_path'])
    text='# Destination synthetic demo continuation\n\nRead START-HERE.md and _relay/knowledge/PROJECT-PURPOSE.md. Source evidence is historical. This project has invented observations only and uses the Python standard library.\n\nActual route: '+rec['route']+'\nReceiver runtime: '+sys.executable+'\nCapsule SHA-256: '+rec['archive_sha256']+'\n\nRun the explicitly trusted `relay demo accept RECEIPT` to check arithmetic and database/report relationships. With an existing Python 3.10+, run `python experiment.py --project .` independently. A frozen Relay executable is not an external Python interpreter for arbitrary projects. Then write DESTINATION-NOTE.md with actual results and one next task.\n'
    handoff=project/'_relay/DESTINATION-HANDOFF.md'
    if not handoff.exists():atomic(handoff,text)
    guidance=project/'AGENTS.md';current=guidance.read_text(encoding='utf-8')
    if 'DEMO_DESTINATION_GUIDANCE' not in current:atomic(guidance,'<!-- DEMO_DESTINATION_GUIDANCE -->\nRead `_relay/DESTINATION-HANDOFF.md` first. Preserve original evidence and existing global instructions. This is the known synthetic demo, not the private scientific laboratory.\n\n'+current)
    # First trusted demo guidance is adaptation, not later engineering work.
    if not rec.get('duplicate_receipt'):receiver.record_adaptation(rec,{'profile':DEMO_FORMAT,'guidance':'Destination-specific synthetic-demo guidance; original source guidance inert'})
    return receiver.read(rec['receipt_path'])

def _validate_profile(project):
    project=Path(project)
    if not is_demo(project):raise ValueError('Not the known synthetic demonstration')
    for name in ['experiment.py','DEMO-PROJECT.json']:
        p=project/name
        if p.is_symlink() or not p.is_file() or p.read_bytes()!=(RESOURCE/name).read_bytes():raise ValueError('Demo executable/descriptor differs from the trusted bundled profile: '+name)
    return project

def _compute(project):
    with (project/'data/observations.csv').open(newline='',encoding='utf-8') as stream:rows=list(csv.DictReader(stream))
    expected=[('sample-a',2.0),('sample-b',4.0),('sample-c',6.0)];observed=[(r['id'],float(r['value'])) for r in rows]
    if observed!=expected:raise ValueError('Synthetic observation IDs or values differ from declared fixture')
    values=[x[1] for x in observed];answer=sum(values)/len(values)
    if abs(answer-4.0)>1e-12:raise ValueError('Mean differs from independent expected value 4')
    return {'observations':len(values),'mean':answer,'expected_mean':4.0,'absolute_tolerance':1e-12}

def _database(project):
    path=project/'private/observations.sqlite3'
    with sqlite3.connect(path) as db:
        if db.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('Database integrity failure')
        observations=db.execute('select id,value from observations order by id').fetchall()
        if observations!=[('sample-a',2.0),('sample-b',4.0),('sample-c',6.0)]:raise ValueError('Stable observation rows differ')
        runs=db.execute('select id,result_path,mean,stage from runs order by id').fetchall()
    if not any(row[0]=='source-run' and row[2]==4.0 and row[3]=='SOURCE_HISTORICAL' for row in runs):raise ValueError('Original source run is missing')
    for ident,path,mean,stage in runs:
        receiver._parts(path);target=receiver._within(project,project.joinpath(*path.split('/')))
        if target.is_symlink() or not target.is_file():raise ValueError('Run references a missing or unsafe artifact')
        report=load(target,{})
        if report.get('id')!=ident or report.get('mean')!=mean:raise ValueError('Database/report relationship differs')
    return {'integrity':'ok','observations':len(observations),'runs':len(runs),'artifact_references':len(runs),'source_run_preserved':True}

def accept_demo(receipt):
    rec=receiver.read(receipt) if isinstance(receipt,(str,Path)) else dict(receipt)
    with lock(Path(rec['project_path'])/'_relay/demo-accept.lock'):
        return _accept_demo(rec)

def _accept_demo(rec):
    project=Path(rec['project_path'])
    folder=project/'_relay/verification';folder.mkdir(parents=True,exist_ok=True)
    out={'schema_version':1,'started_at':now(),'route':rec['route'],'scope':'SYNTHETIC_DEMO_ONLY','project_path':str(project),'source_capsule_id':rec['capsule_id'],'source_capsule_sha256':rec['archive_sha256'],'destination':{'system':platform.system(),'machine':platform.machine(),'executable':sys.executable,'python_version':platform.python_version(),'runtime_inclusive':bool(getattr(sys,'frozen',False))},'passed':{},'failed':{},'skipped':{},'new_run_id':None}
    def check(name,fn):
        try:out['passed'][name]=fn() or True
        except Exception as error:out['failed'][name]=type(error).__name__+': '+str(error)[:500]
    check('immutable_capsule_and_restoration',lambda: receiver.verify_restoration(rec)['status']=='PASSED' or (_ for _ in ()).throw(ValueError('Restoration integrity failed')))
    check('trusted_demo_source_bytes',lambda:(_validate_profile(project) and {'experiment_sha256':sha(project/'experiment.py'),'known_source_bytes':True}))
    check('independent_mean',lambda:_compute(project))
    check('historical_database_and_artifacts',lambda:_database(project))
    if not out['failed']:
        ident='destination-'+uuid.uuid4().hex[:12];out['new_run_id']=ident;target=project/'results'/ident;target.mkdir()
        result={'id':ident,**_compute(project),'classification':'DESTINATION_OBSERVED_RESULT','source_capsule_id':rec['capsule_id'],'source_capsule_sha256':rec['archive_sha256'],'route':rec['route'],'destination':out['destination'],'recorded_at':now()};atomic(target/'report.json',result);atomic(target/'report.md','# Destination synthetic mean\n\nMean 4, absolute tolerance 1e-12. Runtime and capsule identity are in report.json.\n')
        with sqlite3.connect(project/'private/observations.sqlite3') as db:db.execute('insert into runs values (?,?,?,?)',(ident,'results/'+ident+'/report.json',4.0,'DESTINATION_OBSERVED'))
        check('new_destination_run_and_relationships',lambda:_database(project))
    out.update(status='ACCEPTANCE_PASSED' if not out['failed'] and not out['skipped'] else 'FAILED',finished_at=now(),receipt_path=str(folder/('demo-acceptance-'+uuid.uuid4().hex[:12]+'.json')))
    atomic(out['receipt_path'],out);sealed=receiver.record_acceptance(rec,out)
    atomic(project/'_relay/ACCEPTANCE-LATEST.json',out)
    atomic(project/'_relay/DESTINATION-HANDOFF.md','# Synthetic demo destination handoff\n\nStatus: '+out['status']+'\nActual route: '+rec['route']+'\nActual runtime: '+sys.executable+'\nCapsule SHA-256: '+rec['archive_sha256']+'\nSaved acceptance: '+str(Path(out['receipt_path']).relative_to(project))+'\n\nRead README.md and experiment.py. A fresh engineer should identify the existing interpreter, run the standalone mean experiment and write DESTINATION-NOTE.md with its actual result. All observations are invented. Do not infer full private-laboratory or workstation acceptance. Database snapshots are never automatically merged.\n')
    return {'acceptance':out,'receiver_state':sealed['state'],'ready_to_continue':sealed.get('ready_to_continue',False),'receipt_path':rec['receipt_path']}

def change_and_return(receipt,output):
    rec=receiver.read(receipt) if isinstance(receipt,(str,Path)) else dict(receipt);project=_validate_profile(rec['project_path']);note=project/NOTE
    if note.exists() and note.read_text(encoding='utf-8')!=note_text():raise ValueError('Existing independent return note preserved; choose generic Return instead')
    atomic(note,note_text());return returns.create_return(rec,output)

def note_text():return '# Synthetic receiving engineer letter\n\nThe invented mean experiment was reconstructed here. The selected note demonstrates a bounded return; actual runtime and numerical acceptance are recorded separately in destination receipts.\n'

def reconcile_demo(return_capsule,source_project):
    """Exercise real imported return against disposable copies, never source."""
    source_project=_validate_profile(source_project);source_before={str(p.relative_to(source_project)):sha(p) for p in source_project.rglob('*') if p.is_file()}
    with tempfile.TemporaryDirectory(prefix='relay-demo-reconcile-') as tmp:
        root=Path(tmp);clean=root/'clean';conflict=root/'conflict';shutil.copytree(source_project,clean);shutil.copytree(source_project,conflict)
        preview=returns.preview_return(return_capsule,clean);row=next((x for x in preview['entries'] if x['path']==NOTE),None)
        if not row or row['decision']!='APPLICABLE':raise ValueError('Returned demo note is not applicable to the independent source baseline')
        applied=returns.apply_return(preview,[NOTE]);assert (clean/NOTE).read_text(encoding='utf-8')==note_text();duplicate=returns.apply_return(preview,[NOTE]);assert duplicate['duplicate_import'];rolled=returns.rollback_return(applied['receipt_path']);assert rolled['state']=='ROLLED_BACK' and not (clean/NOTE).exists()
        atomic(conflict/NOTE,'Newer independent work must survive.\n');bad=returns.preview_return(return_capsule,conflict);badrow=next(x for x in bad['entries'] if x['path']==NOTE);assert badrow['decision']=='CONFLICT'
        try:returns.apply_return(bad,[NOTE])
        except ValueError:pass
        else:raise AssertionError('Conflicting newer edit was not refused')
        assert (conflict/NOTE).read_text()=='Newer independent work must survive.\n'
    assert source_before=={str(p.relative_to(source_project)):sha(p) for p in source_project.rglob('*') if p.is_file()}
    return {'status':'PASSED','scope':'ACTUAL_TRANSFERRED_SYNTHETIC_RETURN','return_sha256':sha(return_capsule),'selected_note_applied':True,'duplicate_import_noop':True,'rollback_restored_absence':True,'independent_conflict_refused':True,'source_project_unchanged':True,'database_policy':'Separate snapshot, manual reconciliation only'}

def main(argv=None,state_dir=None):
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='operation')
    for name in ['create','prepare']:
        q=s.add_parser(name);q.add_argument('--root')
    q=s.add_parser('export');q.add_argument('--root');q.add_argument('--output')
    q=s.add_parser('restore');q.add_argument('capsule');q.add_argument('--destination',required=True);q.add_argument('--route',choices=['LOCAL_LINUX','NATIVE_WINDOWS_X64','WSL_LINUX_X64'])
    q=s.add_parser('accept');q.add_argument('receipt')
    q=s.add_parser('return');q.add_argument('receipt');q.add_argument('--output',required=True)
    q=s.add_parser('reconcile');q.add_argument('return_capsule');q.add_argument('--project',required=True)
    a=p.parse_args(argv)
    if a.operation in [None,'create','prepare']:result=create(a.root) if getattr(a,'root',None) else prepare(state_dir)
    elif a.operation=='export':result=export_demo(a.root,state_dir,a.output)
    elif a.operation=='restore':result=restore_demo(a.capsule,a.destination,a.route)
    elif a.operation=='accept':result=accept_demo(a.receipt)
    elif a.operation=='return':result=change_and_return(a.receipt,a.output)
    else:result=reconcile_demo(a.return_capsule,a.project)
    print(json.dumps(result,indent=2,ensure_ascii=True));return 1 if result.get('status')=='FAILED' or 'acceptance' in result and result['acceptance']['status']!='ACCEPTANCE_PASSED' else 0
