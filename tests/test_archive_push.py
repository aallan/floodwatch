"""The nightly push: commits in its own worktree, on the tip of origin/main.

These run real git against repositories in a temporary directory: a bare
"GitHub", the server's checkout cloned from it, and a second clone standing
in for someone pushing code to main meanwhile.
"""

import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.support import NOW, DBTestCase

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("archive_script", ROOT / "scripts" / "archive.py")
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)

IDENTITY = ["-c", "user.name=Test", "-c", "user.email=test@example.invalid"]


def git(cwd, *args):
    return subprocess.run(["git", *IDENTITY, *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


@unittest.skipUnless(shutil.which("git"), "needs git")
class Push(DBTestCase):
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.origin = self.tmp / "origin.git"
        git(self.tmp, "init", "--quiet", "--bare", "--initial-branch=main", str(self.origin))
        seed = self.tmp / "seed"
        git(self.tmp, "clone", "--quiet", str(self.origin), str(seed))
        (seed / "archive").mkdir()
        (seed / "archive" / "stations.csv").write_text("id,label,lat,lon,river,type,rloi,measure_id\r\n")
        (seed / "serve.py").write_text("# the server\n")
        (seed / ".gitignore").write_text("data/\n")
        git(seed, "add", ".")
        git(seed, "commit", "--quiet", "-m", "Start")
        git(seed, "push", "--quiet", "origin", "main")
        self.server = self.tmp / "server"
        git(self.tmp, "clone", "--quiet", str(self.origin), str(self.server))
        self.worktree = self.server / "data" / "archive-worktree"
        m = self.add_station("50140", name="Umberleigh")
        self.add_readings(m, [(NOW, 0.41), (NOW + 900, 0.42)])

    def push(self):
        with mock.patch("builtins.print"):
            return script.push(root=self.server, worktree=self.worktree)

    def origin_log(self):
        return git(self.origin, "log", "--format=%s", "main").splitlines()

    def test_pushes_the_archive_and_leaves_the_servers_checkout_alone(self):
        before = git(self.server, "rev-parse", "HEAD")
        self.assertTrue(self.push())
        self.assertEqual(self.origin_log()[1:], ["Start"])
        self.assertTrue(self.origin_log()[0].startswith("Archive readings and spills"))
        files = git(self.origin, "ls-tree", "--name-only", "main", "archive/").split()
        self.assertIn("archive/level_50140_umberleigh.csv", files)
        self.assertEqual(git(self.server, "rev-parse", "HEAD"), before)
        self.assertEqual(git(self.server, "status", "--porcelain"), "")

    def test_lands_on_top_of_code_pushed_to_main_meanwhile(self):
        other = self.tmp / "other"
        git(self.tmp, "clone", "--quiet", str(self.origin), str(other))
        (other / "serve.py").write_text("# the server, changed\n")
        git(other, "commit", "--quiet", "-am", "Change the server")
        git(other, "push", "--quiet", "origin", "main")
        self.assertTrue(self.push())
        self.assertEqual(self.origin_log()[1:], ["Change the server", "Start"])
        # The server's checkout is behind, but clean, so a deploy's pull is a fast forward.
        self.assertEqual(git(self.server, "status", "--porcelain"), "")
        git(self.server, "pull", "--quiet", "--ff-only")
        self.assertTrue((self.server / "archive" / "level_50140_umberleigh.csv").exists())

    def test_nothing_new_pushes_nothing(self):
        self.assertTrue(self.push())
        self.assertFalse(self.push())
        self.assertEqual(len(self.origin_log()), 2)

    def test_a_failed_push_leaves_nothing_for_the_next_night(self):
        # GitHub refuses every push tonight, after the commit has been made.
        hook = self.origin / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\necho refused >&2\nexit 1\n")
        hook.chmod(0o755)
        with self.assertRaises(subprocess.CalledProcessError):
            self.push()
        hook.unlink()
        self.add_readings(self.add_station("50199", kind="rain", name="Lapford", unit="mm"), [(NOW, 0.2)])
        self.assertTrue(self.push())
        self.assertEqual(len(self.origin_log()), 2)    # one archive commit, not one per night

    def test_a_push_rejected_because_main_moved_starts_again_from_the_new_tip(self):
        other = self.tmp / "other"
        git(self.tmp, "clone", "--quiet", str(self.origin), str(other))
        real_git = script.git
        raced = []

        def racing_git(*args, **kwargs):
            # Just before the first push, someone else pushes to main.
            if args[0] == "push" and not raced:
                raced.append(True)
                (other / "serve.py").write_text("# raced\n")
                git(other, "commit", "--quiet", "-am", "Race")
                git(other, "push", "--quiet", "origin", "main")
            return real_git(*args, **kwargs)

        with mock.patch.object(script, "git", side_effect=racing_git):
            self.assertTrue(self.push())
        self.assertEqual(self.origin_log()[1:], ["Race", "Start"])


if __name__ == "__main__":
    unittest.main()
