#!/bin/bash
# driver.sh — the bench deck driver: generates the deck from briefs.py, routes
# briefs by the registry, stages material, resumes, classifies completion.
# Replaces the per-run hand-driven steps whose defects are recorded in the
# bench spec (diag-staging, watch-prestaged, watch-partial, watch-rc).
# Phases: setup | inst | deck | probe | all (default) | score | score-blind.
# BENCH_PROCEDURE=outcome (default) runs the twelve-cell two-arm deck; =probe
# runs the six method cells through the planted-defect probe (dl-probe).
# Method cells carry lspec and hooks, baseline cells a NOTES.md brief and no
# tool; held-out slots run only under BENCH_HELDOUT=1 (dl-heldout). Resumable:
# a session whose transcript ends in a final text part and whose end-of-session
# HEAD stamp exists is never re-run; an incomplete transcript is quarantined to
# *.partial (dl-completion).
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
EV=${BENCH_EV:?set BENCH_EV to the evidence dir for this run}
SRC=${LSPEC_SRC:?set LSPEC_SRC to the live-spec checkout under test (dl-artifact)}
if [ -n "$(git -C "$SRC" status --porcelain)" ]; then
  echo "driver.sh: LSPEC_SRC ($SRC) has uncommitted changes; a run's basis is a commit, and the tool and" \
       "files copied from the working tree must be that commit's (dl-artifact)" >&2
  exit 2
fi
PHASE=${1:-all}
# outcome (default): twelve cells, two arms, the operating deck (dl-baseline).
# probe: six method cells, P1/P2 planted-defect slots (dl-probe).
PROCEDURE=${BENCH_PROCEDURE:-outcome}
mkdir -p "$EV/transcripts" "$EV/metrics" "$EV/logs"
export BENCH_EV=$EV

# arms this procedure instantiates and drives; a probe has no baseline to
# plant a spec defect in (dl-probe)
arms() { if [ "$PROCEDURE" = probe ]; then echo method; else echo "method baseline"; fi; }

# watch-nobus: setup and scoring need no inhibitor (they start no session);
# a session batch does, and a full run keeps watch-suspend's protection: if the
# inhibitor is installed but cannot start, say so and stop before any session.
case "$PHASE" in
  inst|deck|probe|all)
    if [ -z "${LSPEC_BENCH_INHIBITED:-}" ] && command -v systemd-inhibit >/dev/null; then
      if ! systemd-inhibit --what=idle true 2>/dev/null; then
        echo "driver.sh: systemd-inhibit is installed but could not start (no bus?);" \
             "no session ran. Set LSPEC_BENCH_INHIBITED=1 to run without the suspend guard (watch-suspend)." >&2
        exit 2
      fi
      export LSPEC_BENCH_INHIBITED=1
      exec systemd-inhibit --what=idle "$0" "$PHASE"
    fi
    ;;
esac

log() { echo "$1 $(date -Is)" >> "$EV/driver-progress.log"; }

# session done (dl-completion; watch-rc: exit codes advisory; watch-tdone):
# one implementation, briefs.py session_done — final text part AND the
# runner's end-of-session HEAD stamp (metrics/NAME.head from run_session.sh)
tdone() { python3 "$HERE/briefs.py" done "$EV" "$1"; }

sess() {  # sess CELL PROFILE BRIEF TAG
  local cell=$1 profile=$2 brief=$3 tag=$4
  if tdone "$cell-$tag"; then log "$cell $tag skipped (done)"; return 0; fi
  local t="$EV/transcripts/$cell-$tag.jsonl"
  [ -f "$t" ] && mv "$t" "$t.partial"
  # < /dev/null: a session must not inherit (and consume) the dispatch loop's
  # herestring stdin, or read hits EOF and the deck ends early (watch-stdineat)
  "$HERE/run_session.sh" "$EV/cells/$cell" "$profile" "$brief" "$tag" < /dev/null > "$EV/logs/$cell.$tag.out" 2>&1
  log "$cell $tag rc=$?"
}

# fail-closed staging: abort the whole driver if the material is not where the
# brief's premise puts it (diag-staging; never in a launch preamble)
stage_rebuild_notes() {  # $1 = ae86 cell repo
  local repo=$1
  if [ ! -f "$repo/rebuild-notes/torque-sequence.md" ]; then
    rm -rf "$repo/rebuild-notes"
    cp -r "$HERE/staging/rebuild-notes" "$repo/rebuild-notes"
  fi
  for f in torque-sequence.md wiring-conversion.md coolant-routing.md; do
    [ -f "$repo/rebuild-notes/$f" ] || { log "FATAL staging $repo missing rebuild-notes/$f"; exit 1; }
  done
}

stage_o4_edit() {  # $1 = cell repo, $2 = subject; verified in place, aborts on failure
  local repo=$1 subject=$2
  if [ "$subject" = ae86 ]; then
    grep -qs "unsourced" "$repo/calc/fitment.py" && return 0   # already reverted by a session
    sed -i 's/^OIL_PAN_DEPTH_MM = 180.0/OIL_PAN_DEPTH_MM = 172.0/' "$repo/calc/fitment.py"
    grep -qs "^OIL_PAN_DEPTH_MM = 172.0" "$repo/calc/fitment.py" || { log "FATAL O4 staging failed $repo"; exit 1; }
  else
    grep -qs "^NIGHT_MULT = 1.30" "$repo/factorytax/shifts.py" && return 0
    sed -i 's/^NIGHT_MULT = 1.25/NIGHT_MULT = 1.30/' "$repo/factorytax/shifts.py"
    grep -qs "^NIGHT_MULT = 1.30" "$repo/factorytax/shifts.py" || { log "FATAL O4 staging failed $repo"; exit 1; }
  fi
  log "$(basename "$repo") O4edit staged: $(git -C "$repo" status --porcelain | grep -E 'fitment|shifts' | tr '\n' ' ')"
}

# cell naming (dl-baseline): method cells S-N, baseline cells S-base-N; the
# arm of a cell is read back from its name by arm_of
arm_of() { case "$1" in *-base-*) echo baseline ;; *) echo method ;; esac; }
cells_of() { echo "$1-$2"; }   # cells_of SUBJECT N -> method cell name
base_cell() { echo "$1-base-$2"; }

# dl-adopt: a method cell whose previous brief left an lspec request open is
# adopted by the next brief, as the operator's standing say-so
adopt_if_open() {  # adopt_if_open CELL REPO TAG
  local cell=$1 repo=$2 tag=$3
  if [ "$(arm_of "$cell")" = method ] && [ -f "$(git -C "$repo" rev-parse --absolute-git-dir)/lspec/request.json" ]; then
    (cd "$repo" && python3 lspec.py start --adopt --reason "deck brief $tag per dl-adopt" >> "$EV/logs/$cell.adopt.log" 2>&1) \
      && log "$cell $tag adopted the open request" \
      || log "$cell $tag adopt not needed or refused (see logs)"
  fi
}

setup() {
  local S N CELL HOOKDIR H ARM BASE
  mkdir -p "$EV/subjects" "$EV/cells"
  python3 "$HERE/briefs.py" emit-all "$EV/briefs" || { log "FATAL brief generation failed"; exit 1; }
  for S in ae86 factorytax; do
    for ARM in $(arms); do
      BASE="$EV/subjects/$S-base"; [ "$ARM" = baseline ] && BASE="$EV/subjects/$S-base-baseline"
      if [ ! -d "$BASE" ]; then
        cp -a "$HERE/subjects/$S" "$BASE"
        rm -rf "$BASE"/factorytax/__pycache__ "$BASE"/factorytax/tests/__pycache__
        git -C "$BASE" init -q
        if [ "$ARM" = method ]; then   # the tool rides only in the method arm (dl-baseline)
          cp "$SRC/lspec.py" "$BASE/"
          cp -r "$SRC/hooks" "$BASE/"
          [ ! -d "$SRC/models" ] || cp -r "$SRC/models" "$BASE/"   # find's model, on a basis that carries one
        fi
        git -C "$BASE" add -A
        git -C "$BASE" -c user.email=bench@local -c user.name=bench \
          commit -qm "baseline: subject ($ARM arm) @ $(git -C "$SRC" rev-parse --short HEAD)"
        log "staged subject $(basename "$BASE")"
      fi
      for N in 1 2 3; do
        CELL=$(cells_of "$S" "$N"); [ "$ARM" = baseline ] && CELL=$(base_cell "$S" "$N")
        if [ ! -d "$EV/cells/$CELL" ]; then
          git -C "$BASE" clone -q --no-hardlinks "$BASE" "$EV/cells/$CELL"
          HOOKDIR=$(git -C "$EV/cells/$CELL" rev-parse --path-format=absolute --git-path hooks)
          rm -f "$HOOKDIR"/*.sample
          if [ "$ARM" = method ]; then   # enforced: hooks installed in every method cell
            for H in commit-msg post-commit pre-commit prepare-commit-msg; do
              ln -sf "../../hooks/$H" "$HOOKDIR/$H"
            done
          fi
          log "staged cell $CELL ($ARM)"
        fi
      done
    done
  done
}

inst() {
  local N S ARM CELL PLAN TAG FILE HOOK COND
  for N in 1 2 3; do
    for S in ae86 factorytax; do
      for ARM in $(arms); do
        CELL=$(cells_of "$S" "$N"); [ "$ARM" = baseline ] && CELL=$(base_cell "$S" "$N")
        PLAN=$(python3 "$HERE/briefs.py" plan "$S" inst "$ARM") || { log "FATAL brief plan $S inst $ARM"; exit 1; }
        IFS=$'\t' read -r TAG FILE HOOK COND <<< "$PLAN"
        sess "$CELL" inst "$EV/briefs/$FILE" "$TAG" &
      done
    done
    wait
  done
}

# dispatch one slot from the registry plan: conditional skip, fail-closed
# staging hook in the slot's own step (diag-staging), then the session
dispatch() {  # dispatch CELL SUBJECT REPO WIRED LINE
  local cell=$1 subject=$2 repo=$3 wired=$4 line=$5
  local TAG FILE HOOK COND
  IFS=$'\t' read -r TAG FILE HOOK COND <<< "$line"
  if [ "$COND" = w1 ] && [ "$wired" = 1 ]; then
    log "$cell $TAG skipped (depends-on present at seed)"
    return 0
  fi
  if [ "$COND" = heldout ] && [ -z "${BENCH_HELDOUT:-}" ]; then
    log "$cell $TAG skipped (held out: BENCH_HELDOUT unset, dl-heldout)"
    return 0
  fi
  # open-requests policy (dl-adopt): a method cell whose previous brief left an
  # lspec request open is adopted by the next brief, as the operator's say-so
  adopt_if_open "$cell" "$repo" "$TAG"
  case "$HOOK" in
    none) ;;
    rebuild_notes) stage_rebuild_notes "$repo" ;;
    o4_edit)       stage_o4_edit "$repo" "$subject" ;;
    *) log "FATAL unknown stage hook $HOOK"; exit 1 ;;
  esac
  sess "$cell" oper "$EV/briefs/$FILE" "$TAG"
}

deck() {  # one cell's full operating deck, ordered and routed by the registry
  local cell=$1 subject=$2
  local repo="$EV/cells/$cell" arm
  arm=$(arm_of "$cell")
  local wired line PLAN   # wired evaluated on the seed, before any deck session (dl-w1)
  wired=$(python3 "$HERE/briefs.py" wired "$repo") || wired=0
  [ "$wired" = 1 ] || wired=0
  PLAN=$(python3 "$HERE/briefs.py" plan "$subject" deck "$arm") || { log "FATAL brief plan $subject deck $arm"; exit 1; }
  while IFS= read -r line; do
    dispatch "$cell" "$subject" "$repo" "$wired" "$line"
  done <<< "$PLAN"
  # watch-misroute / watch-verroute: verify-route is an end-of-deck check
  # (it needs every planned brief delivered or W1 logged skipped), so it runs
  # after each cell's deck, from the first cell onward
  python3 "$HERE/briefs.py" verify-route "$EV" "$cell" "$subject" "$arm" \
    || { log "FATAL route verification $cell"; exit 1; }
}

decks() {
  local N ARM P1 P2 R1 R2
  for N in 1 2 3; do
    for ARM in method baseline; do
      if [ "$ARM" = method ]; then
        deck "$(cells_of ae86 "$N")" ae86 & P1=$!
        deck "$(cells_of factorytax "$N")" factorytax & P2=$!
      else
        deck "$(base_cell ae86 "$N")" ae86 & P1=$!
        deck "$(base_cell factorytax "$N")" factorytax & P2=$!
      fi
      R1=0; R2=0; wait "$P1" || R1=$?; wait "$P2" || R2=$?
      # fail-closed: a FATAL inside a deck subshell must abort the whole run
      if [ "$R1" -ne 0 ] || [ "$R2" -ne 0 ]; then
        log "FATAL deck subshell failed (rc $R1/$R2)"; exit 1
      fi
    done
  done
}

# probe_cell: one method cell's probe deck (dl-probe). P1's own step first
# commits the fixture claims (so the dependent and status clause pre-exist at
# HEAD), then stages its uncommitted passage, runs the session and records what
# the gate surfaced and what the session did. Fail-closed: a staging or
# measurement failure aborts the run.
probe_cell() {  # probe_cell CELL SUBJECT
  local cell=$1 subject=$2 repo="$EV/cells/$1"
  local TAG FILE HOOK COND
  while IFS=$'\t' read -r TAG FILE HOOK COND; do
    # the fixture is P1's premise, so it is committed in P1's own step
    # (diag-staging: never a launch preamble)
    if [ "$TAG" = P1 ]; then
      python3 "$HERE/probe.py" setup "$EV" "$cell" "$subject" \
        || { log "FATAL probe setup $cell"; exit 1; }
    fi
    adopt_if_open "$cell" "$repo" "$TAG"
    python3 "$HERE/probe.py" stage "$EV" "$cell" "$subject" "$TAG" \
      || { log "FATAL probe stage $cell $TAG"; exit 1; }
    sess "$cell" oper "$EV/briefs/$FILE" "$TAG"
    python3 "$HERE/probe.py" check "$EV" "$cell" "$subject" "$TAG" \
      || { log "FATAL probe check $cell $TAG"; exit 1; }
  done <<< "$(python3 "$HERE/briefs.py" plan "$subject" probe method)"
  python3 "$HERE/briefs.py" verify-route "$EV" "$cell" "$subject" method probe \
    || { log "FATAL probe route $cell"; exit 1; }
}

probe_deck() {
  local N P1 P2 R1 R2
  for N in 1 2 3; do
    probe_cell "$(cells_of ae86 "$N")" ae86 & P1=$!
    probe_cell "$(cells_of factorytax "$N")" factorytax & P2=$!
    R1=0; R2=0; wait "$P1" || R1=$?; wait "$P2" || R2=$?
    # fail-closed: a staging or measurement failure in a probe subshell aborts
    if [ "$R1" -ne 0 ] || [ "$R2" -ne 0 ]; then
      log "FATAL probe subshell failed (rc $R1/$R2)"; exit 1
    fi
  done
}

# the blind grader's package (dl-evidence): transcripts, metrics, the cells'
# repos and the rubric — no briefs, no deck, no driver log, no orchestrator
# notes. The grader did not drive the sessions; the report says who scored.
score_blind() {
  local B="$EV/blind"
  rm -rf "$B"; mkdir -p "$B"
  cp -a "$EV/transcripts" "$EV/metrics" "$EV/cells" "$B/"
  cp "$HERE/rubric.md" "$HERE/seed-inventory.md" "$B/"
  if [ "$PROCEDURE" = probe ]; then
    cat > "$B/GRADER.txt" <<'EOT'
You are scoring a benchmark probe run you did not take part in (bench-spec
 dl-probe). In this directory: rubric.md and seed-inventory.md (the instruments),
transcripts/ (one jsonl per session, named CELL-SLOT), metrics/ (cost per
session), and cells/ (each cell's repository at run end; its git history is the
evidence). Score series G only, per cell, reporting for each probe session the
outcome found in git at handoff and the tick answer recorded in the transcript
(quote both). A-F are not scored on a probe run: it measures detection, not
seeding, operation or outcomes. Do not infer what a session was asked beyond
its transcript.
EOT
  else
    cat > "$B/GRADER.txt" <<'EOT'
You are scoring a benchmark run you did not take part in. In this directory:
rubric.md and seed-inventory.md (the pre-registered instruments), transcripts/
(one jsonl per session, named CELL-SLOT), metrics/ (cost per session), cells/
(each cell's repository at run end; its git history is the evidence). Score
every criterion the rubric lists, per cell, MET / PARTIAL / FAILED, quoting the
git or transcript evidence for each verdict. Do not infer what a session was
asked beyond its transcript. Write the scores as a table, then the D-series
counts per cell, then F-series outcomes for both arms (method cells S-N,
baseline cells S-base-N).
EOT
  fi
  log "blind package at $B ($(ls "$B/transcripts" | wc -l) transcripts); launch the grader in a fresh sandbox on it"
}

case "$PHASE" in
  setup) setup ;;
  inst)  inst ;;
  deck)  decks ;;
  probe) probe_deck ;;
  all)   setup; inst; if [ "$PROCEDURE" = probe ]; then probe_deck; else decks; fi ;;
  score) python3 "$HERE/briefs.py" skeleton "$EV" "$EV/report-skeleton.html" ;;
  score-blind) score_blind ;;
  *) echo "usage: driver.sh [setup|inst|deck|probe|all|score|score-blind]" >&2; exit 2 ;;
esac
log "$PHASE DONE"
