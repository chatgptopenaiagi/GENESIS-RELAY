"""Small portable primitives: canonical JSON, streaming hashes, atomic files, locks."""
import contextlib,datetime,hashlib,json,os,subprocess,tempfile,time
from pathlib import Path

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def canonical(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('utf-8')
def load(path,default=None):
 try:return json.loads(Path(path).read_text(encoding='utf-8'))
 except (OSError,ValueError):return default

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);raw=value if isinstance(value,bytes) else value.encode('utf-8') if isinstance(value,str) else canonical(value)
 fd,name=tempfile.mkstemp(prefix='.'+path.name+'-',suffix='.partial',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)
@contextlib.contextmanager
def lock(path,timeout=10):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('a+b') as f:
  if f.tell()==0:f.write(b'0');f.flush()
  f.seek(0);end=time.monotonic()+timeout
  while True:
   try:
    if os.name=='nt':
     import msvcrt;msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
    else:
     import fcntl;fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
    break
   except (OSError,BlockingIOError):
    if time.monotonic()>end:raise RuntimeError('Another Relay writer owns this operation')
    time.sleep(.05)
  try:yield
  finally:
   if os.name=='nt':
    import msvcrt;f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
   else:
    import fcntl;fcntl.flock(f,fcntl.LOCK_UN)

def run(argv,timeout=30,cwd=None,env=None):
 with tempfile.TemporaryFile() as out,tempfile.TemporaryFile() as err:
  p=subprocess.Popen([str(x) for x in argv],stdout=out,stderr=err,cwd=cwd,env=env)
  try:p.wait(timeout=timeout)
  except subprocess.TimeoutExpired:p.kill();p.wait();raise RuntimeError('Bounded command timed out: '+Path(str(argv[0])).name)
  out.seek(0);err.seek(0);a=out.read(16000001);b=err.read(1000001)
  if len(a)>16000000:raise RuntimeError('Command output exceeded finite cap')
  return p.returncode,a.decode(errors='replace'),b.decode(errors='replace')

def module_command(module,*arguments):
 """Launch only a trusted Relay module, including runtime-inclusive builds.

 Frozen sys.executable is Relay, not a general Python interpreter. Source and
 wheel children ignore ambient PYTHONPATH/PYTHONHOME and untrusted working dirs.
 """
 import sys
 allowed={'genesis_relay.ui','genesis_relay.receive_cli'}
 if module not in allowed:raise ValueError('Unsupported internal Relay module')
 if getattr(sys,'frozen',False):return [sys.executable,'_module',module,*map(str,arguments)]
 bootstrap='import sys,importlib;sys.path.insert(0,sys.argv.pop(1));name=sys.argv.pop(1);raise SystemExit(importlib.import_module(name).main())'
 return [sys.executable,'-I','-c',bootstrap,str(Path(__file__).resolve().parent.parent),module,*map(str,arguments)]
