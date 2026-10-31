"""Measured synthetic resource test; never a private project export."""
import json,os,resource,tempfile,time
from pathlib import Path
from genesis_relay.capsule import export,verify
with tempfile.TemporaryDirectory(prefix='relay-memory-') as folder:
 root=Path(folder);project=root/'project';project.mkdir();block=os.urandom(65536)
 with (project/'synthetic.bin').open('wb') as f:
  for _ in range(128):f.write(block)
 start=time.monotonic();out=export(project,state_dir=root/'state',quiesce=False);proof=verify(out['path']);result={'scope':'Synthetic 8 MiB streaming export+verify, not another private Science Lab capture.','bytes_source':8*1024**2,'seconds':round(time.monotonic()-start,3),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'verified':proof['verified'],'status':'PASSED'};print(json.dumps(result));assert result['peak_rss_kib']<256*1024
