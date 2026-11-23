"""The archive: exporting readings and spills to CSV, and restoring them on a new server."""

import tempfile
import unittest
from pathlib import Path

from monitor import archive, db
from tests.support import DBTestCase

V1_STATIONS = (
    "id,label,lat,lon,river,type,rloi,measure_id\r\n"
    "50140,Umberleigh,50.99,-3.98,River Taw,level,3106,50140-level-stage-i-15_min-m\r\n"
    "50199,Lapford Bowerthy,50.87,-3.79,,rainfall,,50199-rainfall-tipping_bucket_raingauge-t-15_min-mm\r\n"
    "47158,Halwill,50.77,-4.22,,rainfall,,47158-rainfall-tipping_bucket_raingauge-t-15_min-mm\r\n"
    "50198,Barnstaple (Tidal),51.08,-4.06,River Taw,level,,50198-level-tidal_level-i-15_min-mAOD\r\n")


class Archive(DBTestCase):
    def setUp(self):
        super().setUp()
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)

    def v1_archive(self):
        """An archive as v1 left it."""
        (self.dir / "stations.csv").write_text(V1_STATIONS)
        (self.dir / "level_50140_umberleigh.csv").write_text(
            "dateTime,value,unit,station_id,station_label\r\n"
            "2026-01-13T00:00:00Z,0.71,m,50140,Umberleigh\r\n"
            "2026-01-13T00:15:00Z,0.72,m,50140,Umberleigh\r\n")
        (self.dir / "rainfall_50199.csv").write_text(
            "dateTime,value,unit,station_id,station_label\r\n2026-01-13T00:00:00Z,0.2,mm,50199,Lapford Bowerthy\r\n")
        (self.dir / "cso_SBB00257.csv").write_text(
            "start_time,end_time,duration_min,is_ongoing\r\n"
            "2026-06-10T10:00:00.300000Z,2026-06-10T11:00:00.300000Z,60,false\r\n"
            "2026-11-20T08:00:00Z,,,true\r\n")
        (self.dir / "cso_SBB01111.csv").write_text(  # an overflow not listed today
            "start_time,end_time,duration_min,is_ongoing\r\n2026-06-10T10:00:00Z,,,true\r\n")
        (self.dir / "cso_sites.csv").write_text("id,river,lat,lon\r\n")  # one of v1's other files
        self.add_station("50140", name="Umberleigh")
        self.add_station("50199", kind="rain", name="Lapford Bowerthy", unit="mm",
                         measure="50199-rainfall-tipping_bucket_raingauge-t-15_min-mm", typical=None)
        self.add_station("50198", kind="tidal", name="Barnstaple", measure="50198-level-tidal_level-i-15_min-m")
        self.add_overflow("SBB00257")

    def test_restoring_v1s_archive(self):
        self.v1_archive()
        # A reading already held, from the Environment Agency, is kept.
        self.add_readings("50140-level-stage-i-15_min-m", [(archive.to_ts("2026-01-13T00:15:00Z"), 0.72)])
        # The server's own log has moved on since v1's last, still open, spill.
        later = archive.to_ts("2026-11-23T09:00:00Z")
        self.con.execute("INSERT INTO overflow_events (id, started, ended) VALUES ('SBB00257', ?, NULL)", (later,))
        readings, spills, skipped = archive.restore(self.con, self.dir)
        self.assertEqual((readings, spills), (2, 2))
        self.assertIn("47158", skipped)    # not a station today
        self.assertIn("50198", skipped)    # the archive holds a different series
        rows = self.con.execute("SELECT started, ended FROM overflow_events WHERE id = 'SBB00257' ORDER BY started").fetchall()
        self.assertEqual([tuple(r) for r in rows], [
            (archive.to_ts("2026-06-10T10:00:00Z"), archive.to_ts("2026-06-10T11:00:00Z")),  # fractions of seconds dropped
            (archive.to_ts("2026-11-20T08:00:00Z"), later),   # closed when the next began
            (later, None),                                   # still spilling
        ])
        self.assertEqual(int(db.get_meta(self.con, "overflow_log_started")), archive.to_ts("2026-06-03T00:00:00Z"))
        # Running it again adds nothing.
        self.assertEqual(archive.restore(self.con, self.dir)[:2], (0, 0))

    def test_an_export_carries_on_v1s_files(self):
        self.v1_archive()
        archive.restore(self.con, self.dir)
        self.add_readings("50140-level-stage-i-15_min-m", [(archive.to_ts("2026-11-23T10:00:00Z"), 1.31)])
        before = (self.dir / "level_50140_umberleigh.csv").read_text()
        archive.export(self.con, self.dir)
        after = (self.dir / "level_50140_umberleigh.csv").read_bytes().decode()
        # The same file, in v1's format, with the new reading added at the end.
        self.assertTrue(after.startswith(before.replace("\n", "\r\n") if "\r\n" not in before else before))
        self.assertTrue(after.endswith("2026-11-23T10:00:00Z,1.31,m,50140,Umberleigh\r\n"))
        stations = archive.read_csv(self.dir / "stations.csv")
        by_id = {r["id"]: r for r in stations}
        self.assertEqual(by_id["50140"]["rloi"], "3106")               # kept from v1
        self.assertEqual(by_id["47158"]["label"], "Halwill")           # no longer listed, kept
        self.assertEqual(by_id["50199"]["type"], "rainfall")
        # A second export with nothing new changes nothing.
        self.assertEqual(archive.export(self.con, self.dir), 0)

    def test_a_new_station_gets_a_file_named_as_v1_named_them(self):
        m = self.add_station("50130", name="Leehamford")
        self.add_readings(m, [(archive.to_ts("2026-11-23T10:00:00Z"), 0.4)])
        self.add_overflow("SBB00999")
        self.con.execute("INSERT INTO overflow_events VALUES ('SBB00999', ?, ?)",
                         (archive.to_ts("2026-11-22T10:00:00Z"), archive.to_ts("2026-11-22T11:30:00Z")))
        self.assertEqual(archive.export(self.con, self.dir), 3)
        self.assertTrue((self.dir / "level_50130_leehamford.csv").exists())
        spill = archive.read_csv(self.dir / "cso_SBB00999.csv")
        self.assertEqual(spill, [{"start_time": "2026-11-22T10:00:00Z", "end_time": "2026-11-22T11:30:00Z",
                                  "duration_min": "90", "is_ongoing": "false"}])

    def test_ids_that_arent_plain_ids_never_become_file_names(self):
        # The IDs come from outside feeds; the nightly push commits the files.
        m = self.add_station("../../serve", name="Nowhere")
        self.add_readings(m, [(1_793_361_600, 0.5)])
        self.con.execute("INSERT INTO overflow_events VALUES ('../X', 1793361600, 1793365200)")
        self.con.commit()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "archive"
            archive.export(self.con, out)
            names = sorted(p.name for p in Path(tmp).rglob("*") if p.is_file())
            self.assertNotIn("serve", " ".join(names))
            self.assertFalse(any("X" in n for n in names if n.startswith("cso_")))
            self.assertTrue(all(p.parent == out for p in Path(tmp).rglob("*.csv")))

    def test_no_archive_restores_nothing(self):
        self.assertEqual(archive.restore(self.con, self.dir), (0, 0, {}))


if __name__ == "__main__":
    unittest.main()
