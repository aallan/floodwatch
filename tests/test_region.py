"""Which positions belong to the catchment: inside it, or near it and nearer to it than to a neighbour."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from monitor import region


def fc(*rings):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {}, "geometry": {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}}]}


# The catchment, a square about 7 km across, and a neighbour beside it to the
# west with a gap of about 1.4 km between them, like the estuary between the
# Taw's bank and the Torridge's. A neighbour to the north touches it, like
# the Exmoor coast over the watershed.
TAW = [[-3.90, 50.90], [-3.80, 50.90], [-3.80, 50.96], [-3.90, 50.96], [-3.90, 50.90]]
TORRIDGE = [[-4.02, 50.90], [-3.92, 50.90], [-3.92, 50.96], [-4.02, 50.96], [-4.02, 50.90]]
EXMOOR = [[-3.90, 50.96], [-3.80, 50.96], [-3.80, 51.02], [-3.90, 51.02], [-3.90, 50.96]]


class Membership(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        boundary, neighbours = Path(d.name) / "catchment.geojson", Path(d.name) / "neighbours.geojson"
        boundary.write_text(json.dumps(fc(TAW)))
        neighbours.write_text(json.dumps(fc(TORRIDGE, EXMOOR)))
        for name, path in (("BOUNDARY", boundary), ("NEIGHBOURS", neighbours)):
            patcher = mock.patch.object(region, name, path)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.belongs = region.membership(1500)

    def test_inside(self):
        self.assertTrue(self.belongs(-3.85, 50.93))

    def test_inside_a_neighbour_is_theirs(self):
        self.assertFalse(self.belongs(-3.97, 50.93))
        self.assertFalse(self.belongs(-3.85, 50.99))

    def test_in_the_gap_it_goes_to_whichever_is_nearer(self):
        # Between the two, 350 m from the catchment and 1 km from the neighbour.
        self.assertTrue(self.belongs(-3.905, 50.93))
        # Within 1.5 km of the catchment, but nearer the neighbour.
        self.assertFalse(self.belongs(-3.915, 50.93))

    def test_too_far_off_belongs_to_nobody(self):
        self.assertFalse(self.belongs(-3.85, 50.85))     # 5 km south, beside nothing

    def test_without_a_neighbours_file_near_enough_is_enough(self):
        with mock.patch.object(region, "NEIGHBOURS", Path("/nonexistent/neighbours.geojson")):
            belongs = region.membership(1500)
        self.assertTrue(belongs(-3.915, 50.93))
        self.assertFalse(belongs(-3.85, 50.85))


if __name__ == "__main__":
    unittest.main()
