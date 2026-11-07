#!/bin/bash
# The files of live-spec.html's collection in a live-spec checkout, one per
# line, as that checkout's own tool derives them (lspec show --graph): what the
# sandbox binds, so a split in the methodology never leaves a referent behind
# (watch-nobackground). A file whose split row declares an import from this
# repository is a copy of this spec and is left out,
# so the cells under test never read the harness or the rubric that scores
# them (dl-island). Usage: methodology-files.sh LSPEC_SRC
set -euo pipefail
SRC=${1:?usage: methodology-files.sh LSPEC_SRC}
cd "$SRC"
python3 lspec.py --main live-spec.html show --graph | python3 -c '
import re, sys
main = open("live-spec.html", encoding="utf-8").read()
def from_bench(rid):
    m = re.search(r"<tr id=\"%s\".*?</tr>" % re.escape(rid), main, re.S)
    return bool(m and re.search(r"<code data-import>\S*/live-spec-bench(\.git)?/? @", m.group(0)))
on = False
for line in sys.stdin:
    if line.startswith("collection:"):
        on = True
        continue
    if not on:
        continue
    if line.startswith("  depends-on edges"):
        break
    m = re.match(r"  (\S+\.html)(?:\s+<- \S+ \((\S+)\))?", line)
    if m and not (m.group(2) and from_bench(m.group(2))):
        print(m.group(1))
'
