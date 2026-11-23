"""Poll the Environment Agency for new readings.

    python3 -m monitor.poll           # poll every 5 minutes
    python3 -m monitor.poll --once    # one cycle, then exit

serve.py runs the same loop in a background thread, so a deployment needs
only the one process.
"""

import argparse
import threading
import time

from . import archive, db, drought, ea, floods, live, overflows, powercuts, weather

# Stations report every 15 minutes but not in step, and the EA publishes each
# reading some minutes after it is taken, so polling more often than the
# reporting interval shortens the wait for each new reading.
INTERVAL = 5 * 60
STATION_REFRESH = 24 * 3600
DROUGHT_RETRY = 3600   # after a failed drought report, try again in an hour

# The first cycle after the server starts reads everything, whatever the
# schedules say, so that whatever a deploy adds or changes shows straight away.
_started = False


def cycle():
    global _started
    fresh, _started = not _started, True
    con = db.connect()
    try:
        # The feeds are independent; a failure in one doesn't stop the others.
        # Filling gaps in the gauges' history comes last, because on a first
        # run, or after the server has been down, it can take minutes.
        gaps = None
        for name, poll in (("gauge", poll_gauges), ("overflow", poll_overflows),
                           ("archive", restore_spills),
                           ("flood warning", poll_floods), ("weather warning", poll_weather),
                           ("power cut", poll_powercuts), ("drought", poll_drought)):
            try:
                result = poll(con, fresh)
                if name == "gauge":
                    gaps = result
            except Exception as e:  # noqa: BLE001
                ea.log(f"{name} poll failed: {e}")
        if gaps:
            try:
                fill_gauge_gaps(con, *gaps)
            except Exception as e:  # noqa: BLE001
                ea.log(f"gauge history fill failed: {e}")
    finally:
        con.close()


def poll_gauges(con, fresh=False):
    """The latest reading at every gauge, written to live.json. Returns what
    fill_gauge_gaps needs to fetch any missing history."""
    refreshed = int(db.get_meta(con, "stations_refreshed", 0))
    if fresh or time.time() - refreshed > STATION_REFRESH:
        ea.log("refreshing the station list")
        n = ea.refresh_stations(con)
        db.set_meta(con, "stations_refreshed", int(time.time()))
        con.commit()
        ea.log(f"station list refreshed: {n} stations")
    restore_readings(con)
    latest, held = ea.store_latest(con)
    db.set_meta(con, "last_poll", int(time.time()))
    con.commit()
    live.write(con)
    ea.log(f"gauges: {len(latest)} latest readings")
    return latest, held


def restore_readings(con):
    """On a new server, load the readings in archive/ once the stations are
    listed, before the latest readings are stored, so the gap fill that
    follows fetches only what the archive doesn't hold. A failure is logged
    and tried again next cycle; it doesn't stop the gauge poll."""
    if db.get_meta(con, "archive_readings_restored") or db.get_meta(con, "archive_restored"):
        return
    if not con.execute("SELECT 1 FROM stations LIMIT 1").fetchone():
        return  # the station list failed; try again next cycle
    try:
        loaded, skipped = archive.restore_readings(con) if archive.has_readings() else ({}, {})
    except Exception as e:  # noqa: BLE001
        ea.log(f"archive: restoring readings failed, trying again next cycle: {e}")
        return
    db.set_meta(con, "archive_readings_restored", int(time.time()))
    con.commit()
    ea.log(f"archive: restored {sum(loaded.values())} readings" + (f"; skipped {len(skipped)} stations" if skipped else ""))


def restore_spills(con, fresh=False):
    """On a new server, load the spill logs in archive/ once the overflows
    are listed. Until then it waits, however many cycles that takes, so a
    failed first overflow poll can't lose them."""
    if db.get_meta(con, "archive_spills_restored") or db.get_meta(con, "archive_restored"):
        return
    if not con.execute("SELECT 1 FROM overflows LIMIT 1").fetchone():
        return  # the overflow list failed; try again next cycle
    spills = archive.restore_spills(con)
    db.set_meta(con, "archive_spills_restored", int(time.time()))
    con.commit()
    overflows.write_summary(con)
    ea.log(f"archive: restored {sum(spills.values())} spills")


def fill_gauge_gaps(con, latest, held):
    filled = ea.fill_gaps(con, latest, held)
    if filled:
        live.write(con)
        ea.log(f"gauges: {filled} series filled in")


def poll_floods(con, fresh=False):
    refreshed = int(db.get_meta(con, "flood_areas_refreshed", 0))
    if fresh or time.time() - refreshed > STATION_REFRESH:
        # The daily list refresh failing mustn't stop the warnings: they're
        # read against yesterday's list, and the refresh is tried next cycle.
        try:
            n = floods.refresh_areas(con)
            db.set_meta(con, "flood_areas_refreshed", int(time.time()))
            con.commit()
            ea.log(f"flood area list refreshed: {n} areas")
        except Exception as e:  # noqa: BLE001
            con.rollback()
            ea.log(f"flood area list refresh failed, trying again next cycle: {e}")
    warnings = floods.poll_warnings(con)
    floods.write_summary(warnings)
    ea.log(f"flood warnings: {len(warnings)} in force")


def poll_weather(con, fresh=False):
    """The Met Office feed is a few hundred bytes, so it's read every cycle."""
    warnings = weather.poll()
    ea.log(f"weather warnings: {len(warnings)} for Devon")


def poll_powercuts(con, fresh=False):
    """NGED's file of live power cuts is a few kilobytes, so it's read every cycle."""
    cuts = powercuts.poll()
    ea.log(f"power cuts: {len(cuts)} in the catchment, {sum(c['off'] for c in cuts)} customers off")


def poll_drought(con, fresh=False):
    """The drought report is weekly, so it's read every six hours."""
    if fresh or time.time() - int(db.get_meta(con, "drought_refreshed", 0)) > drought.REFRESH:
        try:
            status = drought.poll()
        except Exception:
            # Try again in an hour rather than every cycle: a report that no
            # longer parses won't start parsing in five minutes.
            db.set_meta(con, "drought_refreshed", int(time.time()) - drought.REFRESH + DROUGHT_RETRY)
            con.commit()
            raise
        db.set_meta(con, "drought_refreshed", int(time.time()))
        con.commit()
        ea.log(f"drought: {', '.join(s['stage'] for s in status['stages']) or 'none'} ({status['report']['period']})")


def poll_overflows(con, fresh=False):
    refreshed = int(db.get_meta(con, "overflows_refreshed", 0))
    if fresh or time.time() - refreshed > STATION_REFRESH:
        # As with flood areas: a failed daily refresh is tried next cycle, and
        # the spill log carries on against yesterday's list meanwhile.
        try:
            n = overflows.refresh_overflows(con)
            db.set_meta(con, "overflows_refreshed", int(time.time()))
            if not db.get_meta(con, "overflow_log_started"):
                db.set_meta(con, "overflow_log_started", int(time.time()))
            con.commit()
            ea.log(f"overflow list refreshed: {n} overflows")
        except Exception as e:  # noqa: BLE001
            con.rollback()
            ea.log(f"overflow list refresh failed, trying again next cycle: {e}")
    n = overflows.poll_overflows(con)
    overflows.write_summary(con)
    ea.log(f"overflows: {n} statuses")


def run_forever(stop=None):
    stop = stop or threading.Event()
    while not stop.is_set():
        started = time.time()
        try:
            cycle()
        except Exception as e:  # noqa: BLE001 - log, wait, try again next interval
            ea.log(f"poll failed: {e}")
        stop.wait(max(60, INTERVAL - (time.time() - started)))


def start_thread():
    stop = threading.Event()
    threading.Thread(target=run_forever, args=(stop,), name="poller", daemon=True).start()
    return stop


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="run one cycle and exit")
    args = ap.parse_args()
    if args.once:
        cycle()
    else:
        run_forever()


if __name__ == "__main__":
    main()
