#!/usr/bin/env python3
"""Download public release assets anonymously and test actual installed artifacts."""
from __future__ import annotations
import argparse,datetime,hashlib,json,os,platform,subprocess,sys,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',default='v0.1.0');p.add_argument('--repository',default='chatgptopenaiagi/GENESIS-RELAY');p.add_argument('--work',required=True);p.add_argument('--report',required=True);p.add_argument('--platform',choices=['windows-x86_64','linux-x86_64','linux-aarch64']);a=p.parse_args();root=Path(a.work).absolute();root.mkdir(parents=True,exist_ok=True);downloads=root/'downloads';downloads.mkdir();version=a.tag.removeprefix('v');target=a.platform or ('windows-x86_64' if os.name=='nt' else 'linux-aarch64' if platform.machine().lower() in ['aarch64','arm64'] else 'linux-x86_64');result={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_commit':os.environ.get('GITHUB_SHA'),'platform':{'system':platform.system(),'machine':platform.machine(),'python':platform.python_version()},'repository':a.repository,'tag':a.tag,'download_authentication':'NONE: urllib public HTTP, no GitHub token headers','scope':'Actual public software and synthetic demo only; no private laboratory, WSL or Codex model inference','attempt_failures':[],'passed':{},'failed':{}}
 op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 def fetch(url,target=None):
  for attempt in range(3):
   try:
    req=urllib.request.Request(url,headers={'User-Agent':'GENESIS-Relay-public-verifier/0.1.0','Accept':'application/vnd.github+json' if 'api.github.com' in url else '*/*'})
    with op.open(req,timeout=45) as r:
     if target:
      partial=target.with_suffix(target.suffix+'.partial')
      with partial.open('wb') as f:
       for block in iter(lambda:r.read(1048576),b''):f.write(block)
      os.replace(partial,target);return target
     return json.load(r)
   except (OSError,ValueError,urllib.error.URLError) as e:
    result['attempt_failures'].append({'url':url,'attempt':attempt+1,'error':type(e).__name__,'message':str(e)[:300]})
    if attempt==2:raise
    time.sleep(attempt+1)
 def check(name,fn):
  try:result['passed'][name]=fn() or True;print('PASS',name,flush=True)
  except Exception as e:result['failed'][name]=type(e).__name__+': '+str(e)[-1500:];print('FAIL',name,result['failed'][name],flush=True)
 def run(args,cwd=None):
  env=os.environ.copy()
  for k in ['PYTHONPATH','PYTHONHOME','GENESIS_RELAY_HOME']:env.pop(k,None)
  r=subprocess.run(list(map(str,args)),cwd=cwd or root,env=env,capture_output=True,text=True,timeout=240)
  if r.returncode:raise AssertionError(r.stderr[-1200:]+r.stdout[-1200:])
  return r.stdout
 release={};assets={};native_name=f'GENESIS-RELAY-{version}-{target}'+('.zip' if target.startswith('windows') else '.tar.gz');wheel_name=f'genesis_relay-{version}-py3-none-any.whl';sdist_name=f'genesis_relay-{version}.tar.gz';demo_name=f'GENESIS-RELAY-{version}-demo-capsule.zip'
 def metadata():
  nonlocal release,assets
  repo=fetch('https://api.github.com/repos/'+a.repository);assert repo['private'] is False
  release=fetch('https://api.github.com/repos/'+a.repository+'/releases/tags/'+urllib.parse.quote(a.tag,safe=''));assert release['tag_name']==a.tag and release['prerelease'] and not release['draft'];assets={x['name']:x for x in release['assets']};required=[native_name,wheel_name,sdist_name,demo_name,'RELEASE-MANIFEST.json','SHA256SUMS.txt']
  for n in required:assert n in assets,n;fetch(assets[n]['browser_download_url'],downloads/n);assert (downloads/n).stat().st_size==assets[n]['size']
  return {'public':True,'prerelease':True,'release_url':release['html_url'],'assets_received':required}
 check('anonymous_public_metadata_and_downloads',metadata)
 def integrity():
  sums={line.split('  ',1)[1]:line.split('  ',1)[0] for line in (downloads/'SHA256SUMS.txt').read_text().splitlines() if line.strip()};verified=[]
  for f in downloads.iterdir():
   if f.name=='SHA256SUMS.txt':continue
   assert f.name in sums,'Downloaded asset missing external checksum: '+f.name;assert sha(f)==sums[f.name],f.name;verified.append({'name':f.name,'bytes':f.stat().st_size,'sha256':sha(f)})
  manifest=json.loads((downloads/'RELEASE-MANIFEST.json').read_text());commit=manifest['source_commit'];ref=fetch('https://api.github.com/repos/'+a.repository+'/git/ref/tags/'+urllib.parse.quote(a.tag,safe=''));obj=ref['object']
  if obj['type']=='tag':obj=fetch(obj['url'])['object']
  assert obj['type']=='commit' and obj['sha']==commit,'Public tag target differs from frozen source commit';result['release_source_commit']=commit
  return {'assets':verified,'annotated_tag_source_commit':commit,'hashes_are_integrity_not_authenticity':True}
 if not result['failed']:check('published_sizes_hashes_and_tag',integrity)
 def native():
  extracted=root/'native';run([sys.executable,BASE/'tools/extract_distribution.py',downloads/native_name,extracted]);bundle=extracted/f'GENESIS-RELAY-{version}-{target}';exe=bundle/('Genesis-Relay.exe' if os.name=='nt' else 'Genesis-Relay');exe=exe if exe.exists() else bundle/'relay';assert exe.is_file()
  report=root/'native-acceptance.json';run([sys.executable,BASE/'tools/ci_acceptance.py','--phase','standalone','--work',root/'native-acceptance','--executable',exe,'--report',report]);data=json.loads(report.read_text());assert data['status']=='PASSED';return {'executable':str(exe),'download_sha256':sha(downloads/native_name),'native_acceptance':data,'downloaded_demo_verified':json.loads(run([exe,'verify',downloads/demo_name,'--summary']))['verified']}
 if not result['failed']:check('downloaded_native_distribution_acceptance',native)
 def wheel():
  venv=root/'wheel-venv';run([sys.executable,'-m','venv',venv]);bin_dir=venv/('Scripts' if os.name=='nt' else 'bin');python=bin_dir/('python.exe' if os.name=='nt' else 'python');run([python,'-I','-m','pip','install','--no-index','--no-deps',downloads/wheel_name]);module=run([python,'-I','-c','import genesis_relay;print(genesis_relay.__file__)']).strip();assert str(venv) in module and 'site-packages' in module
  report=root/'wheel-acceptance.json';run([sys.executable,BASE/'tools/ci_acceptance.py','--phase','standalone','--work',root/'wheel-acceptance','--python',python,'--report',report]);accepted=json.loads(report.read_text());assert accepted['status']=='PASSED';return {'installed_python':str(python),'installed_module':module,'acceptance':accepted}
 if not result['failed']:check('downloaded_wheel_clean_install_acceptance',wheel)
 result['status']='PASSED' if not result['failed'] else 'FAILED';result['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();report=Path(a.report);report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'passed':len(result['passed']),'failed':len(result['failed'])}),flush=True);return bool(result['failed'])
if __name__=='__main__':raise SystemExit(main())
