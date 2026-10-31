"""Known synthetic continuation, real snapshot and trusted acceptance tests."""
import json,os,sqlite3,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from genesis_relay import capsule,demo,receiver,returns
from genesis_relay.common import module_command,sha

class DemoTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='relay-demo-test-');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.source=self.root/'synthetic lab';demo.create(self.source)
 def exported(self):return demo.export_demo(self.source,self.root/'state',self.root/'capsule.zip')
 def restored(self):return demo.restore_demo(self.exported()['path'],self.root/'receiver')
 def test_synthetic_complete_export_without_external_requirements(self):
  e=self.exported();v=capsule.verify(e['path']);self.assertTrue(v['completeness']['full_non_secret_project_complete']);self.assertEqual(v['completeness']['counts']['UNREADABLE_OR_MISSING'],0);self.assertTrue(any(x['path']=='private/observations.sqlite3' and x['disposition']=='INCLUDED_TRANSFORMED' for x in v['manifest']['entries']));self.assertFalse(v['completeness']['offline_ready'])
 def test_owned_creation_is_idempotent_and_preserves_independent_work(self):
  (self.source/'operator.txt').write_text('Keep');self.assertFalse(demo.create(self.source)['created']);self.assertEqual((self.source/'operator.txt').read_text(),'Keep');other=self.root/'unrelated';other.mkdir()
  with self.assertRaisesRegex(ValueError,'nothing overwritten'):demo.create(other)
 def test_restoration_accepts_real_arithmetic_and_database_history(self):
  rec=self.restored();accepted=demo.accept_demo(rec['receipt_path']);self.assertTrue(accepted['ready_to_continue']);self.assertEqual(accepted['receiver_state'],'READY_TO_CONTINUE');self.assertEqual(len(accepted['acceptance']['passed']),5);self.assertEqual(accepted['acceptance']['failed'],{});self.assertEqual(receiver.digest(rec['capsule_path']),rec['archive_sha256']);self.assertEqual(demo._database(Path(rec['project_path']))['runs'],2);self.assertEqual(demo._database(self.source)['runs'],1)
 def test_source_script_changes_cannot_execute_or_claim_ready(self):
  rec=self.restored();demo.accept_demo(rec['receipt_path']);project=Path(rec['project_path']);marker=self.root/'executed';(project/'experiment.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\n');failed=demo.accept_demo(rec['receipt_path']);self.assertFalse(failed['ready_to_continue']);self.assertIn('trusted_demo_source_bytes',failed['acceptance']['failed']);self.assertFalse(marker.exists());self.assertEqual(demo._database(project)['runs'],2)
 def test_changed_data_fails_numerical_acceptance(self):
  rec=self.restored();project=Path(rec['project_path']);(project/'data/observations.csv').write_text('id,value\nsample-a,2\nsample-b,4\nsample-c,600\n');failed=demo.accept_demo(rec['receipt_path']);self.assertFalse(failed['ready_to_continue']);self.assertIn('independent_mean',failed['acceptance']['failed'])
 def test_actual_return_selected_apply_duplicate_conflict_and_rollback(self):
  rec=self.restored();demo.accept_demo(rec['receipt_path']);ret=demo.change_and_return(rec['receipt_path'],self.root/'return.zip');result=demo.reconcile_demo(ret['path'],self.source);self.assertEqual(result['status'],'PASSED');self.assertTrue(result['source_project_unchanged']);self.assertTrue(result['independent_conflict_refused']);self.assertTrue(returns.preview_return(ret['path'],self.source)['database_reconciliation'])
 def test_known_script_runs_independently_with_current_python(self):
  p=subprocess.run([sys.executable,'-I',str(self.source/'experiment.py'),'--project',str(self.source)],cwd=self.root,capture_output=True,text=True,timeout=20);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)['mean'],4.0)
 def test_frozen_dispatch_does_not_treat_relay_as_python(self):
  with patch.object(sys,'frozen',True,create=True):self.assertEqual(module_command('genesis_relay.ui','serve'),[sys.executable,'_module','genesis_relay.ui','serve']);self.assertTrue(receiver.destination_capabilities()['receiver_runtime_inclusive']);self.assertIsNone(receiver.destination_capabilities()['receiver_python'])
  with self.assertRaises(ValueError):module_command('arbitrary.capsule.module')
 def test_opaque_db_file_is_preserved_and_returned_without_sqlite_guess(self):
  (self.source/'opaque.db').write_bytes(b'Opaque non-SQLite project data');rec=self.restored();self.assertEqual(receiver.verify_restoration(rec)['status'],'PASSED');work=Path(rec['project_path']);(work/'opaque.db').write_bytes(b'Updated opaque non-SQLite project data');ret=returns.create_return(rec,self.root/'opaque-return.zip');row=next(x for x in returns.verify_return(ret['path'])['manifest']['entries'] if x['path']=='opaque.db');self.assertEqual(row['operation'],'UPDATE')

if __name__=='__main__':unittest.main(verbosity=2)
