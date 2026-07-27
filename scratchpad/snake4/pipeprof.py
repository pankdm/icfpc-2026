import json, os, subprocess, sys
REPO="/Users/dmitrykorolev/projects/icfpc-2026-main"
for f in sys.argv[1:]:
    r = subprocess.run(["python3", REPO+"/tools/lift.py", f, "--json"],
                       capture_output=True, text=True, cwd=REPO)
    ir = json.loads(r.stdout.strip().splitlines()[-1])
    print(os.path.basename(f), sorted(len(p.get("path") or []) for p in ir["pipes"]))
