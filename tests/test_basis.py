"""The artifact under test (dl-artifact): the sandbox binds the methodology's
whole collection as its tool derives it (watch-nobackground), and a dirty
LSPEC_SRC is refused by the driver and the sandbox; a method base carries the
whole tool, a baseline base none of it. Needs a live-spec
checkout: LSPEC_SRC, else ../live-spec beside this repository."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
SRC = Path(os.environ.get("LSPEC_SRC", HERE.parent / "live-spec"))


@unittest.skipUnless((SRC / "live-spec.html").exists(), "no live-spec checkout to test against")
class Basis(unittest.TestCase):
    def clone(self):
        d = tempfile.mkdtemp()
        subprocess.run(["git", "clone", "-q", str(SRC), d], check=True)
        return d

    def test_bound_set_is_the_whole_collection(self):
        d = self.clone()
        out = subprocess.run([str(HERE / "methodology-files.sh"), d], capture_output=True, text=True, check=True).stdout
        files = out.split()
        self.assertEqual(files[0], "live-spec.html")
        self.assertIn("background.html", files)
        self.assertIn("portability.html", files)    # the split the hand-listed set missed

    def test_bound_set_leaves_out_this_spec(self):
        d = self.clone()
        graph = subprocess.run(["python3", "lspec.py", "--main", "live-spec.html", "show", "--graph"],
                               cwd=d, capture_output=True, text=True, check=True).stdout
        if "bench-spec.html" not in graph:
            self.skipTest("this basis does not import the bench")
        out = subprocess.run([str(HERE / "methodology-files.sh"), d], capture_output=True, text=True, check=True).stdout
        files = out.split()
        self.assertIn("portability.html", files)
        self.assertFalse([f for f in files if f.endswith("bench-spec.html")], files)

    def test_a_dirty_basis_is_refused(self):
        d = self.clone()
        Path(d, "live-spec.html").write_text(Path(d, "live-spec.html").read_text() + "\n")
        env = {**os.environ, "LSPEC_SRC": d, "BENCH_EV": tempfile.mkdtemp()}
        for script, args in (("driver.sh", ["setup"]), ("sandbox.sh", [d, "--", "true"])):
            r = subprocess.run(["bash", str(HERE / script), *args], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 2, (script, r.stderr))
            self.assertIn("uncommitted changes", r.stderr)

    def busless_inhibitor(self):
        """A systemd-inhibit that exists but cannot reach a bus (watch-nobus)."""
        bindir = tempfile.mkdtemp()
        fake = Path(bindir, "systemd-inhibit")
        fake.write_text("#!/bin/sh\necho 'Failed to connect to bus' >&2\nexit 2\n")
        fake.chmod(0o755)
        return bindir

    def test_the_inhibitor_reexec_names_the_driver_absolutely(self):
        """watch-reexec: systemd-inhibit resolves a command through PATH, so a
        bare `driver.sh` re-exec dies before any phase."""
        text = (HERE / "driver.sh").read_text()
        self.assertIn('exec systemd-inhibit --what=idle "$HERE/driver.sh"', text)
        self.assertNotIn('exec systemd-inhibit --what=idle "$0"', text)

    def test_setup_runs_without_a_system_bus(self):
        d = self.clone()
        env = {**os.environ, "LSPEC_SRC": d, "BENCH_EV": tempfile.mkdtemp(),
               "PATH": self.busless_inhibitor() + os.pathsep + os.environ["PATH"]}
        env.pop("LSPEC_BENCH_INHIBITED", None)
        r = subprocess.run(["bash", str(HERE / "driver.sh"), "setup"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_full_run_stops_when_the_inhibitor_cannot_start(self):
        d = self.clone()
        env = {**os.environ, "LSPEC_SRC": d, "BENCH_EV": tempfile.mkdtemp(),
               "PATH": self.busless_inhibitor() + os.pathsep + os.environ["PATH"]}
        env.pop("LSPEC_BENCH_INHIBITED", None)
        r = subprocess.run(["bash", str(HERE / "driver.sh"), "all"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("could not start", r.stderr)

    def test_method_base_carries_the_whole_tool(self):
        d = self.clone()
        ev = tempfile.mkdtemp()
        env = {**os.environ, "LSPEC_SRC": d, "BENCH_EV": ev, "LSPEC_BENCH_INHIBITED": "1"}
        r = subprocess.run(["bash", str(HERE / "driver.sh"), "setup"], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        tool = ["lspec.py", "hooks"] + (["models"] if Path(d, "models").is_dir() else [])
        for name in tool:
            self.assertTrue(Path(ev, "subjects", "ae86-base", name).exists(), name)
            self.assertFalse(Path(ev, "subjects", "ae86-base-baseline", name).exists(), name)
        if "models" in tool:
            for f in Path(d, "models").rglob("*"):
                if f.is_file():
                    copy = Path(ev, "subjects", "ae86-base", f.relative_to(d))
                    self.assertEqual(copy.read_bytes(), f.read_bytes(), f.name)


if __name__ == "__main__":
    unittest.main()
