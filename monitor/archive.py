"""The archive: every reading and spill, as CSV files in the repository.

The Environment Agency's API keeps about four weeks of readings, and South
West Water's feed only each overflow's latest spill, so the database is the
only copy of the rest. The archive keeps it with the code: archive/ holds a
file of 15-minute readings for each gauge, a spill log for each storm
overflow, and stations.csv, in the format Floodwatch v1 published, from
which its data carries on.

The server exports to the archive every night (scripts/archive.py push,
run by a systemd timer, commits and pushes it), and restores from it the
first time it runs on a new machine, so a fresh server starts with all the
history there is.
"""

import csv
import re
import time
from datetime import datetime
from pathlib import Path

from . import db

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "archive"

READING_COLUMNS = ["dateTime", "value", "unit", "station_id", "station_label"]
STATION_COLUMNS = ["id", "label", "lat", "lon", "river", "type", "rloi", "measure_id"]
SPILL_COLUMNS = ["start_time", "end_time", "duration_min", "is_ongoing"]
OVERFLOW_FILE = re.compile(r"cso_([A-Z0-9]+)\.csv")
# Station and overflow IDs come from outside feeds and go into file names,
# which the nightly push commits, so anything but a plain ID is skipped.
# fullmatch, not match: '$' would let a trailing newline through.
STATION_ID = re.compile(r"[A-Za-z0-9_-]{1,24}")
OVERFLOW_ID = re.compile(r"[A-Z0-9]{1,24}")


def iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def to_ts(text):
    return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, columns, rows):
    """Write a file only if its contents change, by way of a temporary file,
    so an unchanged file keeps its timestamp and a reader never sees half."""
    tmp = path.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="") as f:
        # CRLF, as v1 wrote them, so a night's export changes only new lines.
        w = csv.writer(f, lineterminator="\r\n")
        w.writerow(columns)
        w.writerows(rows)
    if path.exists() and path.read_bytes() == tmp.read_bytes():
        tmp.unlink()
        return False
    tmp.replace(path)
    return True


def slug(text):
    return re.sub(r"[^a-z0-9()]+", "_", str(text).lower()).strip("_") or "station"


def station_type(kind):
    return {"rain": "rainfall", "tidal": "tidal"}.get(kind, "level")


def readings_file(directory, sid, kind, name):
    """A station's readings file: the one already in the archive, so its
    history carries on, or a new one named as v1 named them."""
    prefix = "rainfall" if kind in ("rain", "rainfall") else "level"
    found = sorted(directory.glob(f"{prefix}_{sid}.csv")) + sorted(directory.glob(f"{prefix}_{sid}_*.csv"))
    if found:
        return found[0]
    return directory / (f"rainfall_{sid}.csv" if prefix == "rainfall" else f"level_{sid}_{slug(name)}.csv")


# ---------------------------------------------------------------- export

def export(con, directory=ARCHIVE):
    """Write every station's readings and every overflow's spills. Files of
    stations no longer listed are left as they are. Returns the number of
    files changed."""
    directory.mkdir(parents=True, exist_ok=True)
    changed = 0
    # One consistent snapshot, whatever the poller writes meanwhile.
    began = not con.in_transaction
    if began:
        con.execute("BEGIN")
    try:
        stations = con.execute("SELECT * FROM stations ORDER BY id").fetchall()
        for s in stations:
            if not STATION_ID.fullmatch(s["id"] or ""):
                continue
            rows = con.execute("SELECT ts, value FROM readings WHERE measure = ? ORDER BY ts", (s["measure"],)).fetchall()
            if not rows:
                continue
            path = readings_file(directory, s["id"], s["kind"], s["name"])
            changed += write_csv(path, READING_COLUMNS,
                                 ([iso(ts), value, s["unit"] or "", s["id"], s["name"]] for ts, value in rows))
        # stations.csv: today's stations, and any the archive holds that are
        # no longer listed, so their files stay explained.
        old = directory / "stations.csv"
        archived = {r["id"]: r for r in read_csv(old)} if old.exists() else {}
        # The river levels and flooding ID (rloi) isn't in the station list;
        # v1 recorded it for its gauges, and it's kept.
        listed = {s["id"]: [s["id"], s["name"], s["lat"], s["lon"], s["river"] or "", station_type(s["kind"]),
                            archived.get(s["id"], {}).get("rloi", ""), s["measure"]]
                  for s in stations if STATION_ID.fullmatch(s["id"] or "")}
        for sid, r in archived.items():
            listed.setdefault(sid, [r.get(c, "") for c in STATION_COLUMNS])
        changed += write_csv(old, STATION_COLUMNS, (listed[k] for k in sorted(listed)))
        for (oid,) in con.execute("SELECT DISTINCT id FROM overflow_events ORDER BY id").fetchall():
            if not OVERFLOW_ID.fullmatch(oid or ""):
                continue
            events = con.execute("SELECT started, ended FROM overflow_events WHERE id = ? ORDER BY started", (oid,)).fetchall()
            changed += write_csv(directory / f"cso_{oid}.csv", SPILL_COLUMNS, (
                [iso(started), iso(ended) if ended else "", round((ended - started) / 60) if ended else "",
                 "false" if ended else "true"] for started, ended in events))
    finally:
        if began:
            con.rollback()
    return changed


# ---------------------------------------------------------------- restore

def restore_readings(con, directory=ARCHIVE):
    """Load each listed station's readings, matched to the series it shows.
    Returns ({station id: rows added}, {station id: why it was skipped})."""
    measures = {r["id"]: r["measure"] for r in con.execute("SELECT id, measure FROM stations")}
    loaded, skipped = {}, {}
    for s in read_csv(directory / "stations.csv"):
        sid = s["id"]
        if not STATION_ID.fullmatch(sid or ""):
            skipped[str(sid)] = "not a plain station ID"
            continue
        if sid not in measures:
            skipped[sid] = f"{s['label']}: not a station today"
            continue
        if s.get("measure_id") and s["measure_id"] != measures[sid]:
            skipped[sid] = f"{s['label']}: the archive has {s['measure_id']}, the station shows {measures[sid]}"
            continue
        path = readings_file(directory, sid, s["type"], s["label"])
        if not path.exists():
            skipped[sid] = f"{s['label']}: no readings file"
            continue
        rows = []
        for r in read_csv(path):
            try:
                rows.append((measures[sid], to_ts(r["dateTime"]), float(r["value"])))
            except (KeyError, ValueError, TypeError):
                continue
        before = con.total_changes
        con.executemany("INSERT OR IGNORE INTO readings (measure, ts, value) VALUES (?, ?, ?)", rows)
        loaded[sid] = con.total_changes - before
    con.commit()
    return loaded, skipped


# When the spill log began: v1 started logging spills on 3 June 2026. Its
# logs hold some earlier spills, the latest each overflow had reported when
# it was first polled.
LOG_STARTED = to_ts("2026-06-03T00:00:00Z")


def restore_spills(con, directory=ARCHIVE):
    """Load the spill logs of the overflows listed. Returns {overflow id: spills added}."""
    ours = {r["id"] for r in con.execute("SELECT id FROM overflows")}
    loaded = {}
    for path in sorted(directory.glob("cso_*.csv")):
        m = OVERFLOW_FILE.fullmatch(path.name)
        if not m or m.group(1) not in ours:
            continue
        oid, rows = m.group(1), []
        for r in read_csv(path):
            if not r.get("start_time"):
                continue
            ended = to_ts(r["end_time"]) if r.get("end_time") and r.get("is_ongoing") != "true" else None
            rows.append((oid, to_ts(r["start_time"]), ended))
        before = con.total_changes
        con.executemany("INSERT OR IGNORE INTO overflow_events (id, started, ended) VALUES (?, ?, ?)", rows)
        loaded[oid] = con.total_changes - before
    close_superseded(con)
    if loaded:
        current = db.get_meta(con, "overflow_log_started")
        if not current or int(current) > LOG_STARTED:
            db.set_meta(con, "overflow_log_started", LOG_STARTED)
    con.commit()
    return loaded


def close_superseded(con):
    """A spill still open when a later one began ended when the later one
    began, as the poller records it."""
    for oid, started in con.execute("SELECT id, started FROM overflow_events WHERE ended IS NULL").fetchall():
        nxt = con.execute("SELECT MIN(started) FROM overflow_events WHERE id = ? AND started > ?",
                          (oid, started)).fetchone()[0]
        if nxt is not None:
            con.execute("UPDATE overflow_events SET ended = ? WHERE id = ? AND started = ?", (nxt, oid, started))


def has_readings(directory=None):
    return ((directory or ARCHIVE) / "stations.csv").exists()


def restore(con, directory=ARCHIVE):
    """Load the whole archive. Readings and spills already held are kept, so
    it's safe to run again. Returns (readings added, spills added, skipped)."""
    if not has_readings(directory):
        return 0, 0, {}
    loaded, skipped = restore_readings(con, directory)
    spills = restore_spills(con, directory)
    return sum(loaded.values()), sum(spills.values()), skipped
