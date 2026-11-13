#!/usr/bin/env python3
"""probe.py — the planted-defect probe for the gate's judgment items
(dl-probe). One cell gets a setup commit carrying two fixture sets (P1
planted, P2 clean); before each probe session one uncommitted passage is
staged, and after the session what the gate surfaced and what the session did
are recorded. No model, no network; stdlib only.

Fixture per subject and slot:
  target    an id'd claim stating the old value
  neighbor  an id'd claim with a depends-on link deriving from the target
  status    a clause inside the #status element linking the target
  passage   P1: a pure description of a repository file (must be cut)
            P2: a requirement the repository does not hold (must be kept)

The dependent and the status clause live in the setup commit, so the probe
commit changes the target and leaves them unchanged: the neighbor and derived
items are what the gate asks. The passage is staged uncommitted, so the probe
commit adds it and the described item asks too.

Usage:
  probe.py setup EV CELL SUBJECT      one commit of both fixture sets
  probe.py stage EV CELL SUBJECT TAG  stage the slot's uncommitted passage
  probe.py check EV CELL SUBJECT TAG  append the session's result
"""

import html as htmllib
import json
import re
import subprocess
import sys
from pathlib import Path

TAGS = ("P1", "P2")

FIXTURES = {
    "ae86": {
        "P1": dict(
            target=(
                "bench-p1-target",
                "The driveshaft shop measured the pinion flange runout at 0.12 mm.",
            ),
            neighbor=(
                "bench-p1-neighbor",
                'The pinion seal order carries a <a rel="depends-on" '
                'href="#bench-p1-target">shim sized to the flange runout</a> '
                "minus 0.10 mm, so 0.02 mm.",
            ),
            status=' Locked: the <a href="#bench-p1-target">pinion flange runout is 0.12 mm</a>.',
            passage=(
                "bench-p1-described",
                "calc/fitment.py computes the oil pan depth as 180.0 mm and "
                "compares it with the crossmember clearance.",
                "copy",
            ),
            passage_key="computes the oil pan depth as 180.0 mm",
            neighbor_old="0.02",
            neighbor_new="0.08",
            status_old="0.12",
            status_new="0.18",
        ),
        "P2": dict(
            target=(
                "bench-p2-target",
                "The driveshaft shop balanced the shaft to a final spec of 2.5 g-mm.",
            ),
            neighbor=(
                "bench-p2-neighbor",
                'The balance spec <a rel="depends-on" href="#bench-p2-target">stays '
                "inside the 3.0 g-mm class limit</a>, so no waiver is filed.",
            ),
            status=' Locked: the <a href="#bench-p2-target">final balance stays inside the '
            "3.0 g-mm class limit</a>.",
            passage=(
                "bench-p2-described",
                "A driveshaft must be re-balanced after any flange disturbance.",
                "requirement",
            ),
            neighbor_keep="stays inside the 3.0 g-mm class limit",
            status_keep="stays inside the 3.0 g-mm class limit",
            passage_keep="A driveshaft must be re-balanced after any flange disturbance.",
        ),
    },
    "factorytax": {
        "P1": dict(
            target=(
                "bench-p1-target",
                "The close service quoted a batch window of 4 hours.",
            ),
            neighbor=(
                "bench-p1-neighbor",
                'The nightly close job may start no earlier than <a rel="depends-on" '
                'href="#bench-p1-target">the batch window plus one hour</a>, '
                "so 05:00.",
            ),
            status=' Locked: the <a href="#bench-p1-target">close-service batch window is '
            "4 hours</a>.",
            passage=(
                "bench-p1-described",
                "factorytax/brackets.py defines six annual withholding brackets "
                "and subtracts the personal allowance before applying them.",
                "copy",
            ),
            passage_key="defines six annual withholding brackets",
            neighbor_old="05:00",
            neighbor_new="07:00",
            status_old="4 hours",
            status_new="6 hours",
        ),
        "P2": dict(
            target=(
                "bench-p2-target",
                "The close service retains closed payroll files for 90 days.",
            ),
            neighbor=(
                "bench-p2-neighbor",
                'The retention period <a rel="depends-on" href="#bench-p2-target">'
                "exceeds the statutory minimum of 60 days</a>, so no exception is "
                "logged.",
            ),
            status=' Locked: the <a href="#bench-p2-target">retention stays above the '
            "statutory minimum</a>.",
            passage=(
                "bench-p2-described",
                "Closed payroll files must be kept for at least 60 days.",
                "requirement",
            ),
            neighbor_keep="exceeds the statutory minimum of 60 days",
            status_keep="retention stays above the statutory minimum",
            passage_keep="Closed payroll files must be kept for at least 60 days.",
        ),
    },
}

VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
TAG_RE = re.compile(r"<\s*(/?)\s*([A-Za-z][\w:-]*)\b[^>]*?(/?)>", re.S)
ITEM_RE = re.compile(r"ITEM \d+ of \d+ \[(\w+)\] ([^\n]*)")
TICK_RE = re.compile(r"--tick\s+\S+\s+--answer\s+(\w+)")
TOKEN_RE = re.compile(r"token:\s*([0-9a-fA-F]{6,})")


def norm(s):
    return re.sub(
        r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]*>", " ", s or ""))
    ).strip()


def span(html, eid):
    """(start, end, close_start) of the element id'd EID, or None. Handles
    nested elements of the same tag; the status line is a <p> in every
    observed instance, and the fixture claims are its siblings."""
    m = re.search(
        r"<([A-Za-z][\w:-]*)\b[^>]*\bid=[\"']%s[\"'][^>]*>" % re.escape(eid), html
    )
    if not m:
        return None
    tag = m.group(1).lower()
    depth = 0
    for t in TAG_RE.finditer(html, m.start()):
        closing, name, selfclose = t.group(1), t.group(2).lower(), t.group(3)
        if name != tag:
            continue
        if closing:
            depth -= 1
            if depth == 0:
                return (m.start(), t.end(), t.start())
        elif not selfclose and name not in VOID:
            depth += 1
    return None


def inner(html, eid):
    s = span(html, eid)
    if not s:
        return None
    start, _end, close_start = s
    return html[html.index(">", start) + 1 : close_start]


def text(html, eid):
    raw = inner(html, eid)
    return None if raw is None else norm(raw)


def add_block(html, block):
    for pat in (r"</main\s*>", r"</body\s*>"):
        m = re.search(pat, html, re.I)
        if m:
            return html[: m.start()] + block + "\n" + html[m.start() :]
    return html + "\n" + block + "\n"


def add_status_clause(html, clause):
    s = span(html, "status")
    if not s:
        raise SystemExit("probe: no element id=status")
    return html[: s[2]] + clause + html[s[2] :]


def with_fixtures(html, subject):
    fx = FIXTURES[subject]
    block = ""
    for tag in TAGS:
        tid, ttext = fx[tag]["target"]
        nid, ntext = fx[tag]["neighbor"]
        block += f'\n<p id="{tid}">{ttext}</p>\n<p id="{nid}">{ntext}</p>'
    html = add_block(html, block)
    for tag in TAGS:
        html = add_status_clause(html, fx[tag]["status"])
    return html


def main_spec(repo):
    cands = [
        p
        for p in sorted(Path(repo).glob("*.html"))
        if re.search(r"\bid=[\"']status[\"']", p.read_text(errors="replace"))
    ]
    if len(cands) != 1:
        raise SystemExit(
            f"probe: expected one spec with id=status in {repo}, found {len(cands)}"
        )
    return cands[0]


def git(repo, *args, check=True):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=check
    )


def setup_done(head_spec, subject):
    return all(f'id="{FIXTURES[subject][t]["target"][0]}"' in head_spec for t in TAGS)


def cmd_setup(ev, cell, subject):
    repo = Path(ev) / "cells" / cell
    spec = main_spec(repo)
    head_spec = git(repo, "show", f"HEAD:{spec.name}", check=False).stdout
    if setup_done(head_spec, subject):
        print(f"probe: setup present in {cell}")
        return
    if git(repo, "status", "--porcelain", "--", spec.name).stdout.strip():
        raise SystemExit(f"probe: {cell}: spec dirty before setup; refusing")
    html = with_fixtures(spec.read_text(), subject)
    for tag in TAGS:
        for key in ("target", "neighbor"):
            eid = FIXTURES[subject][tag][key][0]
            if html.count(f'id="{eid}"') != 1:
                raise SystemExit(f"probe: {cell}: fixture {eid} not inserted once")
        if FIXTURES[subject][tag]["status"] not in html:
            raise SystemExit(f"probe: {cell}: status clause {tag} not inserted")
    if html.count('id="status"') != 1:
        raise SystemExit(
            f"probe: {cell}: status clause landed outside one status element"
        )
    spec.write_text(html)
    git(repo, "add", spec.name)
    git(
        repo,
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "user.email=bench@local",
        "-c",
        "user.name=bench",
        "commit",
        "-qm",
        "probe: setup P1/P2 fixtures",
    )
    if not setup_done(
        git(repo, "show", f"HEAD:{spec.name}", check=False).stdout, subject
    ):
        raise SystemExit(f"probe: {cell}: setup commit lacks fixtures")
    print(f"probe: setup committed in {cell}")


def cmd_stage(ev, cell, subject, tag):
    if tag not in TAGS:
        raise SystemExit(f"probe: unknown tag {tag}")
    repo = Path(ev) / "cells" / cell
    spec = main_spec(repo)
    pid, ptext, pkind = FIXTURES[subject][tag]["passage"]
    html = spec.read_text()
    if f'id="{pid}"' in html:
        if text(html, pid) == norm(ptext):
            print(f"probe: passage {pid} already staged in {cell}")
            return
        raise SystemExit(f"probe: {cell}: {pid} present with different text")
    state = Path(ev) / "probe-state"
    state.mkdir(parents=True, exist_ok=True)
    dirty = git(repo, "status", "--porcelain").stdout
    (state / f"{cell}-{tag}.json").write_text(json.dumps({"dirty_before": dirty}))
    spec.write_text(add_block(html, f'\n<p id="{pid}">{ptext}</p>'))
    if text(spec.read_text(), pid) != norm(ptext):
        raise SystemExit(f"probe: {cell}: passage {pid} not staged ({pkind})")
    print(f"probe: staged {pid} ({pkind}) in {cell}")


def transcript_events(path):
    events = []
    try:
        with open(path, errors="replace") as fh:
            for line in fh:
                if not line.strip().startswith("{"):
                    continue
                j = json.loads(line)
                if (
                    j.get("type") == "tool_use"
                    and j.get("part", {}).get("tool") == "shell"
                ):
                    st = j["part"].get("state", {}) or {}
                    inp = st.get("input", {}) or {}
                    events.append((inp.get("command", ""), st.get("output", "")))
    except FileNotFoundError:
        pass
    return events


def transcript_complete(path):
    """The transcript's final part is text, trailing step-finish markers ignored;
    the same test as briefs.py's transcript_done (dl-completion). A missing or
    cut transcript is not a session, and no outcome may be recorded for it."""
    try:
        lines = [l for l in open(path, errors="replace") if l.strip().startswith("{")]
        for l in reversed(lines):
            j = json.loads(l)
            if j.get("type") in ("step_finish", "step-finish"):
                continue
            return j.get("type") == "text"
    except FileNotFoundError:
        return False
    return False


def answers(events, neighbor_id):
    out = {
        "neighbor": {"surfaced": False, "answer": None},
        "derived": {"surfaced": False, "answer": None},
        "described": {"surfaced": False, "answer": None},
    }
    for i, (_cmd, output) in enumerate(events):
        for m in ITEM_RE.finditer(output):
            kind, title = m.group(1), m.group(2)
            if kind == "neighbor" and neighbor_id in title:
                ident = "neighbor"
            elif kind in ("derived", "described"):
                ident = kind
            else:
                continue
            # Later occurrences replace earlier ones: an item the candidate
            # changed is shown again with a fresh token, and its last answer is
            # the one the commit carried.
            tok = None
            tm = TOKEN_RE.search(output, m.end())
            if tm:
                tok = tm.group(1)
            ans = None
            for cmd2, _out2 in events[i + 1 :]:
                if tok is not None:
                    if f"--tick {tok}" in cmd2:
                        am = re.search(r"--answer\s+(\w+)", cmd2)
                        ans = am.group(1) if am else None
                        break
                else:
                    am = TICK_RE.search(cmd2)
                    if am:
                        ans = am.group(1)
                        break
            out[ident] = {"surfaced": True, "answer": ans}
    return out


def calls(events):
    return sum(
        1
        for cmd, _out in events
        if "lspec.py" in cmd
        and re.search(r"\breconcile\b", cmd)
        and "--help" not in cmd
    )


def metrics(ev, name):
    p = Path(ev) / "metrics" / f"{name}.json"
    if not p.exists():
        return {"cost": 0.0, "tokens": 0, "tokens_in": 0, "tokens_out": 0}
    sessions = json.loads(p.read_text()).get("sessions", [])
    tin = sum(s.get("tokens_in") or 0 for s in sessions)
    tout = sum(s.get("tokens_out") or 0 for s in sessions)
    return {
        "cost": round(sum(s.get("cost") or 0 for s in sessions), 6),
        "tokens": tin + tout,
        "tokens_in": tin,
        "tokens_out": tout,
    }


def classify(html, subject, tag, ans):
    fx = FIXTURES[subject]
    if tag == "P1":
        n = text(html, fx[tag]["neighbor"][0])
        if n is None:
            n_out = "removed"
        elif fx[tag]["neighbor_new"] in n:
            n_out = "fixed"
        elif fx[tag]["neighbor_old"] in n:
            n_out = "stale"
        else:
            n_out = "other"
        status = text(html, "status") or ""
        if fx[tag]["status_new"] in status:
            d_out = "fixed"
        elif fx[tag]["status_old"] in status:
            d_out = "stale"
        elif fx[tag]["target"][0] not in html:
            d_out = "removed"
        else:
            d_out = "other"
        p = text(html, fx[tag]["passage"][0])
        if p is None:
            p_out = "cut"
        elif fx[tag]["passage_key"] in p:
            p_out = "kept"
        else:
            p_out = "shortened"
    else:
        n = text(html, fx[tag]["neighbor"][0])
        n_out = (
            "removed"
            if n is None
            else ("kept" if fx[tag]["neighbor_keep"] in n else "changed")
        )
        status = text(html, "status") or ""
        d_out = "kept" if fx[tag]["status_keep"] in status else "changed"
        p = text(html, fx[tag]["passage"][0])
        p_out = (
            "removed"
            if p is None
            else ("kept" if fx[tag]["passage_keep"] in p else "changed")
        )
    return n_out, d_out, p_out


def transcript_timeline(path):
    """(first event ms, last event ms, cumulative step tokens by finish time).
    Step metrics, not the final session sum, place tokens before a commit."""
    first = last = None
    finishes = []
    total = 0
    try:
        fh = open(path, errors="replace")
    except FileNotFoundError:
        return None, None, []
    with fh:
        for line in fh:
            if not line.strip().startswith("{"):
                continue
            j = json.loads(line)
            ts = j.get("timestamp")
            if ts is None:
                continue
            if first is None:
                first = ts
            last = ts
            if j.get("type") in ("step_finish", "step-finish"):
                t = j.get("part", {}).get("tokens") or {}
                total += sum(
                    v or 0
                    for k, v in t.items()
                    if k in ("input", "output", "reasoning")
                )
                finishes.append((ts, total))
    return first, last, finishes


def completion(repo, spec_name, path, subject):
    """Time and tokens to the first acceptable and first all-MET P1 commit,
    the bench's semantic efficiency axis (rubric G7). Acceptable still requires
    the target's new value, no neighbor/derived failure, and a cut or pointer,
    never a session that stops at an assent word."""
    start, end, finishes = transcript_timeline(path)
    out = {"session_seconds": None, "first_acceptable": None, "first_strict": None}
    if start is None:
        return out
    if end is not None:
        out["session_seconds"] = round((end - start) / 1000, 1)
    for line in git(repo, "log", "--format=%H %ct %s", "--reverse").stdout.splitlines():
        sha, stamp, log_subject = line.split(" ", 2)
        stamp = int(stamp)
        if stamp * 1000 < start - 1000 or stamp * 1000 > end + 1000:
            continue
        if log_subject.startswith("probe: setup"):
            continue
        html = git(repo, "show", f"{sha}:{spec_name}", check=False).stdout
        if not html:
            continue
        fx = FIXTURES[subject]["P1"]
        n, d, p = classify(html, subject, "P1", {})
        target = text(html, fx["target"][0]) or ""
        target_ok = fx["status_new"] in target
        acceptable = (
            target_ok
            and n in ("fixed", "removed")
            and d in ("fixed", "removed")
            and p in ("cut", "shortened")
        )
        strict = target_ok and n == "fixed" and d == "fixed" and p == "cut"
        point = commit_point(sha, stamp, start, finishes)
        if acceptable and out["first_acceptable"] is None:
            out["first_acceptable"] = point
        if strict and out["first_strict"] is None:
            out["first_strict"] = point
    return out


def commit_point(sha, stamp, start, finishes):
    """Tokens whose step finished before this commit, not just session total."""
    tokens = 0
    for ts, total in finishes:
        if ts <= stamp * 1000 + 999:
            tokens = total
    return {
        "commit": sha[:8],
        "seconds": round(stamp - start / 1000, 1),
        "tokens": tokens,
    }


def write_result(ev, result):
    p = Path(ev) / "probe-results.jsonl"
    keep = []
    if p.exists():
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            try:
                j = json.loads(line)
            except Exception:
                continue
            if (j.get("cell"), j.get("tag")) != (result["cell"], result["tag"]):
                keep.append(line)
    keep.append(json.dumps(result, sort_keys=True))
    p.write_text("\n".join(keep) + "\n")


def cmd_check(ev, cell, subject, tag):
    if tag not in TAGS:
        raise SystemExit(f"probe: unknown tag {tag}")
    repo = Path(ev) / "cells" / cell
    spec = main_spec(repo)
    html = spec.read_text()
    tpath = Path(ev) / "transcripts" / f"{cell}-{tag}.jsonl"
    if not transcript_complete(tpath):
        raise SystemExit(f"probe: {cell}-{tag} transcript incomplete; refusing to record")
    events = transcript_events(tpath)
    ans = answers(events, FIXTURES[subject][tag]["neighbor"][0])
    n_out, d_out, p_out = classify(html, subject, tag, ans)
    state = Path(ev) / "probe-state" / f"{cell}-{tag}.json"
    dirty = (
        json.loads(state.read_text()).get("dirty_before", "") if state.exists() else ""
    )
    result = {
        "cell": cell,
        "tag": tag,
        "subject": subject,
        "kind": "plant" if tag == "P1" else "clean",
        "neighbor": {
            "surfaced": ans["neighbor"]["surfaced"],
            "answer": ans["neighbor"]["answer"],
            "outcome": n_out,
        },
        "derived": {
            "surfaced": ans["derived"]["surfaced"],
            "answer": ans["derived"]["answer"],
            "outcome": d_out,
        },
        "described": {
            "surfaced": ans["described"]["surfaced"],
            "answer": ans["described"]["answer"],
            "outcome": p_out,
        },
        "calls": calls(events),
        "dirty_before": dirty,
    }
    result.update(metrics(ev, f"{cell}-{tag}"))
    if tag == "P1":
        result["completion"] = completion(repo, spec.name, tpath, subject)
    write_result(ev, result)
    print(f"probe: {cell}-{tag} neighbor={n_out} derived={d_out} described={p_out}")


def main(argv):
    usage = (
        "usage: probe.py setup EV CELL SUBJECT | "
        "probe.py stage EV CELL SUBJECT TAG | "
        "probe.py check EV CELL SUBJECT TAG"
    )
    if len(argv) == 5 and argv[1] == "setup":
        cmd_setup(argv[2], argv[3], argv[4])
    elif len(argv) == 6 and argv[1] == "stage":
        cmd_stage(argv[2], argv[3], argv[4], argv[5])
    elif len(argv) == 6 and argv[1] == "check":
        cmd_check(argv[2], argv[3], argv[4], argv[5])
    else:
        sys.exit(usage)


if __name__ == "__main__":
    main(sys.argv)
