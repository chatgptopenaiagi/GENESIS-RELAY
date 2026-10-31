"""Create a reusable receiver/source kit, never a private continuation capsule."""
import hashlib,json,zipfile
from pathlib import Path
B=Path(__file__).resolve().parents[1]
def main():
 dist=B/'dist';files={}
 for name in ['README.md','THEORY.md','ARCHITECTURE.md','CAPSULE-FORMAT.md','KNOWLEDGE-HANDOFF.md','WINDOWS-RESTORATION.md','WINDOWS-NEXT-STEPS.md','RETURN-PROTOCOL.md','UI-WALKTHROUGH.md','LICENSE','pyproject.toml','MANIFEST.in']:
  files[name]=(B/name).read_bytes()
 for root in ['src/genesis_relay','windows','tests','tools','examples']:
  for p in (B/root).rglob('*'):
   if p.is_file() and '__pycache__' not in p.parts and not p.name.endswith('.pyc'):files[p.relative_to(B).as_posix()]=p.read_bytes()
 for p in dist.glob('genesis_relay-0.1.0*'):
  if p.is_file():files['packages/'+p.name]=p.read_bytes()
 files['relay.sh']=b'''#!/bin/sh\nset -eu\nrelay_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nexec "${GENESIS_RELAY_PYTHON:-python3}" -I -c 'import sys; sys.path.insert(0,sys.argv.pop(1)); from genesis_relay.cli import main; raise SystemExit(main())' "$relay_root/src" "$@"\n'''
 files['START-HERE.md']=b'''# Trusted Relay software kit\n\nThis is reusable software, not your private laboratory capsule. Keep the separate capsule ZIP and external SHA-256 reference private. Nothing is published automatically.\n\nLinux: `sh relay.sh --help` uses an existing Python 3.10+. Set GENESIS_RELAY_PYTHON to an existing absolute interpreter when needed. Alternatively install packages/*.whl into a new venv without dependencies.\n\nPowerShell 7: inspect windows/Receive-Relay.ps1 and WINDOWS-NEXT-STEPS.md. An adjacent trusted src/ tree permits isolated bootstrap with an existing Python; the capsule cannot supply this receiver code. E: is preferred only if it exists; choose an alternative explicitly.\n\nNative Windows, WSL and fresh Windows Codex execution have NOT_RUN qualification on this delivery. Linux PowerShell parsing/Inspect and relocated Linux scientific acceptance are separately scoped evidence. No ARM64 scientific environment is a Windows installation.\n\nThe operator's local FINAL-REPORT, TEST-RESULTS, capsule locations and private evidence are intentionally outside this software kit. The private capsule itself contains its project source, historical results, engineering letter and dependency requirements. See CAPSULE-FORMAT.md and RETURN-PROTOCOL.md before executing restoration or applying returned changes.\n'''
 files['SOFTWARE-SHA256SUMS.txt']=''.join(hashlib.sha256(raw).hexdigest()+'  '+name+'\n' for name,raw in sorted(files.items())).encode()
 target=dist/'genesis-relay-software-0.1.0.zip'
 with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as z:
  for name,raw in sorted(files.items()):
   info=zipfile.ZipInfo('genesis-relay-software-0.1.0/'+name);info.external_attr=(0o100755 if name=='relay.sh' else 0o100644)<<16;info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,raw)
 print(json.dumps({'kit':str(target),'size':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'files':len(files),'private_capsules_included':False}))
if __name__=='__main__':main()
