"""probe.py — the planted-defect probe (dl-probe). Pure files and git; no
model. The fixtures must land inside the #status element and beside the other
claims, the classifier must read the three outcomes from the spec, and the
answer must pair with its item's token, not merely the next tick."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import probe  # noqa: E402

SPEC = (
    "<!DOCTYPE html><html><body><main><h1>T</h1>\n"
    '<p id="status">Status: x. Open: one (<a href="#open-x">open-x</a>).</p>\n'
    '<p id="claim">c</p></main></body></html>\n'
)


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)


class Fixtures(unittest.TestCase):
    def test_both_slots_land_inside_status_and_beside_the_claims(self):
        html = probe.with_fixtures(SPEC, "ae86")
        self.assertEqual(html.count('id="status"'), 1)
        self.assertEqual(html.count('id="bench-p1-target"'), 1)
        self.assertEqual(html.count('id="bench-p2-target"'), 1)
        self.assertIn("pinion flange runout is 0.12 mm", probe.text(html, "status"))
        self.assertIn("final balance stays inside", probe.text(html, "status"))
        self.assertTrue(
            probe.text(html, "bench-p1-neighbor").startswith("The pinion seal")
        )

    def test_fixtures_are_idempotent_for_a_matching_head(self):
        html = probe.with_fixtures(SPEC, "factorytax")
        self.assertTrue(probe.setup_done(html, "factorytax"))

    def test_passage_stages_before_main(self):
        html = probe.add_block(SPEC, '<p id="x">p</p>')
        self.assertLess(html.index('id="x"'), html.index("</main>"))


class Classify(unittest.TestCase):
    def test_planted_slot_reads_stale_then_fixed(self):
        html = probe.with_fixtures(SPEC, "ae86")
        html = probe.add_block(
            html,
            '<p id="bench-p1-described">calc/fitment.py computes the oil pan depth '
            "as 180.0 mm and compares it with the crossmember clearance.</p>",
        )
        self.assertEqual(
            probe.classify(html, "ae86", "P1", {}), ("stale", "stale", "kept")
        )
        fixed = (
            html.replace("runout at 0.12 mm", "runout at 0.18 mm")
            .replace("so 0.02 mm", "so 0.08 mm")
            .replace(
                "pinion flange runout is 0.12 mm", "pinion flange runout is 0.18 mm"
            )
        )
        fixed = fixed.replace(
            '<p id="bench-p1-described">calc/fitment.py computes the oil pan depth '
            "as 180.0 mm and compares it with the crossmember clearance.</p>\n",
            "",
        )
        self.assertEqual(
            probe.classify(fixed, "ae86", "P1", {}), ("fixed", "fixed", "cut")
        )
        shortened = html.replace(
            "calc/fitment.py computes the oil pan depth as 180.0 mm and compares it "
            "with the crossmember clearance.",
            "See calc/fitment.py for the clearance check.",
        )
        self.assertEqual(probe.classify(shortened, "ae86", "P1", {})[2], "shortened")

    def test_clean_slot_reads_kept(self):
        html = probe.with_fixtures(SPEC, "factorytax")
        html = probe.add_block(
            html,
            '<p id="bench-p2-described">Closed payroll files must be kept for at '
            "least 60 days.</p>",
        )
        self.assertEqual(
            probe.classify(html, "factorytax", "P2", {}), ("kept", "kept", "kept")
        )

    def test_removal_is_not_a_hit_on_the_clean_control(self):
        html = probe.with_fixtures(SPEC, "ae86")
        changed = html.replace("stays inside the 3.0 g-mm class limit", "is 1.8 g-mm")
        self.assertNotEqual(probe.classify(changed, "ae86", "P2", {})[0], "kept")


class Answers(unittest.TestCase):
    def test_answer_pairs_with_its_item_token(self):
        events = [
            (
                "python3 lspec.py reconcile --next",
                "ITEM 3 of 4 [derived] is the bootloader re-derived?\n  token: bb222222",
            ),
            (
                "python3 lspec.py reconcile --next",
                "ITEM 4 of 4 [neighbor] neighbor spec.html#bench-p1-neighbor\n  token: cc333333",
            ),
            ("python3 lspec.py reconcile --tick cc333333 --answer holds", "answered"),
            (
                "python3 lspec.py reconcile --tick bb222222 --answer rederived",
                "answered",
            ),
        ]
        got = probe.answers(events, "bench-p1-neighbor")
        self.assertEqual(got["neighbor"]["answer"], "holds")
        self.assertEqual(got["derived"]["answer"], "rederived")
        self.assertFalse(got["described"]["surfaced"])


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.ev = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.ev, ignore_errors=True)
        self.cell = Path(self.ev, "cells", "ae86-1")
        self.cell.mkdir(parents=True)
        Path(self.ev, "transcripts").mkdir()
        Path(self.ev, "metrics").mkdir()
        Path(self.cell, "spec.html").write_text(SPEC)
        run(["git", "init", "-q"], self.cell)
        run(
            ["git", "-c", "user.email=a@b", "-c", "user.name=a", "add", "-A"], self.cell
        )
        run(
            [
                "git",
                "-c",
                "user.email=a@b",
                "-c",
                "user.name=a",
                "commit",
                "-qm",
                "base",
            ],
            self.cell,
        )

    def test_setup_stage_check_round_trip(self):
        probe.cmd_setup(self.ev, "ae86-1", "ae86")
        head = run(["git", "show", "HEAD:spec.html"], self.cell).stdout
        self.assertTrue(probe.setup_done(head, "ae86"))
        probe.cmd_stage(self.ev, "ae86-1", "ae86", "P1")
        html = Path(self.cell, "spec.html").read_text()
        self.assertIsNotNone(probe.text(html, "bench-p1-described"))
        fixed = (
            html.replace("runout at 0.12 mm", "runout at 0.18 mm")
            .replace("so 0.02 mm", "so 0.08 mm")
            .replace(
                "pinion flange runout is 0.12 mm", "pinion flange runout is 0.18 mm"
            )
        )
        fixed = fixed.replace(
            '<p id="bench-p1-described">calc/fitment.py computes the oil pan depth '
            "as 180.0 mm and compares it with the crossmember clearance.</p>\n",
            "",
        )
        Path(self.cell, "spec.html").write_text(fixed)
        with open(Path(self.ev, "transcripts", "ae86-1-P1.jsonl"), "w") as f:
            for out, cmd in (
                (
                    "ITEM 4 of 5 [neighbor] neighbor spec.html#bench-p1-neighbor\n  token: cc333333",
                    "python3 lspec.py reconcile --tick cc333333 --answer holds",
                ),
                (
                    "ITEM 5 of 5 [described] any description the repository already holds?\n  token: dd444444",
                    "python3 lspec.py reconcile --tick dd444444 --answer confirmed",
                ),
                (
                    "ITEM 3 of 5 [derived] is the bootloader re-derived?\n  token: bb222222",
                    "python3 lspec.py reconcile --tick bb222222 --answer rederived",
                ),
            ):
                f.write(
                    json.dumps(
                        {
                            "type": "tool_use",
                            "part": {
                                "tool": "shell",
                                "state": {
                                    "input": {
                                        "command": "python3 lspec.py reconcile --next"
                                    },
                                    "output": out,
                                },
                            },
                        }
                    )
                    + "\n"
                )
                f.write(
                    json.dumps(
                        {
                            "type": "tool_use",
                            "part": {
                                "tool": "shell",
                                "state": {
                                    "input": {"command": cmd},
                                    "output": "answered",
                                },
                            },
                        }
                    )
                    + "\n"
                )
        Path(self.ev, "metrics", "ae86-1-P1.json").write_text(
            json.dumps(
                {"sessions": [{"cost": 0.02, "tokens_in": 100, "tokens_out": 20}]}
            )
        )
        probe.cmd_check(self.ev, "ae86-1", "ae86", "P1")
        result = json.loads(
            Path(self.ev, "probe-results.jsonl").read_text().splitlines()[-1]
        )
        self.assertEqual(
            result["neighbor"],
            {"surfaced": True, "answer": "holds", "outcome": "fixed"},
        )
        self.assertEqual(result["derived"]["outcome"], "fixed")
        self.assertEqual(result["described"]["outcome"], "cut")
        self.assertEqual(result["calls"], 6)
        self.assertEqual(result["tokens"], 120)


if __name__ == "__main__":
    unittest.main()
