#!/usr/bin/env python3
"""Run the public synthetic regression suite and preserve exact counts/skips."""
import argparse,datetime,json,os,platform,sys,unittest
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();base=Path(__file__).resolve().parents[1];sys.path.insert(0,str(base/'src'));suite=unittest.defaultTestLoader.discover(str(base/'tests'));r=unittest.TextTestRunner(verbosity=2).run(suite);out={'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_commit':os.environ.get('GITHUB_SHA'),'platform':{'system':platform.system(),'machine':platform.machine(),'python':platform.python_version()},'scope':'Current public synthetic source regression suite; native installed-artifact acceptance is separate.','tests_run':r.testsRun,'passed':r.testsRun-len(r.failures)-len(r.errors)-len(r.skipped),'failed':len(r.failures),'errors':len(r.errors),'skipped':[{'test':str(t),'reason':why} for t,why in r.skipped],'status':'PASSED' if r.wasSuccessful() else 'FAILED'};path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(out,indent=2)+'\n');return not r.wasSuccessful()
if __name__=='__main__':raise SystemExit(main())
