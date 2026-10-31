"""Trusted receiver command bridge used by PowerShell; never loaded from a capsule."""
import argparse,json,sys
from pathlib import Path
from . import receiver,returns

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['Inspect','Plan','Restore','Verify','Open','LaunchCodex','Info','Return','ReturnInspect','ReturnPreview','ReturnApply','ReturnRollback']);p.add_argument('--capsule');p.add_argument('--destination-root');p.add_argument('--receipt');p.add_argument('--route',default='NATIVE_WINDOWS_X64',choices=['LOCAL_LINUX','NATIVE_WINDOWS_X64','WSL_LINUX_X64']);p.add_argument('--python');p.add_argument('--output');p.add_argument('--return-capsule');p.add_argument('--project');p.add_argument('--plan');p.add_argument('--selected',action='append');p.add_argument('--apply',action='store_true');a=p.parse_args(argv)
 try:
  if a.operation=='Inspect':value=receiver.inspect(a.capsule)
  elif a.operation=='Plan':value=receiver.plan(a.capsule,a.destination_root,a.route,a.python)
  elif a.operation=='Restore':
   if not a.apply:raise ValueError('Restore requires explicit --apply after plan review')
   value=receiver.restore(a.capsule,a.destination_root,a.route,a.python)
  elif a.operation=='Verify':value=receiver.verify_restoration(a.receipt)
  elif a.operation=='Info':
   value=receiver.read(a.receipt)
   if not Path(value['project_path']).is_dir():raise ValueError('Receipt workspace does not exist')
  elif a.operation=='Open':value=receiver.open_project(a.receipt)
  elif a.operation=='LaunchCodex':
   if not a.apply:raise ValueError('LaunchCodex requires explicit --apply')
   return receiver.launch_codex(a.receipt)
  elif a.operation=='Return':
   if not a.apply:raise ValueError('Return creation requires explicit --apply')
   value=returns.create_return(a.receipt,a.output)
  elif a.operation=='ReturnInspect':value=returns.verify_return(a.return_capsule)
  elif a.operation=='ReturnPreview':
   value=returns.preview_return(a.return_capsule,a.project)
   if a.output:receiver.atomic(a.output,value)
  elif a.operation=='ReturnApply':
   if not a.apply:raise ValueError('ReturnApply requires explicit --apply and selected paths')
   if not a.selected:raise ValueError('Select at least one previewed path with --selected')
   value=returns.apply_return(a.plan,a.selected)
  else:
   if not a.apply:raise ValueError('ReturnRollback requires explicit --apply')
   value=returns.rollback_return(a.receipt)
  print(json.dumps(value,indent=2,ensure_ascii=False));return 0
 except Exception as error:
  print(json.dumps({'status':'FAILED','error':type(error).__name__,'message':str(error)[:1000]},ensure_ascii=False),file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
