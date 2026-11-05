#!/bin/bash
# The files of live-spec.html's collection in a live-spec checkout, one per
# line, as that checkout's own tool derives them (lspec show --graph): what the
# sandbox binds, so a split in the methodology never leaves a referent behind
# (watch-nobackground). Usage: methodology-files.sh LSPEC_SRC
set -euo pipefail
SRC=${1:?usage: methodology-files.sh LSPEC_SRC}
cd "$SRC"
python3 lspec.py --main live-spec.html show --graph | awk '
  /^collection:/ {on=1; next}
  on && /^  [^ ].*\.html/ {print $1; next}
  on && /^  depends-on edges/ {exit}'
