#!/usr/bin/env python3
"""Committed .man files with no matching archive in submitted/ (by content hash)."""
import hashlib, os, subprocess, sys
SLUGS = sys.argv[1:] or ["tcp","sudoku-validity","subset-sum","sort","snake"]
ROOT="/Users/visenbaev/icfpc26"
def h(b): return hashlib.sha1(b.strip()).hexdigest()
sub={}
for s in SLUGS:
    d=os.path.join(ROOT,"submitted",s if s!="sudoku-validity" else "sudoku-validity")
    if not os.path.isdir(d):
        for alt in os.listdir(os.path.join(ROOT,"submitted")):
            if alt.replace("-","").startswith(s.replace("-","")[:6]): d=os.path.join(ROOT,"submitted",alt)
    if os.path.isdir(d):
        for f in os.listdir(d):
            if f.endswith(".man"):
                sub.setdefault(s,set()).add(h(open(os.path.join(d,f),"rb").read()))
files=subprocess.run(["git","log","--all","--since=6 hours ago","--name-only",
                      "--diff-filter=AM","--pretty=format:"],cwd=ROOT,
                     capture_output=True,text=True).stdout.split("\n")
seen=set()
for p in files:
    p=p.strip()
    if not p.endswith(".man") or "scratchpad" in p or p in seen: continue
    seen.add(p)
    parts=p.split("/")
    if len(parts)<3 or parts[0]!="solutions": continue
    slug=parts[1]
    if slug not in SLUGS: continue
    full=os.path.join(ROOT,p)
    if not os.path.exists(full):
        blob=subprocess.run(["git","log","--all","--format=%H","-1","--",p],cwd=ROOT,
                            capture_output=True,text=True).stdout.strip()
        if not blob: continue
        data=subprocess.run(["git","show",f"{blob}:{p}"],cwd=ROOT,
                            capture_output=True).stdout
    else:
        data=open(full,"rb").read()
    if not data: continue
    if h(data) in sub.get(slug,()): continue
    rows=[r.rstrip() for r in data.decode(errors="replace").split("\n")]
    while rows and not rows[-1]: rows.pop()
    if not rows: continue
    w=max(len(r) for r in rows); ht=len(rows)
    print(f"{slug:18s} box={max(w,ht)**2:7d} {w}x{ht}  {p}")
