"""Loading v1's CSV files: readings matched to v2's series, and spill logs."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

from monitor import db
from tests.support import DBTestCase

spec = importlib.util.spec_from_file_location(
    "backfill_v1", Path(__file__).resolve().parent.parent / "scripts" / "backfill_v1.py")
bf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bf)


class Backfill(DBTestCase):
    def setUp(self):
        super().setUp()
        self._v1 = tempfile.TemporaryDirectory()
        self.addCleanup(self._v1.cleanup)
        self.dir = Path(self._v1.name)
        (self.dir / "stations.csv").write_text(
            "id,label,lat,lon,river,type,rloi,measure_id\n"
            "50140,Umberleigh,50.99,-3.98,River Taw,level,3106,50140-level-stage-i-15_min-m\n"
            "50199,Lapford Bowerthy,50.87,-3.79,,rainfall,,50199-rainfall-tipping_bucket_raingauge-t-15_min-mm\n"
            "47158,Halwill,50.77,-4.22,,rainfall,,47158-rainfall-tipping_bucket_raingauge-t-15_min-mm\n"
            "50198,Barnstaple (Tidal),51.08,-4.06,River Taw,level,,50198-level-tidal_level-i-15_min-mAOD\n")
        (self.dir / "level_50140_umberleigh.csv").write_text(
            "dateTime,value,unit,station_id,station_label\n"
            "2026-01-13T00:00:00Z,0.71,m,50140,Umberleigh\n"
            "2026-01-13T00:15:00Z,0.72,m,50140,Umberleigh\n")
        (self.dir / "rainfall_50199.csv").write_text(
            "dateTime,value,unit,station_id,station_label\n2026-01-13T00:00:00Z,0.2,mm,50199,Lapford Bowerthy\n")
        self.add_station("50140")
        self.add_station("50199", kind="rain", measure="50199-rainfall-tipping_bucket_raingauge-t-15_min-mm")
        self.add_station("50198", kind="tidal", measure="50198-level-tidal_level-i-15_min-m")

    def test_readings_go_to_the_series_v2_shows(self):
        # One reading v2 already holds, from the Environment Agency, is kept.
        self.add_readings("50140-level-stage-i-15_min-m", [(bf.ts("2026-01-13T00:15:00Z"), 0.72)])
        loaded, skipped = bf.backfill_readings(self.con, self.dir)
        self.assertEqual(loaded, {"50140": 1, "50199": 1})
        self.assertIn("47158", skipped)    # not a v2 station
        self.assertIn("50198", skipped)    # v1 kept a different series
        n = self.con.execute("SELECT COUNT(*) FROM readings WHERE measure = '50140-level-stage-i-15_min-m'").fetchone()[0]
        self.assertEqual(n, 2)

    def test_spills_are_loaded_and_an_open_one_closed_by_a_later_spill(self):
        self.add_overflow("SBB00257")
        self.add_overflow("SBB00999")
        (self.dir / "cso_SBB00257.csv").write_text(
            "start_time,end_time,duration_min,is_ongoing\n"
            "2026-06-10T10:00:00Z,2026-06-10T11:00:00Z,60,false\n"
            "2026-11-20T08:00:00Z,,,true\n")
        (self.dir / "cso_SBB01111.csv").write_text(  # outside the catchment
            "start_time,end_time,duration_min,is_ongoing\n2026-06-10T10:00:00Z,,,true\n")
        (self.dir / "cso_sites.csv").write_text("id,river,lat,lon\n")
        # v2's own log already has a later spill for SBB00257.
        later = bf.ts("2026-11-23T09:00:00Z")
        self.con.execute("INSERT INTO overflow_events (id, started, ended) VALUES ('SBB00257', ?, NULL)", (later,))
        loaded = bf.backfill_spills(self.con, self.dir)
        self.assertEqual(loaded, {"SBB00257": 2})
        rows = self.con.execute("SELECT started, ended FROM overflow_events WHERE id = 'SBB00257' ORDER BY started").fetchall()
        self.assertEqual([tuple(r) for r in rows], [
            (bf.ts("2026-06-10T10:00:00Z"), bf.ts("2026-06-10T11:00:00Z")),
            (bf.ts("2026-11-20T08:00:00Z"), later),   # closed when the next began
            (later, None),                           # still spilling
        ])
        self.assertEqual(int(db.get_meta(self.con, "overflow_log_started")), bf.ts("2026-06-03T00:00:00Z"))


if __name__ == "__main__":
    unittest.main()
