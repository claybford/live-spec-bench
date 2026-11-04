"""briefs.py session_done (dl-completion). Pure files, no git, no model."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


# ------------------------------------------------ bench driver (dl-completion)

class BenchDriver(unittest.TestCase):
    """bench/briefs.py session_done, which driver.sh's tdone and verify-route
    both call: a session is done when its transcript's final part is text
    (trailing step-finish markers ignored) and the runner's end-of-session
    HEAD stamp exists. Pure files, no git, no model (dl-completion)."""

    BRIEFS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'briefs.py')

    def done(self, ev, name):
        return subprocess.run([sys.executable, self.BRIEFS, 'done', ev, name]).returncode

    def case(self, ev, name, parts, stamp=True):
        os.makedirs(os.path.join(ev, 'transcripts'), exist_ok=True)
        os.makedirs(os.path.join(ev, 'metrics'), exist_ok=True)
        with open(os.path.join(ev, 'transcripts', name + '.jsonl'), 'w') as f:
            for p in parts:
                f.write(json.dumps({'type': p, 'x': 1}) + '\n')
        if stamp:
            Path(ev, 'metrics', name + '.head').write_text('abc123\n')

    def test_done_only_with_final_text_and_a_stamp(self):
        ev = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, ev, ignore_errors=True)
        self.case(ev, 'ok', ['step_start', 'tool_use', 'text', 'step_finish'])
        self.assertEqual(self.done(ev, 'ok'), 0)
        self.case(ev, 'cut-tool', ['step_start', 'text', 'tool_use'])
        self.assertEqual(self.done(ev, 'cut-tool'), 1)
        self.case(ev, 'cut-step', ['text', 'step_finish', 'step_start'])
        self.assertEqual(self.done(ev, 'cut-step'), 1)
        self.case(ev, 'err', ['text', 'error'])
        self.assertEqual(self.done(ev, 'err'), 1)
        self.case(ev, 'nostamp', ['text', 'step_finish'], stamp=False)
        self.assertEqual(self.done(ev, 'nostamp'), 1)
        self.assertEqual(self.done(ev, 'absent'), 1)

    def test_driver_delegates_tdone_to_briefs(self):
        driver = Path(os.path.dirname(self.BRIEFS), 'driver.sh').read_text()
        self.assertRegex(driver, r'tdone\(\) \{ python3 "\$HERE/briefs.py" done')   # one implementation

    def test_skeleton_lists_sessions_without_paths(self):
        ev = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, ev, ignore_errors=True)
        self.case(ev, 'ae86-1-O1', ['text'])
        Path(ev, 'metrics', 'ae86-1-O1.json').write_text(json.dumps({'sessions': [{'cost': 0.0123}]}))
        out = os.path.join(ev, 'skeleton.html')
        r = subprocess.run([sys.executable, self.BRIEFS, 'skeleton', ev, out], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        html_ = Path(out).read_text()
        self.assertIn('<td>ae86-1</td><td>O1</td><td>done</td>', html_)
        self.assertIn('0.012', html_)
        self.assertIn('<td>C12</td>', html_)
        self.assertNotIn(ev, html_)                              # no evidence paths leak

    def test_registry_has_two_arms_and_held_out_slots(self):
        """dl-baseline, dl-heldout: the method arm's briefs are byte-pinned;
        the baseline arm gets its own inst brief and no tool-bound slots; held-out
        slots are in both arms and skipped by verify-route when logged so."""
        plan = lambda *a: subprocess.run([sys.executable, self.BRIEFS, 'plan', *a],
                                         capture_output=True, text=True).stdout
        method = [l.split('\t')[0] for l in plan('ae86', 'deck').splitlines()]
        base = [l.split('\t')[0] for l in plan('ae86', 'deck', 'baseline').splitlines()]
        self.assertEqual(method, ['O1', 'O2', 'O3', 'O3b', 'O4', 'O5', 'O6', 'O7', 'O8', 'O9', 'O10', 'W1'])
        self.assertEqual(base, ['O1', 'O2', 'O3', 'O3b', 'O4', 'O5', 'O6', 'O8', 'O9', 'O10'])
        self.assertIn('inst-base-factorytax.txt', plan('factorytax', 'inst', 'baseline'))
        self.assertIn('inst-factorytax.txt', plan('factorytax', 'inst'))
        heldout = [l for l in plan('factorytax', 'deck').splitlines() if l.endswith('heldout')]
        self.assertEqual([l.split('\t')[0] for l in heldout], ['O9', 'O10'])
        ev = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, ev, ignore_errors=True)
        # verify-route: a held-out slot logged as skipped passes; a missing one fails
        sys.path.insert(0, os.path.dirname(self.BRIEFS))
        import briefs
        os.makedirs(os.path.join(ev, 'briefs-used')); os.makedirs(os.path.join(ev, 'cells', 'ae86-base-1'))
        for tag, fname, _h, cond, body in briefs.entries('ae86', 'deck', 'baseline'):
            if cond == 'heldout':
                continue
            Path(ev, 'briefs-used', f'ae86-base-1-{tag}.txt').write_text(body)
            self.case(ev, f'ae86-base-1-{tag}', ['text'])
        r = subprocess.run([sys.executable, self.BRIEFS, 'verify-route', ev, 'ae86-base-1', 'ae86', 'baseline'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1); self.assertIn('O9 neither delivered nor logged', r.stderr)
        Path(ev, 'driver-progress.log').write_text('ae86-base-1 O9 skipped (held out)\nae86-base-1 O10 skipped (held out)\n')
        r = subprocess.run([sys.executable, self.BRIEFS, 'verify-route', ev, 'ae86-base-1', 'ae86', 'baseline'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_skeleton_counts_neighbor_answers_by_target_kind(self):
        """watch-headnbr's measurement: neighbor items paired with their answer,
        split by whether the neighbor id is a heading in the cell's spec."""
        ev = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, ev, ignore_errors=True)
        os.makedirs(os.path.join(ev, 'cells', 'ae86-1'))
        Path(ev, 'cells', 'ae86-1', 'spec.html').write_text('<h2 id="regimes">R</h2><p id="claim">c</p>')
        lines = ['ITEM 3 of 5 [neighbor] neighbor spec.html#regimes', 'python3 lspec.py reconcile --tick ab12 --answer holds',
                 'ITEM 4 of 5 [neighbor] neighbor spec.html#claim', 'python3 lspec.py reconcile --tick cd34 --answer holds',
                 'ITEM 5 of 5 [neighbor] neighbor spec.html#regimes', 'edited the file instead']
        self.case(ev, 'ae86-1-O2', ['text'])
        with open(os.path.join(ev, 'transcripts', 'ae86-1-O2.jsonl'), 'w') as f:
            for l in lines:
                f.write(json.dumps({'type': 'text', 'part': {'text': l}}) + '\n')
            f.write(json.dumps({'type': 'text'}) + '\n')
        Path(ev, 'metrics', 'ae86-1-O2.json').write_text(json.dumps({'sessions': []}))
        out = os.path.join(ev, 'skeleton.html')
        r = subprocess.run([sys.executable, self.BRIEFS, 'skeleton', ev, out], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        html_ = Path(out).read_text()
        self.assertIn('<td>ae86-1</td><td>1 / 1</td><td>1 / 0</td>', html_)
        self.assertIn('<td>F5</td>', html_)
        self.assertIn('Scored by:', html_)
