"""Real temporary capsule receipt, safe restoration and return protocol checks.

PowerShell tests execute on Linux when available; they do not qualify Windows.
"""
import hashlib,json,os,shutil,sqlite3,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from genesis_relay import capsule,receiver as r,returns as back

class ReceiverReturnTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='relay-receiver-test-');self.root=Path(self.tmp.name);self.source=self.root/'source';self.source.mkdir();(self.source/'README.md').write_text('Original project purpose.\n');(self.source/'AGENTS.md').write_text('Archived source instructions.\n');(self.source/'.hidden').write_text('hidden source\n');(self.source/'data').mkdir();(self.source/'data/α value.txt').write_text('unicode and spaces\n');self.export=capsule.export(self.source,state_dir=self.root/'sender',quiesce=False);self.dest=self.root/'destination'
 def tearDown(self):self.tmp.cleanup()
 def restore(self):return r.restore(self.export['path'],self.dest)
 def returned(self,edit='Continued work.\n'):
  rec=self.restore();(Path(rec['project_path'])/'README.md').write_text(edit);ret=back.create_return(rec,self.root/'return.zip');return rec,ret
 def test_inspect_and_plan_are_non_executing(self):
  with patch.object(subprocess,'Popen',side_effect=AssertionError('must not execute')):
   info=r.inspect(self.export['path']);plan=r.plan(self.export['path'],self.dest)
  self.assertFalse(info['inspection_executes_code']);self.assertFalse(plan['plan_executes_code']);self.assertFalse(self.dest.exists())
 def test_restore_separates_immutable_source_and_guidance(self):
  rec=self.restore();work=Path(rec['project_path']);self.assertEqual((work/'data/α value.txt').read_bytes(),(self.source/'data/α value.txt').read_bytes());self.assertEqual((work/'.hidden').read_text(),'hidden source\n');self.assertEqual((work/'AGENTS.source.md').read_bytes(),(self.source/'AGENTS.md').read_bytes());self.assertIn('destination guidance',(work/'AGENTS.md').read_text());self.assertTrue((work/'_relay/knowledge/EVIDENCE-INDEX.json').is_file());self.assertEqual(r.digest(rec['capsule_path']),self.export['sha256']);self.assertEqual(r.verify_restoration(rec)['status'],'PASSED');self.assertEqual(rec['transport'],'DESTINATION_RECEIPT' if os.name=='nt' else 'LOCAL_ROUNDTRIP_ONLY')
  if os.name!='nt':self.assertEqual(Path(rec['receipt_path']).stat().st_mode&0o777,0o600);self.assertEqual(Path(rec['evidence_path']).stat().st_mode&0o777,0o700)
 def test_duplicate_receipt_preserves_new_work(self):
  rec=self.restore();work=Path(rec['project_path']);(work/'README.md').write_text('new independent work');again=self.restore();self.assertTrue(again['duplicate_receipt']);self.assertEqual((work/'README.md').read_text(),'new independent work')
 def test_existing_unrelated_workspace_preserved(self):
  p=r.plan(self.export['path'],self.dest);project=Path(p['project_path']);project.mkdir(parents=True);(project/'mine.txt').write_text('do not change')
  with self.assertRaisesRegex(ValueError,'refusing overwrite'):self.restore()
  self.assertEqual((project/'mine.txt').read_text(),'do not change')
 @unittest.skipIf(os.name=='nt','This fixture creates Linux filenames that Windows cannot create; native Windows tests are separate')
 def test_windows_path_mapping_and_native_separation(self):
  for name in ['CON.txt','a:b.txt','Name.txt','name.txt','trailing.']:(self.source/name).write_text(name)
  exp=capsule.export(self.source,state_dir=self.root/'sender2',quiesce=False);plan=r.plan(exp['path'],self.dest,'NATIVE_WINDOWS_X64');self.assertTrue(plan['path_mappings']);self.assertTrue(plan['blocked_prerequisites']);self.assertFalse(self.dest.exists())
  with self.assertRaisesRegex(RuntimeError,'Native Windows'):r.restore(exp['path'],self.dest,'NATIVE_WINDOWS_X64')
 def test_wsl_not_inferred_from_linux(self):
  with patch.dict(os.environ,{},clear=True),patch('platform.release',return_value='ordinary-linux'):
   p=r.plan(self.export['path'],self.dest,'WSL_LINUX_X64')
  self.assertTrue(any('actual WSL' in x for x in p['blocked_prerequisites']))
 def test_insufficient_destination_storage(self):
  with patch.object(shutil,'disk_usage',return_value=shutil._ntuple_diskusage(1,1,0)):
   plan=r.plan(self.export['path'],self.dest)
  self.assertTrue(any('Insufficient' in x for x in plan['blocked_prerequisites']))
 def test_interrupted_materialization_resumes(self):
  original=r._write_object;count=[0]
  def interrupted(*args):
   count[0]+=1
   if count[0]==2:raise OSError('simulated interruption')
   return original(*args)
  with patch.object(r,'_write_object',side_effect=interrupted):
   with self.assertRaisesRegex(OSError,'simulated'):self.restore()
  rec=self.restore();self.assertEqual(rec['state'],'RESTORED');self.assertEqual((Path(rec['project_path'])/'README.md').read_bytes(),(self.source/'README.md').read_bytes());states=[x['state'] for x in rec['history']];order=['RECEIVED','INTEGRITY_VERIFIED','RESTORATION_PLANNED','RESTORED'];self.assertEqual([order.index(x) for x in states],sorted(order.index(x) for x in states))
 def test_interrupted_transfer_resumes_matching_prefix(self):
  plan=r.plan(self.export['path'],self.dest);evidence=Path(plan['evidence_path']);evidence.mkdir(parents=True);data=Path(self.export['path']).read_bytes();(evidence/'capsule.zip.partial').write_bytes(data[:100]);rec=self.restore();self.assertEqual(r.digest(rec['capsule_path']),self.export['sha256'])
 def test_changed_transfer_prefix_rejected(self):
  plan=r.plan(self.export['path'],self.dest);evidence=Path(plan['evidence_path']);evidence.mkdir(parents=True);(evidence/'capsule.zip.partial').write_bytes(b'incorrect prefix')
  with self.assertRaisesRegex(ValueError,'prefix differs'):self.restore()
  self.assertEqual((evidence/'capsule.zip.partial').read_bytes(),b'incorrect prefix')
 def test_return_success_conflict_duplicate_and_rollback(self):
  rec,ret=self.returned();self.assertEqual(Path(ret['path']).stat().st_mode&0o777,0o600) if os.name!='nt' else None;preview=back.preview_return(ret['path'],self.source);row=next(x for x in preview['entries'] if x['path']=='README.md');self.assertEqual(row['decision'],'APPLICABLE');applied=back.apply_return(preview,['README.md']);self.assertEqual((self.source/'README.md').read_text(),'Continued work.\n');self.assertTrue(back.apply_return(preview,['README.md'])['duplicate_import']);rolled=back.rollback_return(applied);self.assertEqual(rolled['state'],'ROLLED_BACK');self.assertEqual((self.source/'README.md').read_text(),'Original project purpose.\n');self.assertTrue(back.preview_return(ret['path'],self.source)['duplicate'])
 def test_return_conflict_never_overwrites_newer_work(self):
  rec,ret=self.returned();(self.source/'README.md').write_text('independent source edit');preview=back.preview_return(ret['path'],self.source);self.assertIn('README.md',preview['conflicts'])
  with self.assertRaisesRegex(ValueError,'conflict'):back.apply_return(preview,['README.md'])
  self.assertEqual((self.source/'README.md').read_text(),'independent source edit')
 def test_stale_preview_rejected(self):
  rec,ret=self.returned();preview=back.preview_return(ret['path'],self.source);(self.source/'README.md').write_text('late edit')
  with self.assertRaises(ValueError):back.apply_return(preview,['README.md'])
  self.assertEqual((self.source/'README.md').read_text(),'late edit')
 def test_return_new_file_and_proposed_delete_require_selection(self):
  rec=self.restore();work=Path(rec['project_path']);(work/'new idea.md').write_text('new idea');(work/'.hidden').unlink();ret=back.create_return(rec,self.root/'return.zip');p=back.preview_return(ret['path'],self.source);deleted=next(e for e in p['entries'] if e['path']=='.hidden');self.assertEqual(deleted['decision'],'DELETE_REQUIRES_SELECTION');applied=back.apply_return(p);self.assertTrue((self.source/'.hidden').exists());self.assertEqual((self.source/'new idea.md').read_text(),'new idea');self.assertEqual(back.rollback_return(applied)['state'],'ROLLED_BACK');self.assertFalse((self.source/'new idea.md').exists())
 def test_return_credentials_excluded_and_database_separate(self):
  rec=self.restore();work=Path(rec['project_path']);(work/'private').mkdir();(work/'private/access.json').write_text(json.dumps({'password':'KNOWN-SECRET-RETURN-FIXTURE'}));(work/'debug.txt').write_text('KNOWN-SECRET-RETURN-FIXTURE');(work/'.env.production').write_text('PRIVATE_VALUE=ordinary-private-value');c=sqlite3.connect(work/'private/new.sqlite3');c.execute('create table t(id text primary key,value int)');c.execute('insert into t values("stable-id",3)');c.commit();c.close();ret=back.create_return(rec,self.root/'return.zip');verified=back.verify_return(ret['path']);lookup={x['path']:x for x in verified['manifest']['entries']};self.assertEqual(lookup['private/access.json']['operation'],'EXCLUDED_WITH_REASON');self.assertEqual(lookup['debug.txt']['operation'],'EXCLUDED_WITH_REASON');self.assertEqual(lookup['.env.production']['operation'],'EXCLUDED_WITH_REASON');self.assertEqual(lookup['private/new.sqlite3']['operation'],'DATABASE_SNAPSHOT');p=back.preview_return(ret['path'],self.source);self.assertIn('private/new.sqlite3',p['database_reconciliation'])
  with self.assertRaisesRegex(ValueError,'database'):back.apply_return(p,['private/new.sqlite3'])
  with zipfile.ZipFile(ret['path']) as z:self.assertTrue(all(b'KNOWN-SECRET-RETURN-FIXTURE' not in z.read(n) for n in z.namelist()))
 def test_platform_adaptation_is_reviewed(self):
  rec=self.restore();work=Path(rec['project_path']);(work/'README.md').write_text('adapted base');r.record_adaptation(rec,{'note':'synthetic platform adaptation'});rec=r.read(rec['receipt_path']);(work/'README.md').write_text('continued on adapted base');ret=back.create_return(rec,self.root/'return.zip');p=back.preview_return(ret['path'],self.source);self.assertEqual(next(x for x in p['entries'] if x['path']=='README.md')['decision'],'PLATFORM_ADAPTATION_REVIEW')
 def test_rollback_refuses_newer_independent_edit(self):
  rec,ret=self.returned();applied=back.apply_return(back.preview_return(ret['path'],self.source),['README.md']);(self.source/'README.md').write_text('edited after import');rolled=back.rollback_return(applied);self.assertEqual(rolled['state'],'ROLLBACK_CONFLICT');self.assertEqual((self.source/'README.md').read_text(),'edited after import')
 def test_corrupt_return_rejected(self):
  rec,ret=self.returned();original=Path(ret['path']);bad=self.root/'bad.zip'
  with zipfile.ZipFile(original) as src,zipfile.ZipFile(bad,'w') as dst:
   for item in src.infolist():dst.writestr(item.filename,b'corrupted' if item.filename.startswith('objects/') else src.read(item))
  with self.assertRaisesRegex(ValueError,'hash mismatch'):back.verify_return(bad)
 def test_powershell_parse_and_linux_inspect_only(self):
  pwsh=shutil.which('pwsh')
  if not pwsh:self.skipTest('PowerShell unavailable; no Windows claim')
  script=Path(__file__).resolve().parents[1]/'windows/Receive-Relay.ps1';result=subprocess.run([pwsh,'-NoProfile','-NonInteractive','-File',str(script),'-Operation','Inspect','-Capsule',self.export['path'],'-Python',sys.executable],capture_output=True,text=True,timeout=30);self.assertEqual(result.returncode,0,result.stderr);d=json.loads(result.stdout);self.assertEqual(d['capsule_id'],self.export['capsule_id']);self.assertFalse(d['inspection_executes_code'])
 def test_receiver_cli_apply_gate(self):
  env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');p=subprocess.run([sys.executable,'-m','genesis_relay.receive_cli','Restore','--capsule',self.export['path'],'--destination-root',str(self.dest),'--route','LOCAL_LINUX'],capture_output=True,text=True,env=env,timeout=30);self.assertNotEqual(p.returncode,0);self.assertIn('explicit --apply',p.stderr);self.assertFalse(self.dest.exists())


 def test_object_partial_resume_and_final_rename_recovery(self):
  with patch.object(r,'_write_object',side_effect=OSError('synthetic interrupted materialization')):
   with self.assertRaises(OSError):self.restore()
  plan=r.plan(self.export['path'],self.dest);partial=Path(plan['project_path']).with_name(Path(plan['project_path']).name+'.partial');(partial/'.README.md.relay-partial').write_bytes((self.source/'README.md').read_bytes()[:5]);rec=self.restore();self.assertEqual((Path(rec['project_path'])/'README.md').read_bytes(),(self.source/'README.md').read_bytes())
  other=self.root/'destination-final-gap'
  with patch.object(r,'record_adaptation',side_effect=OSError('synthetic final receipt interruption')):
   with self.assertRaises(OSError):r.restore(self.export['path'],other)
  recovered=r.restore(self.export['path'],other);self.assertEqual(recovered['state'],'RESTORED');self.assertEqual(r.verify_restoration(recovered)['status'],'PASSED')
 def test_return_letter_and_destination_records_preserved(self):
  rec=self.restore();work=Path(rec['project_path']);(work/'_relay/ADAPTATION.json').write_text(json.dumps({'route':'LOCAL_LINUX','note':'synthetic change'}));ret=back.create_return(rec,self.root/'return.zip');verified=back.verify_return(ret['path']);paths=[e['path'] for e in verified['manifest']['entries']];self.assertTrue(any(p.endswith('/ADAPTATION.json') and p.startswith('_relay-returned/') for p in paths))
  with zipfile.ZipFile(ret['path']) as z:self.assertIn('return letter',z.read('RETURN-LETTER.md').decode())
 def test_interrupted_apply_journal_rollback(self):
  rec,ret=self.returned();applied=back.apply_return(back.preview_return(ret['path'],self.source),['README.md']);journal=r.read(applied['receipt_path']);journal.update(state='APPLYING',applied=[],in_progress='README.md');r.atomic(applied['receipt_path'],journal);duplicate=back.apply_return(back.preview_return(ret['path'],self.source),['README.md']);self.assertTrue(duplicate['recovery_required']);rolled=back.rollback_return(applied['receipt_path']);self.assertEqual(rolled['state'],'ROLLED_BACK');self.assertEqual((self.source/'README.md').read_text(),'Original project purpose.\n')
 def test_powershell_trusted_bootstrap_ignores_untrusted_current_directory(self):
  pwsh=shutil.which('pwsh')
  if not pwsh:self.skipTest('PowerShell unavailable')
  evil=self.root/'untrusted cwd';evil.mkdir();(evil/'genesis_relay').mkdir();marker=evil/'SHOULD-NOT-EXECUTE';(evil/'genesis_relay/__init__.py').write_text('from pathlib import Path; Path('+repr(str(marker))+').touch(); raise RuntimeError("untrusted module")')
  script=Path(__file__).resolve().parents[1]/'windows/Receive-Relay.ps1';result=subprocess.run([pwsh,'-NoProfile','-NonInteractive','-File',str(script),'-Operation','Inspect','-Capsule',self.export['path'],'-Python',sys.executable],cwd=evil,capture_output=True,text=True,timeout=30);self.assertEqual(result.returncode,0,result.stderr);self.assertFalse(marker.exists());self.assertEqual(json.loads(result.stdout)['capsule_id'],self.export['capsule_id'])


 def test_acceptance_binding_failed_history_then_qualified_ready(self):
  rec=self.restore();work=Path(rec['project_path']);folder=work/'_relay/verification';folder.mkdir();base={'route':rec['route'],'project_path':str(work),'source_capsule_id':rec['capsule_id'],'source_capsule_sha256':rec['archive_sha256'],'passed':{'synthetic_fixture_check':True},'failed':{'synthetic_expected_failure':'retained'},'skipped':{},'status':'FAILED'}
  base['receipt_path']=str(folder/'failed.json');r.atomic(base['receipt_path'],base);failed=r.record_acceptance(rec,base);self.assertEqual(failed['state'],'RESTORED');self.assertFalse(failed['ready_to_continue']);self.assertEqual(len(failed['failures']),1)
  success={**base,'failed':{},'status':'ACCEPTANCE_PASSED','receipt_path':str(folder/'passed.json')};r.atomic(success['receipt_path'],success);ready=r.record_acceptance(rec,success);self.assertEqual(ready['state'],'READY_TO_CONTINUE');self.assertTrue(ready['ready_to_continue']);self.assertEqual(ready['readiness_scope'],'NATIVE_WINDOWS_X64' if os.name=='nt' else 'LOCAL_ROUNDTRIP_ONLY');self.assertEqual(len(ready['acceptance_history']),2);self.assertEqual(len(ready['failures']),1);self.assertEqual(r.digest(rec['capsule_path']),self.export['sha256'])
  later={**base,'receipt_path':str(folder/'later-failed.json')};r.atomic(later['receipt_path'],later);not_ready=r.record_acceptance(rec,later);self.assertFalse(not_ready['ready_to_continue']);self.assertEqual(not_ready['state'],'READY_TO_CONTINUE');self.assertEqual(len(not_ready['failures']),2)
 def test_acceptance_rejects_wrong_binding_and_skips(self):
  rec=self.restore();work=Path(rec['project_path']);folder=work/'_relay/verification';folder.mkdir();value={'route':rec['route'],'project_path':str(work),'source_capsule_id':'wrong','source_capsule_sha256':rec['archive_sha256'],'passed':{'synthetic':True},'failed':{},'skipped':{},'status':'ACCEPTANCE_PASSED','receipt_path':str(folder/'wrong.json')};r.atomic(value['receipt_path'],value)
  with self.assertRaisesRegex(ValueError,'another capsule'):r.record_acceptance(rec,value)
  value.update(source_capsule_id=rec['capsule_id'],status='PARTIAL',skipped={'synthetic_optional':'not run'},receipt_path=str(folder/'partial.json'));r.atomic(value['receipt_path'],value);partial=r.record_acceptance(rec,value);self.assertFalse(partial['ready_to_continue']);self.assertEqual(partial['state'],'RESTORED')
 def test_fresh_process_reads_delivered_guidance_and_evidence(self):
  rec=self.restore();work=Path(rec['project_path']);script='from pathlib import Path; import json,sys; p=Path(sys.argv[1]); assert "destination guidance" in (p/"AGENTS.md").read_text(); assert (p/"START-HERE.md").is_file(); k=p/"_relay/knowledge"; assert all((k/n).is_file() for n in ["PROJECT-PURPOSE.md","ARCHITECTURE.md","CURRENT-STATE.md","KNOWN-PROBLEMS.md","NEXT-STEPS.md"]); assert json.loads((k/"EVIDENCE-INDEX.json").read_text()); print("delivered knowledge discovered")';result=subprocess.run([sys.executable,'-I','-c',script,str(work)],capture_output=True,text=True,timeout=20);self.assertEqual(result.returncode,0,result.stderr);self.assertIn('delivered knowledge',result.stdout)
 def test_selected_other_interpreter_not_mislabelled_and_wsl_architecture(self):
  value=r.destination_capabilities('/not-this-interpreter/python');self.assertIsNone(value['python_version']);self.assertIn('NOT_RUN',value['selected_interpreter_probe'])
  with patch('platform.release',return_value='microsoft-wsl2'),patch('platform.machine',return_value='aarch64'):
   plan=r.plan(self.export['path'],self.dest,'WSL_LINUX_X64')
  self.assertTrue(plan['blocked_prerequisites'])


 def test_receiver_reserved_names_preserve_every_source_payload(self):
  (self.source/'START-HERE.md').write_text('Original source start document\n');(self.source/'AGENTS.source.md').write_text('User file already owns this alias\n');(self.source/'AGENTS.override.md').write_text('Archived source override, never autoactivate\n');(self.source/'.relay-reconstruction.json').write_text('{"source":true}');(self.source/'.README.md.relay-partial').write_text('Genuine source file with receiver temporary suffix\n');(self.source/'_relay/knowledge').mkdir(parents=True);(self.source/'_relay/knowledge/PROJECT-PURPOSE.md').write_text('Genuine source payload, not generated knowledge\n');(self.source/'_relay/source-guidance').mkdir();(self.source/'_relay/source-guidance/AGENTS.md').write_text('Genuine nested source payload\n');(self.source/'nested').mkdir();(self.source/'nested/AGENTS.md').write_text('Nested source guidance\n');(self.source/'.relay-return-history').mkdir();(self.source/'.relay-return-history/user.txt').write_text('Original source history\n');(self.source/'link').symlink_to('README.md');(self.source/'link.relay-symlink.txt').write_text('User file must not be overwritten by descriptor\n')
  exp=capsule.export(self.source,state_dir=self.root/'reserved-sender',quiesce=False);rec=r.restore(exp['path'],self.root/'reserved-dest');work=Path(rec['project_path']);mapping={e['source_path']:e for e in rec['mapping']}
  for name in ['AGENTS.md','START-HERE.md','AGENTS.source.md','AGENTS.override.md','.relay-reconstruction.json','.README.md.relay-partial','_relay/knowledge/PROJECT-PURPOSE.md','_relay/source-guidance/AGENTS.md','nested/AGENTS.md','.relay-return-history/user.txt','link.relay-symlink.txt']:
   self.assertEqual((work/mapping[name]['destination_path']).read_bytes(),(self.source/name).read_bytes(),name)
  self.assertEqual((work/'AGENTS.source.md').read_text(),'User file already owns this alias\n');self.assertIn('destination guidance',(work/'AGENTS.md').read_text());self.assertIn('# Received',(work/'START-HERE.md').read_text());self.assertFalse((work/'AGENTS.override.md').exists());self.assertFalse((work/'nested/AGENTS.md').exists());self.assertFalse((work/'link').is_symlink());self.assertEqual((work/mapping['link']['destination_path']).read_bytes(),b'README.md');self.assertEqual(r.digest(rec['capsule_path']),exp['sha256'])

if __name__=='__main__':unittest.main(verbosity=2)
