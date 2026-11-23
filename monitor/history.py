"""A station's history for its popup chart, and for download.

Readings are kept indefinitely, 15 minutes apart, so a long chart would be
many thousands of points. Up to RAW_DAYS the chart gets every reading; over
a longer range, or all time, readings are put into buckets of an hour or
more, enough that the chart has no more than MAX_POINTS. A river or tidal
gauge's bucket is its highest reading, so floods aren't averaged away; a
rain gauge's is its total.
"""

import csv
import io
import re
import time

RAW_DAYS = 28
MAX_POINTS = 3000
BUCKETS = (3600, 3 * 3600, 6 * 3600, 12 * 3600, 86400, 7 * 86400)


def bucket_for(span):
    """The smallest bucket that keeps a span of seconds within MAX_POINTS."""
    return next((b for b in BUCKETS if span / b <= MAX_POINTS), BUCKETS[-1])


def readings(con, station, days, now=None):
    """{"readings": [[ts, value]], "bucket": seconds or None, "first": ts or None}.

    days is a number of days, or None for all time. The first reading the
    station has is returned too, so a chart of all time knows where to start.
    """
    now = int(now or time.time())
    measure = station["measure"]
    first = con.execute("SELECT MIN(ts) FROM readings WHERE measure = ?", (measure,)).fetchone()[0]
    since = now - days * 86400 if days else (first or now) - 1
    if days and days <= RAW_DAYS:
        rows = con.execute("SELECT ts, value FROM readings WHERE measure = ? AND ts > ? ORDER BY ts",
                           (measure, since)).fetchall()
        return {"readings": [[r[0], r[1]] for r in rows], "bucket": None, "first": first}
    b = bucket_for(now - max(since, first or since))
    agg = "SUM" if station["kind"] == "rain" else "MAX"
    rows = con.execute(f"""SELECT (ts / ?) * ? AS t, {agg}(value) FROM readings
                           WHERE measure = ? AND ts > ? GROUP BY ts / ? ORDER BY t""",
                       (b, b, measure, since, b)).fetchall()
    return {"readings": [[r[0], round(r[1], 3)] for r in rows], "bucket": b, "first": first}


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_") or "station"


def csv_filename(station):
    kind = {"level": "level", "tidal": "tidal", "rain": "rainfall"}.get(station["kind"], "readings")
    return f"{kind}_{slug(station['id'])}_{slug(station['name'])}.csv"


def csv_rows(con, station, chunk=5000):
    """Every reading the station has, as CSV text in pieces: the columns
    Floodwatch has always published, dateTime,value,unit,station_id,station_label."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["dateTime", "value", "unit", "station_id", "station_label"])
    cur = con.execute("SELECT ts, value FROM readings WHERE measure = ? ORDER BY ts", (station["measure"],))
    while True:
        rows = cur.fetchmany(chunk)
        for ts, value in rows:
            w.writerow([time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)), value, station["unit"] or "",
                        station["id"], station["name"]])
        yield out.getvalue()
        out.seek(0)
        out.truncate()
        if not rows:
            return
