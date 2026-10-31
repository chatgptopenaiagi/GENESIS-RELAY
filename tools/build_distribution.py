#!/usr/bin/env python3
"""Build an accurately labelled native bundle or Python-required Linux archive."""
from __future__ import annotations
import argparse,hashlib,json,os,platform,shutil,subprocess,sys,tarfile,tempfile,zipfile
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
VERSION='0.1.0'
DOCS=['README.md','QUICKSTART.md','INSTALL-WINDOWS.md','INSTALL-LINUX.md','KNOWN-LIMITATIONS.md','THEORY.md','ARCHITECTURE.md','CAPSULE-FORMAT.md','RETURN-PROTOCOL.md','KNOWLEDGE-HANDOFF.md','LICENSE']
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kind',choices=['frozen','python-launcher'],required=True);p.add_argument('--output',default='dist');a=p.parse_args();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
 arch=platform.machine().lower();arch='x86_64' if arch in ['amd64','x64'] else 'aarch64' if arch in ['arm64'] else arch
 system='windows' if os.name=='nt' else 'linux';name=f'GENESIS-RELAY-{VERSION}-{system}-{arch}'
 if system=='windows' and arch!='x86_64':raise SystemExit('This builder qualifies only actual Windows x86_64.')
 if a.kind=='python-launcher' and system!='linux':raise SystemExit('Python launcher archive builder is Linux-only.')
 with tempfile.TemporaryDirectory(prefix='relay-native-build-') as tmp:
  tmp=Path(tmp);bundle=tmp/name
  if a.kind=='frozen':
   subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--name','Genesis-Relay','--distpath',str(tmp/'native'),'--workpath',str(tmp/'work'),'--specpath',str(tmp/'spec'),'--paths',str(BASE/'src'),'--collect-all','genesis_relay','--copy-metadata','genesis-relay',str(BASE/'tools/frozen_entry.py')],check=True)
   shutil.move(str(tmp/'native/Genesis-Relay'),bundle)
  else:
   bundle.mkdir();shutil.copytree(BASE/'src/genesis_relay',bundle/'src/genesis_relay',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
   (bundle/'relay').write_text('#!/bin/sh\nset -eu\nrelay_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nexec "${GENESIS_RELAY_PYTHON:-python3}" -I -c \'import sys;sys.path.insert(0,sys.argv.pop(1));from genesis_relay.cli import main;raise SystemExit(main())\' "$relay_root/src" "$@"\n');(bundle/'relay').chmod(0o755)
  for n in DOCS:
   if (BASE/n).is_file():shutil.copy2(BASE/n,bundle/n)
  shutil.copytree(BASE/'windows',bundle/'windows')
  if system=='windows':
   for n in ['Receive-Relay.ps1','Launch-Relay.ps1']:shutil.copy2(BASE/'windows'/n,bundle/n)
  meta={'application_version':VERSION,'capsule_format':'genesis-relay/1.0','build_platform':platform.platform(),'machine':platform.machine(),'architecture':arch,'python':platform.python_version(),'libc':platform.libc_ver(),'kind':a.kind,'contains_python_runtime':a.kind=='frozen','external_runtime_requirement':'None for Relay itself; exported project dependencies are separate.' if a.kind=='frozen' else 'Existing compatible Python 3.10+; this is a shell launcher, not a bundled runtime.','source_commit':os.environ.get('GITHUB_SHA') or subprocess.check_output(['git','-C',str(BASE),'rev-parse','HEAD'],text=True).strip(),'qualification':'Build identity only; native execution acceptance is recorded separately.'}
  (bundle/'BUILD-INFO.json').write_text(json.dumps(meta,indent=2)+'\n')
  if system=='windows':
   target=out/(name+'.zip')
   with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for f in sorted(bundle.rglob('*')):
     if f.is_file():z.write(f,str(f.relative_to(tmp)).replace('\\','/'))
  else:
   target=out/(name+'.tar.gz')
   with tarfile.open(target,'w:gz') as tar:tar.add(bundle,arcname=name)
 result={'path':str(target),'bytes':target.stat().st_size,'sha256':digest(target),'build':meta};(out/(name+'-build.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
