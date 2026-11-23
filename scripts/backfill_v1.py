#!/usr/bin/env python3
"""Load Floodwatch v1's readings and spill logs into the v2 database.

v1 kept its data as CSV files in the repository's data/ directory: a file of
15-minute readings for each gauge, from 13 January 2026, and a spill log for
each storm overflow, from 3 June 2026. The Environment Agency's API keeps
only about four weeks, and South West Water's feed only each overflow's
latest spill, so this is the only copy of the rest.

    git archive origin/main data | tar -x -C /tmp/v1
    python3 scripts/backfill_v1.py /tmp/v1/data

Run it after the server has listed the stations and overflows (its first
poll does), since readings are matched to the series v2 shows for each
station. It can be run again: readings and spills already held are kept.
Standard library only.
"""

import argparse
import csv
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from monitor import db, live, overflows  # noqa: E402

# When v1 started logging spills; its logs hold some earlier spills, the
# latest each overflow had reported when it was first polled.
LOG_STARTED = date(2026, 6, 3)


def ts(iso):
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def backfill_readings(con, data_dir):
    """Returns {station id: rows loaded}, and the stations skipped with why."""
    measures = {r["id"]: r["measure"] for r in con.execute("SELECT id, measure FROM stations")}
    loaded, skipped = {}, {}
    for s in read_csv(data_dir / "stations.csv"):
        sid = s["id"]
        if sid not in measures:
            skipped[sid] = f"{s['label']}: not a v2 station"
            continue
        if s.get("measure_id") and s["measure_id"] != measures[sid]:
            skipped[sid] = f"{s['label']}: v1 kept {s['measure_id']}, v2 shows {measures[sid]}"
            continue
        prefix = "rainfall" if s["type"] == "rainfall" else "level"
        files = sorted(data_dir.glob(f"{prefix}_{sid}.csv")) + sorted(data_dir.glob(f"{prefix}_{sid}_*.csv"))
        if not files:
            skipped[sid] = f"{s['label']}: no readings file"
            continue
        rows = []
        for r in read_csv(files[0]):
            try:
                rows.append((measures[sid], ts(r["dateTime"]), float(r["value"])))
            except (KeyError, ValueError, TypeError):
                continue
        before = con.total_changes
        con.executemany("INSERT OR IGNORE INTO readings (measure, ts, value) VALUES (?, ?, ?)", rows)
        loaded[sid] = con.total_changes - before
    con.commit()
    return loaded, skipped


def backfill_spills(con, data_dir):
    """Returns {overflow id: spills loaded}."""
    ours = {r["id"] for r in con.execute("SELECT id FROM overflows WHERE active = 1")}
    loaded = {}
    for path in sorted(data_dir.glob("cso_*.csv")):
        oid = path.stem[4:]
        if oid not in ours:
            continue  # cso_sites.csv and the like, or an overflow outside the catchment
        rows = []
        for r in read_csv(path):
            if not r.get("start_time"):
                continue
            ended = ts(r["end_time"]) if r.get("end_time") and r.get("is_ongoing") != "true" else None
            rows.append((oid, ts(r["start_time"]), ended))
        before = con.total_changes
        con.executemany("INSERT OR IGNORE INTO overflow_events (id, started, ended) VALUES (?, ?, ?)", rows)
        loaded[oid] = con.total_changes - before
    close_superseded(con)
    started = int(datetime(LOG_STARTED.year, LOG_STARTED.month, LOG_STARTED.day, tzinfo=timezone.utc).timestamp())
    current = db.get_meta(con, "overflow_log_started")
    if not current or int(current) > started:
        db.set_meta(con, "overflow_log_started", started)
    con.commit()
    return loaded


def close_superseded(con):
    """A spill still open when a later one began ended when the later one
    began, as the poller records it: v1's last spill can be open while v2's
    own log has since moved on."""
    open_rows = con.execute("SELECT id, started FROM overflow_events WHERE ended IS NULL").fetchall()
    for oid, started in open_rows:
        nxt = con.execute("SELECT MIN(started) FROM overflow_events WHERE id = ? AND started > ?",
                          (oid, started)).fetchone()[0]
        if nxt is not None:
            con.execute("UPDATE overflow_events SET ended = ? WHERE id = ? AND started = ?", (nxt, oid, started))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("data_dir", type=Path, help="v1's data directory")
    args = ap.parse_args()
    if not (args.data_dir / "stations.csv").exists():
        sys.exit(f"{args.data_dir} has no stations.csv; give v1's data directory")
    con = db.connect()
    try:
        if not con.execute("SELECT COUNT(*) FROM stations").fetchone()[0]:
            sys.exit("The database has no stations yet; let the server's first poll run, then try again")
        loaded, skipped = backfill_readings(con, args.data_dir)
        for sid, n in sorted(loaded.items()):
            print(f"  {sid}: {n} readings")
        for why in skipped.values():
            print(f"  skipped {why}")
        spills = backfill_spills(con, args.data_dir)
        print(f"  {sum(spills.values())} spills for {len(spills)} storm overflows")
        live.write(con)
        overflows.write_summary(con)
    finally:
        con.close()
    print(f"Loaded {sum(loaded.values())} readings for {len(loaded)} stations.")


if __name__ == "__main__":
    main()
