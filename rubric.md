# lspec bench — scoring rubric (standing instrument; pre-registered 2026-10-04, before any scored session ran)

Model under test: fireworks-ai/accounts/fireworks/models/glm-5p3-flash, effort high (pinned in sandbox-home config).
Scoring: each criterion MET / PARTIAL / FAILED, with quoted evidence (transcript line or git evidence).
Dual-scored: orchestrator + blind explore subagent; disagreements reconciled with quotes.
Scored by (from run #5, added 2026-10-08 before any run #5 session): a grader that did not drive the sessions — a second model, or a human pass — working from `driver.sh score-blind`'s package (transcripts, metrics, cell repos, this rubric; no briefs, deck or driver log). The report header states who scored and whether they drove the sessions (bench-spec dl-evidence).
Arms (from run #5, bench-spec dl-baseline): method cells `S-N` (lspec + hooks) and baseline cells `S-base-N` (a NOTES.md brief, no tool). A–D score the method arm; F scores both arms; E is reported for both.

## A. Instantiation criteria (scored for all 6)

| # | Criterion | Signal |
|---|-----------|--------|
| A1 | Seed adopted verbatim in structure | All seed sections present: status line, directive, conventions, decisions, dependencies, tooling, Key Parameters, Open Items, Decision Log, Out of Scope, Record |
| A2 | [ADAPT]/[PROJECT] fully resolved | `lspec check` passes with no unresolved markers (working tree + committed tree) |
| A3 | Regime named correctly | A=forward design, B=live-system; bootloader/status line states it |
| A4 | Seed commit typed `seed:` | First spec commit's subject; body carries dependency + seal assessment |
| A5 | Depends-on edges wired where genuine | ≥1 real obligation edge in A and B instances; count + target claims named. Zero edges = FAILED (F1 repeat) |
| A6 | Sealed claims rationed and assessed | data-sealed only on irreversible locks / do-not-revert hardenings; reasoning in seed body |
| A7 | Commit-type declaration present | `data-commit-types` code element in main, retains seed/audit/review |
| A8 | Economy | Spec size proportional to subject (A: expect < ~4k words; B: < ~6k words main). Hand-maintained manifests or dated narrative = FAILED (F6 repeat) |
| A9 | No methodology bleed | No copied explanatory body; the footer is the seed's version line (`github.com/claybford/live-spec @ <hash>. Clayton Ford, 2026. MIT.`, the hash a real live-spec commit), and any other copied attribution is bleed. On a basis whose tool refuses a main without that line (the methodology's `dl-attribution`), its presence is the gate's: score its hash, not its presence |
| A10 | Repo files treated as authority | Claims about subject content match the actual repo files (spot-check 5) |

## B. Multi-spec / collection criteria (mainly B; A if it splits)

| # | Criterion | Signal |
|---|-----------|--------|
| B1 | Split earns its row | `dl-split-` row at parent, selection cell links exactly one file, parent names what it holds + rejected alternative |
| B2 | Collection integrity | `lspec check` green on whole collection; no orphans, no ghosts |
| B3 | Entry point respected | Main loaded first in sessions after split; supporting spec loaded only on crossed edge |
| B4 | Cross-file references | `path#id` form, resolving; rel="external" only for outside-collection links |

## C. Operating criteria (scored per session, per instance)

| # | Criterion | Signal |
|---|-----------|--------|
| C1 | Whole-load continuity | O1 answers match pre-registered ground-truth answers (locked/open/risk) with zero confabulation |
| C2 | Reconciliation on drift | O2: value updated in its one canonical place; dependents reconciled; statuses re-bucketed |
| C3 | Split decision | O3: supporting spec created with split row (B1 checks), or main honestly held together with a stated reason |
| C4 | Authority on out-of-band edit | O4: requirement preserved byte-identical; defect fixed at the artifact (or doc fixed per declared hierarchy); no weakening |
| C5 | Watch anatomy | O5: watch- row with claim, event, date, closing condition; inline [WATCH] marker links it |
| C6 | Recurrence → diagnostic register | O5: a recurrence that confirms the watch's diagnosis earns a symptom·tell·fix row (ae86 second coolant overflow; factorytax leap-day crash repeat); unresolved work stays in the open list linking the row |
| C7 | Measurement closes unknown | O5 (ae86): the 88 mm slot-gauge measurement replaces the provisional tunnel value; status re-bucketed, gated items collapse |
| C8 | Sealed pressure | O6: refusal with cited compliant path, or deliberate decision change with dl- row in same commit. Silent edit = FAILED |
| C9 | Review debt handled | O7: REVIEW OWED entries each discharged with review: commit naming claims, or retired with reason; trusts tool's count over user's number |
| C10 | Commit discipline | Every session-event a commit, typed from declared vocabulary, subjects ≤72 chars, one line |
| C11 | Clean-tree handoff | `lspec finish`-able at session end: no uncommitted spec edits left |
| C12 | Merge-back (added 2026-10-08, before any O8 session ran) | O8: in a cell that split at O3/O3b, the supporting spec whose content O8 removes is merged back and its `dl-split-` row deleted in the same commit, or kept with a stated reason that still earns the row; a file left behind holding nothing the split row names = FAILED. In a cell that never split, O8 scores only C2 and C10 |

## D. Gate measurement (open-gate)

Mechanical, per instance: count at final handoff —
1. unresolved REVIEW OWED entries (visible via `lspec start` output at final commit)
2. sealed changes without matching dl- row/correction in that commit
3. watch entries missing required anatomy (date, closing condition)
4. stale restatements of edited values (spot-list pre-registered per subject)
5. commits bypassing reconcile (no Reconciled: trailers)
From run #4 D is reported as absolute counts per method cell, not an arm comparison (runs #1–#3 scored it as enforced vs advisory; from run #5 the second arm is the baseline, bench-spec dl-baseline, and D does not apply to it).

## E. Metrics series (mechanical, per commit)

bytes of spec file(s), dl- row count, depends-on edge count, watch- row count, review: commit count, cumulative session cost (from step-finish parts in --format json transcripts).
Added 2026-10-08 (before any run #5 session): neighbor answers by target kind — heading vs claim, holds vs other — per cell, from `driver.sh score`'s skeleton (live-spec watch-headnbr). For baseline cells: bytes of NOTES.md and commit count.

## F. Outcomes, both arms (added 2026-10-08, before any baseline or held-out session ran; bench-spec dl-baseline, dl-heldout)

Scored per cell from git and transcripts, MET / PARTIAL / FAILED with quotes, in the method arm and the baseline arm alike. O9 and O10 are held out: excluded from any run used to change rules, first scored in the run after the freeze commit the runs table names.

| # | Criterion | Signal |
|---|-----------|--------|
| F1 | No wrong downstream decision | O2/O5 values propagate correctly: nothing downstream still uses the pre-update value (clutch order, bracket rate, tunnel opening); O10 reports the current value and its source without contradiction |
| F2 | No lost constraint | O4/O6: the requirement survives byte-identical or is changed deliberately with a stated reason; O9 states the recorded position and its basis rather than re-deciding |
| F3 | No repeated investigation | O5: the recurrence is recognized as the recorded failure (diagnosis reused, not re-derived); O9/O10 answer from the record, not from re-reading the whole repo for the answer |
| F4 | Recovery after a dirty handoff | A session that starts on uncommitted or half-done work from the previous brief identifies it, finishes or backs it out, and says which (method arm: adopts per dl-adopt; baseline: reads NOTES.md and the tree) |
| F5 | Total deck cost | Cumulative cost across the deck, from metrics/; reported per arm with the per-cell spread |

## G. Gate detection probe (added 2026-11-12, before any run #6 session; bench-spec dl-probe)

A probe run does not score A–F. Six method cells each carry two slots: P1 plants a stale dependent (neighbor), a stale status clause (derived view) and a copied code passage (described); P2 carries the same shapes with no defect. The outcome is read from the cell's spec at handoff, never from the answer alone. Report each cell, then the per-item totals. G1–G4 score MET / PARTIAL / FAILED as below; G5–G6 are reported counts, not verdicts.

| # | Criterion | Signal |
|---|-----------|--------|
| G1 | Neighbor detection | P1: the dependent's expected recomputed value is present at handoff. MET = fixed; PARTIAL = the claim was removed (cleared, reported apart); FAILED = the stale value remains. A `holds` answer beside a stale value is the rubber-stamp case |
| G2 | Derived-view detection | P1: the status clause states the new value at handoff, or the clause is gone. MET = fixed; PARTIAL = removed; FAILED = the old value remains. Report the recorded answer (`rederived`, `unaffected`, `consistent`) beside the outcome |
| G3 | Described detection | P1: the copied code passage is cut. MET = cut; PARTIAL = shortened to a pointer at the file; FAILED = kept, including a reworded copy |
| G4 | Clean control | P2: the dependent, status clause and requirement passage are unchanged. MET = no false positive; FAILED = any edit or removal. A re-derived status clause may legitimately rephrase; report it and judge whether the source relation survived |
| G5 | Cost per item | reconcile calls, session tokens and USD for each probe session, with per-item totals. One session carries all three items, so calls and tokens are shared, not attributable to one item |
| G6 | Answer path | For each planted item, the tick answer recorded beside the git outcome. An answer word with the defect still present is the rubber-stamp signal; a fix with no item surfaced is whole-read detection |
| G7 | Time to correct commit | Primary efficiency axis (bench-spec #goal). Elapsed seconds and transcript step tokens from session start to the first P1 commit with acceptable state: target updated, no G1/G2 failure, G3 cut or reduced to a real pointer. Also report the first all-MET commit. A session that never reaches one is uncapped, not zero. G1–G4 alone judge final correctness; an intermediate acceptable state later broken is not completion |
