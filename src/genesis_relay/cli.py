"""Private Linux sender CLI; no AI service required for archive mechanics."""
import argparse,json,sys
from pathlib import Path
from . import __version__,capsule,discovery,state

def main(argv=None):
 argv=list(sys.argv[1:] if argv is None else argv)
 if argv[:1]==['_module']:
  import importlib
  if len(argv)<2 or argv[1] not in {'genesis_relay.ui','genesis_relay.receive_cli'}:raise SystemExit('Unsupported internal Relay module')
  return importlib.import_module(argv[1]).main(argv[2:])
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--version',action='version',version='GENESIS Relay '+__version__);p.add_argument('--state-dir');s=p.add_subparsers(dest='command',required=True)
 for command in ['discover','plan','export']:
  q=s.add_parser(command);q.add_argument('source');q.add_argument('--mode',choices=['full','lightweight','offline-ready'],default='full');q.add_argument('--sentinel')
  if command=='export':q.add_argument('--output');q.add_argument('--no-quiesce',action='store_true')
 for command in ['inspect','verify']:
  q=s.add_parser(command);q.add_argument('capsule');q.add_argument('--summary',action='store_true')
 s.add_parser('status')
 q=s.add_parser('recover');q.add_argument('--apply',action='store_true')
 q=s.add_parser('ui');q.add_argument('operation',choices=['start','stop','status','access','restart']);q.add_argument('--source');q.add_argument('--port',type=int)
 q=s.add_parser('restore');q.add_argument('capsule');q.add_argument('--destination',required=True);q.add_argument('--route',choices=['LOCAL_LINUX','NATIVE_WINDOWS_X64','WSL_LINUX_X64'],default='LOCAL_LINUX');q.add_argument('--python');q.add_argument('--apply',action='store_true')
 q=s.add_parser('adapt');q.add_argument('receipt');q.add_argument('--python',required=True);q.add_argument('--route',default='LOCAL_LINUX');q.add_argument('--apply',action='store_true')
 q=s.add_parser('accept');q.add_argument('receipt');q.add_argument('--apply',action='store_true')
 q=s.add_parser('return');q.add_argument('receipt');q.add_argument('--output',required=True)
 q=s.add_parser('demo',help='Create and exercise the bundled synthetic laboratory');q.add_argument('arguments',nargs=argparse.REMAINDER)
 q=s.add_parser('receive',help='Trusted receiver and selected-return operations');q.add_argument('arguments',nargs=argparse.REMAINDER)
 q=s.add_parser('sign');q.add_argument('capsule');q.add_argument('--key',required=True)
 a=p.parse_args(argv)
 try:
  if a.command=='discover':value=discovery.discover(a.source,mode=a.mode)
  elif a.command=='plan':value=capsule.plan(a.source,mode=a.mode,sentinel_root=a.sentinel)
  elif a.command=='export':value=capsule.export(a.source,a.output,state_dir=a.state_dir,mode=a.mode,sentinel_root=a.sentinel,quiesce=not a.no_quiesce)
  elif a.command in ['inspect','verify']:
   value=capsule.verify(a.capsule)
   if a.summary:value={k:value[k] for k in ['capsule','completeness','archive_sha256','verified','members','expanded_bytes']};value['capsule']={k:v for k,v in value['capsule'].items() if k!='payloads'}
  elif a.command=='status':value=state.status(a.state_dir)
  elif a.command=='recover':value=capsule.recover_checkpoints(a.state_dir,a.apply)
  elif a.command=='demo':
   from . import demo
   return demo.main(a.arguments,state_dir=a.state_dir)
  elif a.command=='receive':
   from .receive_cli import main as receive_main
   return receive_main(a.arguments)
  elif a.command=='ui':
   from .ui import main as ui_main
   return ui_main([a.operation,'--state-dir',str(state.state_dir(a.state_dir))]+(['--source',a.source] if a.source else [])+(['--port',str(a.port)] if a.port else []))
  elif a.command=='restore':
   from . import receiver
   value=receiver.restore(a.capsule,a.destination,a.route,a.python) if a.apply else receiver.plan(a.capsule,a.destination,a.route,a.python)
  elif a.command=='adapt':
   if not a.apply:raise ValueError('Adapt requires --apply after inspecting the restoration plan')
   from . import receiver,laboratory
   receipt=receiver.read(a.receipt);value=laboratory.adapt_project(receipt['project_path'],a.python,a.route,receipt['capsule_id'],receipt['archive_sha256'])
   if value.get('status')=='ADAPTED':receiver.record_adaptation(receipt,value)
  elif a.command=='accept':
   if not a.apply:raise ValueError('Acceptance executes scientific source; explicit --apply is required')
   from . import receiver,laboratory
   receipt=receiver.read(a.receipt);result=laboratory.acceptance(receipt['project_path'],a.receipt);sealed=receiver.record_acceptance(a.receipt,result);value={'acceptance':result,'receiver_state':sealed['state'],'ready_to_continue':sealed.get('ready_to_continue',False),'readiness_scope':sealed.get('readiness_scope')}
  elif a.command=='return':
   from .returns import create_return
   value=create_return(a.receipt,a.output)
  else:
   import shutil
   from .common import run
   tool=shutil.which('gpg')
   if not tool:raise ValueError('No existing GPG signer is available; signing is optional')
   capsule.verify(a.capsule);target=str(Path(a.capsule).absolute())+'.asc';code,out,err=run([tool,'--armor','--local-user',a.key,'--output',target,'--detach-sign',str(Path(a.capsule).absolute())],timeout=90)
   if code:raise ValueError('Existing GPG signing failed; no keys were generated')
   value={'signature':target,'scope':'External detached GPG signature; verify against a separately trusted signer key.'}
  print(json.dumps(value,indent=2,ensure_ascii=True));return 0
 except Exception as e:print(json.dumps({'status':'FAILED','type':type(e).__name__,'error':str(e)[:1500]}),file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
