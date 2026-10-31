#!/usr/bin/env python3
"""Verify the actual Relay wheel/sdist in disposable environments.

Uses an existing packaging Python. No AI calls, scientific recomputation,
production-service controls, publication or global dependency installation.
"""
from __future__ import annotations
import argparse,datetime,hashlib,json,os,re,shutil,stat,subprocess,sys,tarfile,tempfile,zipfile
from pathlib import Path,PurePosixPath

DENIED_PARTS={'private','evidence','capsules','.venv','.relay-venv','__pycache__'}
DENIED_NAMES={'engine.py','worker.py','server.py','catalogue.py','laboratory.sqlite3','access.json','auth.json','sessions.json','jupyter-secret.json'}
SECRET_PATTERNS=[re.compile(pattern) for pattern in [rb'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',rb'\bgh[pousr]_[A-Za-z0-9]{25,}',rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{30,}',rb'\bAKIA[0-9A-Z]{16}\b']]

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()

def known_values(roots):
    values=set()
    for root in roots:
        root=Path(root)
        for relative in ['private/access.json','private/control/access.json','private/jupyter-secret.json','private/mobile-panel.json']:
            path=root/relative
            try:data=json.loads(path.read_text(encoding='utf-8'))
            except (OSError,ValueError):continue
            for key in ['password','token','secret','csrf','salt','hash']:
                value=data.get(key)
                if isinstance(value,str) and len(value)>=8:values.add(value.encode())
    return values

def inspect_member(name,raw,values):
    path=PurePosixPath(name)
    if name.startswith(('/','\\')) or '\\' in name or '..' in path.parts:raise AssertionError('Unsafe software archive member path')
    if any(part in DENIED_PARTS for part in path.parts) or path.name in DENIED_NAMES:raise AssertionError('Operational/private/project-data member in software distribution: '+name)
    if any(value in raw for value in values) or any(pattern.search(raw) for pattern in SECRET_PATTERNS):raise AssertionError('Credential pattern or known active value found; contents suppressed: '+name)

def runtime_payload(wheel):
    with zipfile.ZipFile(wheel) as archive:return {name:archive.read(name) for name in archive.namelist() if name.startswith('genesis_relay/') and not name.endswith('/')}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--wheel');parser.add_argument('--sdist');parser.add_argument('--output',default='evidence/package-tests.json');parser.add_argument('--secret-root',action='append',default=[]);args=parser.parse_args(argv)
    base=Path(__file__).resolve().parents[1];wheel=Path(args.wheel).resolve() if args.wheel else base/'dist/genesis_relay-0.1.0-py3-none-any.whl';sdist=Path(args.sdist).resolve() if args.sdist else base/'dist/genesis_relay-0.1.0.tar.gz';output=Path(args.output);output=output if output.is_absolute() else base/output
    result={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Actual wheel clean-venv install/generic private capsule/local receiver/uninstall and final sdist rebuild; no scientific reruns or native Windows claims.','packaging_python':sys.version.split()[0],'passed':{},'failed':{},'artifacts':{},'privacy':{}}
    values=known_values(args.secret_root)
    def check(name,fn):
        try:result['passed'][name]=fn() or True;print('PASS',name,flush=True)
        except Exception as error:result['failed'][name]=type(error).__name__+': '+str(error)[-1200:];print('FAIL',name,result['failed'][name],flush=True)
    def audit():
        count=0
        with zipfile.ZipFile(wheel) as archive:
            names=archive.namelist();assert len(names)==len(set(names))
            for member in archive.infolist():
                if member.is_dir():continue
                assert member.file_size<=16*1024*1024;assert not stat.S_ISLNK(member.external_attr>>16);inspect_member(member.filename,archive.read(member),values);count+=1
        with tarfile.open(sdist) as archive:
            names=archive.getnames();assert len(names)==len(set(names))
            for member in archive:
                assert not member.issym() and not member.islnk()
                if member.isfile():
                    assert member.size<=16*1024*1024;inspect_member(member.name,archive.extractfile(member).read(),values);count+=1
        result['privacy']={'status':'PASSED','software_members_checked':count,'known_active_values_compared_in_memory':len(values),'sensitive_values_or_hashes_recorded':False,'limitations':'Explicit member/path/pattern/known-value checks; not a proof against every possible unknown secret.'};return {'members_checked':count,'operational_data_absent':True,'known_secret_matches':0}
    check('software_distribution_privacy',audit)
    payload=runtime_payload(wheel)
    def source_identity():
        source={str(p.relative_to(base/'src')):p.read_bytes() for p in (base/'src/genesis_relay').rglob('*') if p.is_file() and '__pycache__' not in p.parts and not p.name.endswith('.pyc')}
        assert payload==source,'Built wheel runtime payload differs from current source; rebuild before delivery'
        assert len(payload)>=19,len(payload)
        assert all('genesis_relay/web/'+name in payload for name in ['index.html','app.js','style.css'])
        assert all('genesis_relay/windows/'+name in payload for name in ['Receive-Relay.ps1','Install-Relay.ps1'])
        return {'runtime_files_byte_equal':len(payload),'web_assets_present':True,'powershell_receiver_and_bootstrap_present':True}
    check('wheel_runtime_and_asset_identity',source_identity)
    env=os.environ.copy()
    for key in ['PYTHONPATH','PYTHONHOME','GENESIS_RELAY_HOME']:env.pop(key,None)
    env.update(PIP_DISABLE_PIP_VERSION_CHECK='1',PYTHONNOUSERSITE='1')
    with tempfile.TemporaryDirectory(prefix='relay-package-') as temporary:
        root=Path(temporary);env['GENESIS_RELAY_HOME']=str(root/'state')
        def run(argv,cwd=None,expected=0,timeout=120):
            proc=subprocess.run([str(arg) for arg in argv],cwd=cwd or root,env=env,capture_output=True,text=True,timeout=timeout)
            if proc.returncode!=expected:raise AssertionError('Command exit '+str(proc.returncode)+': '+(proc.stderr+proc.stdout)[-1400:])
            return proc
        venv=root/'venv';run([sys.executable,'-m','venv',venv]);bin_dir=venv/('Scripts' if os.name=='nt' else 'bin');python=bin_dir/('python.exe' if os.name=='nt' else 'python');cli=bin_dir/('relay.exe' if os.name=='nt' else 'relay');receive=bin_dir/('relay-receive.exe' if os.name=='nt' else 'relay-receive');state=root/'state';fixture=root/'Synthetic project';capsule_path=root/'synthetic-capsule.zip';destination=root/'receiving';fixture.mkdir();(fixture/'README.md').write_text('# Synthetic continuation project\nPackage acceptance fixture only.\n');(fixture/'.hidden-intent').write_text('Keep hidden source text.\n');(fixture/'ideas').mkdir();(fixture/'ideas/α idea.txt').write_text('Unicode synthetic idea; preserve bytes.\n',encoding='utf-8')
        def install():
            run([python,'-m','pip','install','--no-index','--no-deps',wheel]);proc=run([python,'-c','import genesis_relay; print(genesis_relay.__file__)']);assert str(venv) in proc.stdout and 'site-packages' in proc.stdout;run([cli,'--version']);run([cli,'--help']);return {'isolated_venv_import':True,'version_and_help':True,'no_runtime_dependencies_installed':True}
        check('clean_wheel_install_and_start',install)
        def export():
            run([cli,'--state-dir',state,'export',fixture,'--output',capsule_path,'--no-quiesce']);assert capsule_path.is_file();assert Path(str(capsule_path)+'.sha256').is_file();verified=json.loads(run([cli,'verify',capsule_path,'--summary']).stdout);assert verified['verified'];assert verified['completeness']['mode']=='full';return {'real_generic_capsule_exported_and_verified':True,'source_fixture_only':True,'capsule_bytes':capsule_path.stat().st_size}
        check('installed_cli_export_and_verify',export)
        receipt_path=None
        def restored():
            nonlocal receipt_path
            plan=json.loads(run([receive,'Plan','--capsule',capsule_path,'--destination-root',destination,'--route',('NATIVE_WINDOWS_X64' if os.name=='nt' else 'LOCAL_LINUX'),'--python',python]).stdout);assert plan['state']=='RESTORATION_PLANNED';assert not plan['blocked_prerequisites'];assert not Path(plan['project_path']).exists()
            receipt=json.loads(run([receive,'Restore','--capsule',capsule_path,'--destination-root',destination,'--route',('NATIVE_WINDOWS_X64' if os.name=='nt' else 'LOCAL_LINUX'),'--python',python,'--apply']).stdout);receipt_path=Path(receipt['receipt_path']);project=Path(receipt['project_path']);assert (project/'.hidden-intent').read_bytes()==(fixture/'.hidden-intent').read_bytes();assert (project/'ideas/α idea.txt').read_bytes()==(fixture/'ideas/α idea.txt').read_bytes();assert (project/'_relay/knowledge/START-HERE.md').is_file();verified=json.loads(run([receive,'Verify','--receipt',receipt_path]).stdout);assert verified['status']=='PASSED',verified;assert receipt['state']=='RESTORED';return {'plan_without_execution':True,'fresh_workspace_restored':True,'hidden_unicode_bytes_preserved':True,'knowledge_present':True,'receiver_integrity_verified':True,'scientific_acceptance_not_claimed':True}
        check('installed_receiver_plan_restore_verify',restored)
        def uninstall():
            assert receipt_path and receipt_path.is_file();state_hash=digest(state/'registry.json');receipt_hash=digest(receipt_path);run([python,'-m','pip','uninstall','-y','genesis-relay']);assert not cli.exists() and not receive.exists();assert digest(state/'registry.json')==state_hash and digest(receipt_path)==receipt_hash;return {'console_scripts_removed':True,'sender_state_and_receiver_receipts_retained':True}
        check('package_uninstall_preserves_project_state',uninstall)
        def rebuild():
            extracted=root/'source';extracted.mkdir()
            with tarfile.open(sdist) as archive:
                for member in archive:
                    path=PurePosixPath(member.name);assert not path.is_absolute() and '..' not in path.parts and not member.issym() and not member.islnk()
                archive.extractall(extracted,**({'filter':'data'} if hasattr(tarfile,'data_filter') else {}))
            project=next(extracted.iterdir());out=root/'rebuilt';run([sys.executable,'-m','build','--wheel','--no-isolation','--outdir',out],cwd=project,timeout=180);rebuilt=next(out.glob('*.whl'));assert runtime_payload(rebuilt)==payload
            # Installation was already proved for the byte-identical runtime files.
            return {'safe_source_archive_extraction':True,'build_without_global_install':True,'runtime_payload_matches_verified_wheel':True,'runtime_files':len(payload),'whole_archive_bit_reproducibility_claimed':False}
        check('final_sdist_rebuild_payload_identity',rebuild)
    result['artifacts']={path.name:{'bytes':path.stat().st_size,'sha256':digest(path)} for path in [wheel,sdist]};result['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();result['status']='PASSED' if not result['failed'] else 'FAILED';output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():output.rename(output.with_name(output.stem+'-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%f')+output.suffix))
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print(json.dumps({'status':result['status'],'passed':len(result['passed']),'failed':len(result['failed'])}),flush=True);return bool(result['failed'])

if __name__=='__main__':raise SystemExit(main())
