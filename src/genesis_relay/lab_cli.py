"""Trusted destination laboratory controls; never infer ownership from a port."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
if __package__ in [None,'']:
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from genesis_relay import laboratory as lab
else:
    from . import laboratory as lab

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['start','stop','restart','status','access']);parser.add_argument('--project',required=True);args=parser.parse_args(argv)
    try:
        if args.command=='start':result=lab.start(args.project)
        elif args.command=='stop':result=lab.stop(args.project)
        elif args.command=='restart':lab.stop(args.project);result=lab.start(args.project)
        elif args.command=='status':result=lab.status(args.project)
        else:
            if not sys.stdout.isatty():raise RuntimeError('Access helper requires an operator terminal; credentials are not written into general logs.')
            result=lab.status(args.project)
            if result['status']!='RUNNING':raise RuntimeError('Owned destination laboratory is not running; use START-LAB.sh first.')
            project=lab.project_root(args.project);credentials=lab.load(project/'private/access.json')
            if not credentials.get('username') or not credentials.get('password'):raise RuntimeError('Destination-local credentials are unavailable.')
            print(result['url']+'\nUsername: '+credentials['username']+'\nPassword: '+credentials['password']);return 0
        print(json.dumps(result,indent=2));return 0
    except (OSError,ValueError,RuntimeError,KeyError) as error:
        print('Relay laboratory: '+str(error),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
