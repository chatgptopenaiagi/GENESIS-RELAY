"""Synthetic mean experiment. Python standard library only; all data invented."""
from pathlib import Path
import argparse,csv,json,sqlite3,uuid

def compute(project):
    root=Path(project)
    with (root/'data/observations.csv').open(newline='',encoding='utf-8') as stream:
        rows=list(csv.DictReader(stream))
    values=[float(row['value']) for row in rows]
    if not values:raise ValueError('No observations')
    return {'observations':len(values),'mean':sum(values)/len(values),'expected_mean':4.0,'absolute_tolerance':1e-12,'passed':abs(sum(values)/len(values)-4.0)<=1e-12}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--project',default=str(Path(__file__).resolve().parent));args=parser.parse_args(argv)
    value=compute(args.project);print(json.dumps(value,sort_keys=True));return 0 if value['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
