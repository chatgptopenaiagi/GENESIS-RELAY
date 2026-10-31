"""Synthetic adapter/knowledge tests; real relocation is root integration evidence."""
import hashlib,json,os,shutil,socket,sqlite3,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from genesis_relay import knowledge,laboratory as lab

class LaboratoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='relay-lab-fixture-');self.root=Path(self.temp.name);self.project=self.root/'project';self.project.mkdir();(self.project/'_relay').mkdir()
        self.addCleanup(self.temp.cleanup)
    def fixture(self):
        if sys.platform!='linux' and self._testMethodName in {
            'test_adaptation_preserves_kernel_bytes_and_source','test_missing_dependency_blocks_without_verification',
            'test_destination_controls_cannot_reuse_source_port','test_unowned_environment_not_overwritten',
            'test_destination_registry_and_ui_do_not_inherit_source_verification'}:
            self.skipTest('Optional POSIX scientific-service adapter requires actual Linux; portable demo has independent native acceptance')
        from synthetic_science_fixture import create
        source=create(self.root/'synthetic-baseline')
        for name in ['server.py','worker.py','engine.py','catalogue.py']:(self.project/name).write_bytes((source/name).read_bytes())
        return source
    def fake_environment(self,command,**kwargs):
        target=Path(command[-1]);(target/'bin').mkdir(parents=True);(target/'bin/python').write_text('synthetic interpreter placeholder')
        import subprocess
        return subprocess.CompletedProcess(command,0,'','')
    def test_refuses_original_installation(self):
        with self.assertRaisesRegex(ValueError,'original source'):lab.project_root('/root/GENESIS-SCIENCE-LAB')
    def test_native_and_wsl_states_are_separate(self):
        self.fixture();result=lab.adapt_project(self.project,sys.executable,'NATIVE_WINDOWS_X64');self.assertEqual(result['status'],'BLOCKED');self.assertFalse((self.project/'_relay/ADAPTATION.json').exists())
        with patch.object(lab.platform,'release',return_value='ordinary Linux'),patch.dict(os.environ,{'WSL_INTEROP':''}):result=lab.adapt_project(self.project,sys.executable,'WSL_LINUX_X64')
        self.assertEqual(result['status'],'BLOCKED')
    def test_adaptation_preserves_kernel_bytes_and_source(self):
        original=self.fixture();before={name:lab.sha(self.project/name) for name in ['engine.py','worker.py','catalogue.py']};source_server=lab.sha(original/'server.py')
        with patch.object(lab.subprocess,'run',side_effect=self.fake_environment),patch.object(lab,'dependency_probe',return_value={'missing':[],'versions':{}}),patch.object(lab,'choose_port',return_value=8149):result=lab.adapt_project(self.project,sys.executable,capsule_id='synthetic')
        self.assertEqual(result['status'],'ADAPTED');self.assertEqual(before,result['kernel_hashes']);self.assertEqual(lab.sha(original/'server.py'),source_server);text=(self.project/'server.py').read_text();self.assertIn('RELAY_PORT=8149',text);self.assertIn('sys.executable',text);self.assertNotIn("str(BASE/'.venv/bin/python')",text);self.assertIn('RELAY_CONTEXT',text);compile(text,'server.py','exec');self.assertEqual(lab.adapt_project(self.project,sys.executable),result)
        (self.project/'server.py').write_text(text+'\n# new work\n')
        with self.assertRaisesRegex(ValueError,'edited'):lab.adapt_project(self.project,sys.executable)
    def test_missing_dependency_blocks_without_verification(self):
        self.fixture()
        with patch.object(lab.subprocess,'run',side_effect=self.fake_environment),patch.object(lab,'dependency_probe',return_value={'missing':[{'name':'rdkit','error':'ImportError'}]}):result=lab.adapt_project(self.project,sys.executable)
        self.assertEqual(result['status'],'BLOCKED');self.assertFalse((self.project/'_relay/ADAPTATION.json').exists())
    def test_destination_controls_cannot_reuse_source_port(self):
        source=self.fixture();original={}
        for name in ['START-LAB.sh','STOP-LAB.sh','STATUS-LAB.sh','SHOW-ACCESS.sh','START-SERVICES.sh','STOP-SERVICES.sh','STATUS.sh']:
            raw=(source/name).read_bytes();(self.project/name).write_bytes(raw);original[name]=hashlib.sha256(raw).hexdigest()
        (self.project/'tools').mkdir();raw=(source/'tools/lab-client.py').read_bytes();(self.project/'tools/lab-client.py').write_bytes(raw);original['tools/lab-client.py']=hashlib.sha256(raw).hexdigest()
        with patch.object(lab.subprocess,'run',side_effect=self.fake_environment),patch.object(lab,'dependency_probe',return_value={'missing':[],'versions':{}}),patch.object(lab,'choose_port',return_value=8148):result=lab.adapt_project(self.project,sys.executable)
        controls=result['destination_controls'];self.assertEqual(len(controls['files']),8)
        for name,digest in original.items():
            self.assertEqual(lab.sha(self.project/'_relay/source-launchers'/name),digest);self.assertNotIn('8090',(self.project/name).read_text())
        self.assertIn('lab_cli.py',(self.project/'START-LAB.sh').read_text());self.assertIn('LAB_URL',(self.project/'tools/lab-client.py').read_text());self.assertIn('GENESIS_RELAY_DESTINATION_URL_GUARD',(self.project/'tools/lab-client.py').read_text());self.assertEqual(lab.install_destination_controls(self.project)['changed_files'],[])
        (self.project/'STOP-LAB.sh').write_text('# operator edit\n')
        with self.assertRaisesRegex(ValueError,'modified'):lab.install_destination_controls(self.project)
    def test_access_helper_requires_tty(self):
        from genesis_relay import lab_cli
        with patch.object(sys.stdout,'isatty',return_value=False):self.assertEqual(lab_cli.main(['access','--project',str(self.project)]),1)
    def test_actual_owned_restart_and_live_foreign_listener_refusal(self):
        if sys.platform!='linux':self.skipTest('Linux owned-process adapter qualification only')
        source=self.fixture();shutil.copytree(source/'web',self.project/'web');shutil.copytree(source/'data',self.project/'data')
        with patch.object(lab,'dependency_probe',return_value={'missing':[],'versions':{}}):result=lab.adapt_project(self.project,sys.executable)
        try:
            first=lab.start(self.project);self.assertEqual(lab.status(self.project)['status'],'RUNNING');lab.stop(self.project);second=lab.start(self.project);self.assertNotEqual(first['pid'],second['pid']);self.assertTrue(lab.verify_restart(self.project)['status']=='PASSED')
        finally:lab.stop(self.project)
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);listener.bind(('127.0.0.1',result['port']));listener.listen()
            with self.assertRaisesRegex(RuntimeError,'occupied'):lab.start(self.project)
    def test_unowned_environment_not_overwritten(self):
        self.fixture();(self.project/'.relay-venv').mkdir()
        with self.assertRaisesRegex(ValueError,'unowned'):lab.adapt_project(self.project,sys.executable)
    def test_destination_registry_and_ui_do_not_inherit_source_verification(self):
        source=self.fixture();shutil.copytree(source/'web',self.project/'web');raw=(source/'SCIENTIFIC-CAPABILITIES.json').read_bytes();(self.project/'SCIENTIFIC-CAPABILITIES.json').write_bytes(raw);before_web=(self.project/'web/app.js').read_bytes()
        with patch.object(lab.subprocess,'run',side_effect=self.fake_environment),patch.object(lab,'dependency_probe',return_value={'missing':[],'versions':{'numpy':'synthetic-version'}}),patch.object(lab,'choose_port',return_value=8147):result=lab.adapt_project(self.project,sys.executable)
        self.assertEqual((self.project/'_relay/source-registries/SCIENTIFIC-CAPABILITIES.json').read_bytes(),raw);self.assertEqual((self.project/'_relay/source-web/app.js').read_bytes(),before_web);registry=lab.load(self.project/'SCIENTIFIC-CAPABILITIES.json');self.assertEqual(registry['registry_scope'],'DESTINATION_IMPORT_OBSERVATION');self.assertEqual(registry['python'],result['interpreter']);self.assertTrue(all(not e['verified_functions'] for e in registry['engines']));self.assertNotIn('FUNCTIONALLY_VERIFIED',{e['state'] for e in registry['engines']});self.assertNotIn("'Verified: '",(self.project/'web/app.js').read_text());self.assertIn('Destination import check',(self.project/'web/app.js').read_text());self.assertEqual(lab.install_destination_registry(self.project)['changed_files'],[])
    def test_database_and_artifact_relationships(self):
        (self.project/'private').mkdir();db=self.project/'private/laboratory.sqlite3'
        with sqlite3.connect(db) as c:c.execute('create table jobs (id text,status text)');c.execute('insert into jobs values (?,?)',('synthetic','succeeded'))
        result=lab._database(self.project);self.assertTrue(result['integrity_ok']);self.assertEqual(result['missing_artifacts'][0]['artifact'],'result.json')
        folder=self.project/'results/synthetic';folder.mkdir(parents=True);(folder/'result.json').write_text(json.dumps({'artifacts':['report.md']}));(folder/'report.md').write_text('Synthetic result');self.assertEqual(lab._database(self.project)['missing_artifacts'],[])
    def test_foreign_pid_cannot_be_stopped(self):
        with patch.object(lab,'identity',return_value={'pid':99,'start':'new','args':['other.py'],'cwd':str(self.project)}):self.assertFalse(lab.owned({'pid':99,'identity':{'start':'old'}},self.project))
    def test_literal_knowledge_capture_does_not_execute_source(self):
        marker=self.root/'executed';(self.project/'catalogue.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\nEXPERIMENTS=[{"id":"A","defaults":{}}]\n');(self.project/'README.md').write_text('# Synthetic project\nA local lab.\n');(self.project/'TEST-RESULTS.json').write_text(json.dumps({'passed':{'old':True},'failed':{},'checked_at_utc':'2020-01-01T00:00:00Z'}))
        result=knowledge.capture(self.project);self.assertFalse(marker.exists());self.assertEqual(result['historical_summary']['profile'],'GENERIC_PROJECT');self.assertEqual(result['historical_summary']['functional_status'],'UNKNOWN');self.assertTrue(result['historical_summary']['not_destination_verification']);self.assertEqual(len(result['documents']),9);self.assertTrue(any(c['classification']=='UNKNOWN' for c in result['evidence_index']['claims']));self.assertNotIn('GENESIS Science Lab',result['documents']['START-HERE.md'])
    def test_actual_lab_profile_parses_catalogue_without_import(self):
        self.fixture();marker=self.root/'executed';(self.project/'catalogue.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\nEXPERIMENTS=[{"id":"A","defaults":{}}]\n')
        result=knowledge.capture(self.project);self.assertFalse(marker.exists());self.assertEqual(len(result['catalogue']),1);self.assertEqual(result['historical_summary']['catalogue_experiments'],1)
    def test_sentinel_is_project_scoped(self):
        sentinel=self.root/'sentinel';sentinel.mkdir();(sentinel/'ENVIRONMENTS.json').write_text(json.dumps({'generation':'fixture','environments':[{'id':'ours','prefix':str(self.project/'.venv')},{'id':'other','prefix':'/unrelated/private/env'}]}));(sentinel/'CAPABILITY-GRAPH.json').write_text(json.dumps({'generation':'fixture','capabilities':[{'id':'ours:numpy','environment_id':'ours'},{'id':'other:secret','environment_id':'other'}]}));(sentinel/'PROJECT-MAP.json').write_text(json.dumps({'projects':[{'path':str(self.project)},{'path':'/unrelated/private/project'}]}))
        result=knowledge.sentinel_snapshot(self.project,sentinel);self.assertEqual(len(result['environments']),1);self.assertEqual(len(result['capabilities']),1);self.assertEqual(len(result['projects']),1);self.assertEqual(result['classification'],'HISTORICAL_REPORT')
    def test_direct_url_credentials_are_removed(self):self.assertEqual(knowledge._safe_url('https://user:password@example.invalid/path?token=secret#frag'),'https://example.invalid/path')

if __name__=='__main__':unittest.main(verbosity=2)
