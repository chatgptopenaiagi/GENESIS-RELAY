#!/usr/bin/env python3
"""Extract a trusted, checksum-verified software distribution into a new root.

This is not the capsule reader. Never use it to bypass capsule validation.
"""
import argparse,os,tarfile,zipfile
from pathlib import Path,PurePosixPath

def main():
 p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('destination');a=p.parse_args();target=Path(a.destination).resolve()
 if target.exists() and any(target.iterdir()):raise SystemExit('Extraction destination must be new or empty')
 target.mkdir(parents=True,exist_ok=True)
 def safe(name):
  q=PurePosixPath(name)
  if q.is_absolute() or '..' in q.parts or '\\' in name or ':' in name:raise ValueError('Unsafe software distribution member')
  return q
 if a.archive.endswith('.zip'):
  with zipfile.ZipFile(a.archive) as z:
   names=z.namelist();assert len(names)==len(set(names))
   for i in z.infolist():safe(i.filename)
   z.extractall(target)
 else:
  with tarfile.open(a.archive) as t:
   names=t.getnames();assert len(names)==len(set(names))
   for m in t:
    q=safe(m.name)
    if m.issym():
     link=PurePosixPath(m.linkname)
     if link.is_absolute() or '..' in link.parts:raise ValueError('Unsafe runtime symlink')
    elif m.islnk():safe(m.linkname)
    elif not m.isdir() and not m.isfile():raise ValueError('Unsupported runtime archive member')
   t.extractall(target,**({'filter':'data'} if hasattr(tarfile,'data_filter') else {}))
 print(str(target))
if __name__=='__main__':main()
