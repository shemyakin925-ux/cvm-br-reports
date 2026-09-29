#!/usr/bin/env python3
"""Download documents listed in fix_links.tsv (folder, name, link) into out/."""
import os, sys, time, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (research; personal archive)"}
EXT = {b"%PDF": ".pdf", b"PK\x03\x04": ".zip", b"<?xm": ".xml"}
ok = bad = 0
for line in open("fix_links.tsv"):
    if not line.strip():
        continue
    folder, name, link = line.rstrip("\n").split("\t")
    data = None
    for i in range(4):
        try:
            data = urllib.request.urlopen(urllib.request.Request(link, headers=UA), timeout=180).read()
            break
        except Exception:
            time.sleep(5 * (i + 1))
    if not data:
        bad += 1; print("error", link, file=sys.stderr); continue
    os.makedirs(os.path.join("out", folder), exist_ok=True)
    open(os.path.join("out", folder, name + EXT.get(data[:4], ".bin")), "wb").write(data)
    ok += 1
print(f"done fix: ok={ok} err={bad}")
