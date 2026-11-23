#!/usr/bin/env python3
"""Export the database to archive/, restore it from there, or push it.

    python3 scripts/archive.py export    # write archive/ from the database
    python3 scripts/archive.py restore   # load archive/ into the database
    python3 scripts/archive.py push      # export, then commit and push if anything changed

`push` is what the nightly timer runs on the server
(deploy/floodwatch-archive.service). It commits only archive/, as the
archive's own author, and leaves the checkout's git configuration alone.
The server restores from archive/ by itself the first time it runs, so
`restore` is for loading an archive by hand, such as v1's data. Standard
library only.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from monitor import archive, db, live, overflows  # noqa: E402

AUTHOR = ["-c", "user.name=Floodwatch archive", "-c", "user.email=floodwatch-archive@users.noreply.github.com"]


def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=check)


def export():
    con = db.connect(read_only=True)
    try:
        n = archive.export(con)
    finally:
        con.close()
    print(f"archive: {n} files changed")
    return n


def restore(directory):
    con = db.connect()
    try:
        if not con.execute("SELECT COUNT(*) FROM stations").fetchone()[0]:
            sys.exit("The database has no stations yet: let the server's first poll list them, then try again")
        readings, spills, skipped = archive.restore(con, directory)
        for why in skipped.values():
            print(f"  skipped {why}")
        live.write(con)
        overflows.write_summary(con)
    finally:
        con.close()
    print(f"restored {readings} readings and {spills} spills from {directory}")


def push():
    dirty = git("status", "--porcelain", "--untracked-files=no", "--", ".", ":!archive").stdout.strip()
    if dirty:
        sys.exit(f"The checkout has changes outside archive/; not committing:\n{dirty}")
    export()
    git("add", "--", "archive")
    if not git("diff", "--cached", "--quiet", check=False).returncode:
        print("archive: nothing to commit")
        return
    stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    git(*AUTHOR, "commit", "--quiet", "-m", f"Archive readings and spills, {stamp}")
    git("pull", "--rebase", "--quiet")
    git("push", "--quiet")
    print(f"archive: pushed {stamp}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("export", help="write archive/ from the database")
    r = sub.add_parser("restore", help="load an archive into the database")
    r.add_argument("directory", nargs="?", type=Path, default=archive.ARCHIVE,
                   help="the archive to load (default: archive/); v1's data/ directory works too")
    sub.add_parser("push", help="export, then commit and push archive/ if it changed")
    args = ap.parse_args()
    if args.command == "export":
        export()
    elif args.command == "restore":
        restore(args.directory)
    else:
        push()


if __name__ == "__main__":
    main()
