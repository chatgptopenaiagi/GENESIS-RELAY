import hashlib,json,os,sqlite3,subprocess,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from genesis_relay import capsule,discovery,state
from genesis_relay.common import load,sha
class CapsuleTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.source=self.root/'source';self.source.mkdir();(self.source/'README.md').write_text('# Example project\n');(self.source/'.hidden').write_text('hidden local work');self.home=self.root/'state'
 def tearDown(self):self.tmp.cleanup()
 def export(self):return capsule.export(self.source,state_dir=self.home,quiesce=False)
 def mutate(self,path,change):
  dest=self.root/('mutated-'+str(len(list(self.root.glob('mutated*'))))+'.zip')
  with zipfile.ZipFile(path) as z:files={n:z.read(n) for n in z.namelist()}
  change(files)
  with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED) as z:
   for n,raw in files.items():z.writestr(n,raw)
  return dest
 def test_full_entry_accounting_and_hidden_source(self):
  (self.source/'private').mkdir();(self.source/'private/access.json').write_text(json.dumps({'username':'x','password':'EXAMPLE-ONLY-password'}));(self.source/'.venv').mkdir();(self.source/'.venv/my-user-script.py').write_text('print(42)');d=discovery.discover(self.source);rows={e['path']:e for e in d['entries']};self.assertEqual(sum(d['counts'].values()),d['entry_count']);self.assertEqual(rows['.hidden']['disposition'],'INCLUDED_EXACT');self.assertEqual(rows['private/access.json']['disposition'],'EXCLUDED_WITH_REASON');self.assertEqual(rows['.venv/my-user-script.py']['disposition'],'INCLUDED_EXACT')
 def test_export_integrity_and_separate_external_checksum(self):
  d=self.export();v=capsule.verify(d['path']);self.assertTrue(v['verified']);self.assertTrue(v['completeness']['full_non_secret_project_complete']);self.assertEqual(sha(d['path']),d['sha256']);self.assertTrue(Path(d['path']+'.sha256').read_text().startswith(d['sha256']));self.assertEqual(state.status(self.home)['capsules'][d['capsule_id']]['state'],'VERIFIED_FOR_TRANSFER')
 def test_no_transport_claim_without_receipt(self):
  d=self.export()
  with self.assertRaises(ValueError):state.record(self.home,d['capsule_id'],'EXPORTED')
 def test_live_sqlite_uses_backup_integrity(self):
  db=self.source/'records.sqlite3';con=sqlite3.connect(db);con.execute('pragma journal_mode=wal');con.execute('create table records(id primary key,value)');con.execute('insert into records values(?,?)',('stable-id',42));con.commit();d=self.export();v=capsule.verify(d['path']);row=next(e for e in v['manifest']['entries'] if e['path']=='records.sqlite3');self.assertEqual(row['disposition'],'INCLUDED_TRANSFORMED')
  with zipfile.ZipFile(d['path']) as z:(self.root/'backup.sqlite').write_bytes(z.read(row['object']))
  copy=sqlite3.connect(self.root/'backup.sqlite');self.assertEqual(copy.execute('select * from records').fetchall(),[('stable-id',42)]);self.assertEqual(copy.execute('pragma integrity_check').fetchone()[0],'ok');copy.close();con.close()
 def test_changed_during_capture_is_bounded_failure(self):
  with patch.object(capsule,'_signature',side_effect=lambda p:(1,1,__import__('time').monotonic_ns(),0o644)):
   with self.assertRaises(capsule.CapsuleError):self.export()
  self.assertTrue(any(v['failures'] for v in state.status(self.home)['capsules'].values()))
 def test_insufficient_storage_preserves_source(self):
  usage=__import__('shutil').disk_usage(self.root)
  with patch.object(capsule.shutil,'disk_usage',return_value=type(usage)(usage.total,usage.used,0)):
   with self.assertRaisesRegex(capsule.CapsuleError,'Insufficient'):self.export()
  self.assertEqual((self.source/'.hidden').read_text(),'hidden local work')
 def test_interrupted_export_keeps_prior_capsule(self):
  d=self.export();before=sha(d['path'])
  with patch.object(zipfile.ZipFile,'write',side_effect=OSError('simulated interruption')):
   with self.assertRaises(OSError):self.export()
  self.assertEqual(sha(d['path']),before);self.assertTrue(list((self.home/'capsules').glob('*.partial')))
 def test_missing_member_rejected(self):
  d=self.export();bad=self.mutate(d['path'],lambda f:f.pop('START-HERE.md'))
  with self.assertRaises(capsule.CapsuleError):capsule.verify(bad)
 def test_payload_corruption_rejected(self):
  d=self.export()
  def damage(files):files[next(n for n in files if n.startswith('objects/'))]=b'corrupt'
  with self.assertRaises(capsule.CapsuleError):capsule.verify(self.mutate(d['path'],damage))
 def test_unsupported_major_rejected(self):
  d=self.export()
  def damage(f):j=json.loads(f['CAPSULE.json']);j['format_version']='2.0';f['CAPSULE.json']=json.dumps(j).encode()
  with self.assertRaisesRegex(capsule.CapsuleError,'major'):capsule.verify(self.mutate(d['path'],damage))
 def test_unsafe_archive_paths(self):
  for name in ['../evil','/absolute','C:/evil','\\\\server\\share','objects/../x','NUL','objects/x:ads','objects/a.']:
   path=self.root/'bad.zip'
   with zipfile.ZipFile(path,'w') as z:z.writestr(name,'x')
   with self.assertRaises(capsule.CapsuleError,msg=name):capsule.verify(path)
 def test_duplicate_case_colliding_entries(self):
  for names in [('a','a'),('objects/One','objects/one')]:
   path=self.root/'bad.zip'
   with zipfile.ZipFile(path,'w') as z:
    for n in names:z.writestr(n,'x')
   with self.assertRaises(capsule.CapsuleError):capsule.verify(path)
 def test_zip_symlink_rejected(self):
  path=self.root/'bad.zip';info=zipfile.ZipInfo('objects/link');info.create_system=3;info.external_attr=(0o120777<<16)
  with zipfile.ZipFile(path,'w') as z:z.writestr(info,'/etc/passwd')
  with self.assertRaises(capsule.CapsuleError):capsule.verify(path)
 def test_expansion_and_entry_limits(self):
  d=self.export()
  with self.assertRaises(capsule.CapsuleError):capsule.verify(d['path'],max_bytes=10)
  with self.assertRaises(capsule.CapsuleError):capsule.verify(d['path'],max_entries=1)
 def test_unicode_spaces_and_windows_names_lossless_in_evidence(self):
  for name in ['α result.txt','two words.txt','CON.txt','Case.txt','case.txt','colon:name']:(self.source/name).write_text(name)
  d=self.export();v=capsule.verify(d['path']);paths={e['path'] for e in v['manifest']['entries']};self.assertTrue({'α result.txt','CON.txt','Case.txt','case.txt','colon:name'}<=paths)
 def test_secret_content_exclusion_is_visible(self):
  (self.source/'notes.txt').write_text('ghp_'+'A'*40);d=self.export();v=capsule.verify(d['path']);self.assertFalse(v['completeness']['full_non_secret_project_complete']);e=next(e for e in v['manifest']['entries'] if e['path']=='notes.txt');self.assertEqual(e['disposition'],'EXCLUDED_WITH_REASON')
 def test_offline_ready_not_fabricated(self):
  with self.assertRaisesRegex(ValueError,'OFFLINE_READY_BLOCKED'):capsule.plan(self.source,mode='offline-ready')
 def test_lightweight_explicit_reduction(self):
  (self.source/'results').mkdir();(self.source/'results/old.txt').write_text('research');d=capsule.export(self.source,state_dir=self.home,quiesce=False,mode='lightweight');v=capsule.verify(d['path']);self.assertFalse(v['completeness']['full_non_secret_project_complete']);self.assertTrue(any(e['reason'].startswith('Explicit lightweight') for e in v['manifest']['entries']))
 def test_dirty_git_bundle_and_working_tree(self):
  def git(*args):return subprocess.run(['git','-C',str(self.source),*args],check=True,capture_output=True,text=True)
  git('init');git('config','user.email','fixture@example.invalid');git('config','user.name','Synthetic Fixture');git('add','README.md');git('commit','-m','base');(self.source/'README.md').write_text('staged');git('add','README.md');(self.source/'README.md').write_text('unstaged');(self.source/'new.txt').write_text('untracked');d=self.export();v=capsule.verify(d['path']);self.assertTrue(v['completeness']['git']['bundle_verified'])
  with zipfile.ZipFile(d['path']) as z:self.assertIn('history/staged.patch',z.namelist());self.assertIn('history/unstaged.patch',z.namelist());self.assertIn('history/project.bundle',z.namelist())
  self.assertEqual((self.source/'README.md').read_text(),'unstaged');self.assertTrue((self.source/'new.txt').exists())
 def test_non_sqlite_database_suffix_not_relabelled(self):
  (self.source/'opaque.db').write_bytes(b'opaque non-SQLite evidence');d=self.export();e=next(e for e in capsule.verify(d['path'])['manifest']['entries'] if e['path']=='opaque.db');self.assertEqual(e['disposition'],'INCLUDED_EXACT')
 def test_unreadable_directory_accounted_and_blocks_snapshot(self):
  folder=self.source/'unreadable';folder.mkdir();original=discovery.os.scandir
  def scan(path):
   if Path(path)==folder:raise PermissionError('synthetic denied directory')
   return original(path)
  with patch.object(discovery.os,'scandir',side_effect=scan):
   d=discovery.discover(self.source);e=next(e for e in d['entries'] if e['path']=='unreadable');self.assertEqual(e['disposition'],'UNREADABLE_OR_MISSING')
   with self.assertRaises(capsule.CapsuleError):self.export()
 def test_missing_git_object_is_incomplete_not_invented(self):
  def git(*args):return subprocess.run(['git','-C',str(self.source),*args],check=True,capture_output=True,text=True).stdout.strip()
  git('init');git('config','user.email','fixture@example.invalid');git('config','user.name','Synthetic Fixture');git('add','README.md');git('commit','-m','base');oid=git('rev-parse','HEAD:README.md');(self.source/'.git/objects'/oid[:2]/oid[2:]).unlink();d=self.export();v=capsule.verify(d['path']);self.assertFalse(v['completeness']['git']['complete']);self.assertFalse(v['completeness']['full_non_secret_project_complete'])
 def test_state_inside_source_refused(self):
  with self.assertRaisesRegex(capsule.CapsuleError,'outside'):capsule.export(self.source,state_dir=self.source/'state',quiesce=False)
  self.assertFalse((self.source/'state').exists())
 def test_concurrent_export_records_blocked_writer(self):
  from genesis_relay.common import lock
  with lock(self.home/'export.lock'):
   with self.assertRaises(RuntimeError):self.export()
  self.assertTrue(any(r['failures'] for r in state.status(self.home)['capsules'].values()))
 def test_recovery_checkpoint_review_and_foreign_listener_refusal(self):
  from genesis_relay.common import atomic
  (self.source/'START-LAB.sh').write_text('#!/bin/sh\necho synthetic\n');path=self.home/'source-checkpoint-synthetic.json';atomic(path,{'source_root':str(self.source),'needs_restart':True,'original_running':True,'start_helper_sha256':sha(self.source/'START-LAB.sh')})
  self.assertFalse(capsule.recover_checkpoints(self.home)['checkpoints'][0]['applied'])
  with patch.object(capsule,'_source_identity',return_value=None),patch.object(capsule,'_http_code',return_value=401),patch.object(capsule,'run') as run:
   result=capsule.recover_checkpoints(self.home,True);self.assertIn('blocked',result['checkpoints'][0]);run.assert_not_called()
 def test_recovery_checkpoint_hash_guard_and_verified_resume_fixture(self):
  from genesis_relay.common import atomic
  (self.source/'START-LAB.sh').write_text('#!/bin/sh\necho synthetic\n');path=self.home/'source-checkpoint-synthetic.json';atomic(path,{'source_root':str(self.source),'needs_restart':True,'original_running':True,'start_helper_sha256':'bad'})
  self.assertIn('blocked',capsule.recover_checkpoints(self.home,True)['checkpoints'][0]);record=load(path);record['start_helper_sha256']=sha(self.source/'START-LAB.sh');atomic(path,record)
  with patch.object(capsule,'_source_identity',side_effect=[None,{'pid':123}]),patch.object(capsule,'_http_code',side_effect=[None,401]),patch.object(capsule,'run',return_value=(0,'','')):
   self.assertTrue(capsule.recover_checkpoints(self.home,True)['checkpoints'][0]['applied'])
  self.assertFalse(load(path)['needs_restart'])
 def test_generic_json_secret_not_emitted(self):
  (self.source/'config.json').write_text(json.dumps({'db_password':'synthetic-secret-value'}));d=self.export();e=next(e for e in capsule.verify(d['path'])['manifest']['entries'] if e['path']=='config.json');self.assertEqual(e['disposition'],'EXCLUDED_WITH_REASON')
 def test_secret_in_git_commit_not_bundled(self):
  def git(*args):return subprocess.run(['git','-C',str(self.source),*args],check=True,capture_output=True,text=True)
  git('init');git('config','user.email','fixture@example.invalid');git('config','user.name','Synthetic Fixture');git('add','README.md');git('commit','-m','synthetic historical token '+'ghp_'+'A'*40);d=self.export();proof=capsule.verify(d['path']);self.assertFalse(proof['completeness']['git']['complete'])
  with zipfile.ZipFile(d['path']) as z:self.assertNotIn('history/project.bundle',z.namelist())
if __name__=='__main__':unittest.main()
