"""The overlay builder: tracing the catchment, naming rivers, sorting railways and roads."""

import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "fetch_geodata", Path(__file__).resolve().parent.parent / "scripts" / "fetch_geodata.py")
fg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fg)


def square(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def grid(rings, y0=0.0, y1=0.01):
    rows = round((y1 - y0) / fg.GRID_DY)
    spans = fg.Spans(rings, y0, rows)
    return [spans.row(j) for j in range(rows)], y0


class SpanArithmetic(unittest.TestCase):
    def test_union_joins_overlapping_and_touching_spans(self):
        self.assertEqual(fg.union_spans([(0, 1), (3, 4)], [(1, 2), (5, 6)]), [(0, 2), (3, 4), (5, 6)])

    def test_intersection(self):
        self.assertEqual(fg.intersect_spans([(0, 2), (3, 6)], [(1, 4)]), [(1, 2), (3, 4)])
        self.assertEqual(fg.intersect_spans([(0, 1)], [(2, 3)]), [])

    def test_xor_is_what_one_row_covers_and_the_other_doesnt(self):
        self.assertEqual(fg.xor_spans([(0, 4)], [(1, 2)]), [(0, 1), (2, 4)])
        self.assertEqual(fg.xor_spans([(0, 1)], [(0, 1)]), [])


class Tracing(unittest.TestCase):
    def test_a_square_traces_as_one_ring_of_four_corners(self):
        rows, y0 = grid([square(0.001, 0.002, 0.005, 0.008)])
        rings = fg.trace(rows, y0)
        self.assertEqual(len(rings), 1)
        self.assertEqual(len(rings[0]), 5)  # four corners, closed
        xs, ys = {p[0] for p in rings[0]}, {round(p[1], 6) for p in rings[0]}
        self.assertEqual(xs, {0.001, 0.005})
        self.assertEqual(ys, {0.002, 0.008})

    def test_polygons_sharing_an_edge_trace_as_one_outline(self):
        rows, y0 = grid([square(0.001, 0.002, 0.003, 0.008), square(0.003, 0.002, 0.006, 0.008)])
        rings = fg.trace(rows, y0)
        self.assertEqual(len(rings), 1)
        self.assertAlmostEqual(fg.area_km2(rings[0]), fg.area_km2(square(0.001, 0.002, 0.006, 0.008)), places=6)

    def test_separate_areas_trace_as_separate_rings(self):
        rows, y0 = grid([square(0.001, 0.001, 0.002, 0.003), square(0.004, 0.005, 0.006, 0.008)])
        self.assertEqual(len(fg.trace(rows, y0)), 2)

    def test_an_l_shape_keeps_its_inside_corner(self):
        l_shape = [(0.001, 0.001), (0.005, 0.001), (0.005, 0.003), (0.003, 0.003), (0.003, 0.007),
                   (0.001, 0.007), (0.001, 0.001)]
        rows, y0 = grid([l_shape])
        rings = fg.trace(rows, y0)
        self.assertEqual(len(rings), 1)
        self.assertEqual(len(rings[0]), 7)
        self.assertAlmostEqual(fg.area_km2(rings[0]), fg.area_km2(l_shape), places=6)


class Rivers(unittest.TestCase):
    def test_names(self):
        self.assertEqual(fg.river_name("River Lynher or St Germans River"), "River Lynher")
        self.assertEqual(fg.river_name("Yeo"), "River Yeo")
        self.assertEqual(fg.river_name("River Taw"), "River Taw")

    def test_each_river_yeo_is_named_after_the_one_it_is_nearest(self):
        places = fg.SAME_NAME["River Yeo"]
        self.assertEqual(fg.nearest_name([(-4.02, 51.12), (-4.01, 51.09)], places), "River Yeo")      # above Barnstaple
        self.assertEqual(fg.nearest_name([(-3.80, 50.80), (-3.81, 50.86)], places), "Lapford Yeo")
        self.assertEqual(fg.nearest_name([(-3.70, 51.05), (-3.74, 51.02)], places), "Molland Yeo")


class Railways(unittest.TestCase):
    def way(self, ref, *pts, role=""):
        return {"type": "way", "ref": ref, "role": role, "geometry": [{"lon": x, "lat": y} for x, y in pts]}

    def test_track_on_two_routes_is_drawn_once_on_the_tarka_line(self):
        tarka, dartmoor = fg.RAIL_ROUTES  # relation ids, Tarka first
        relations = [
            {"id": dartmoor, "members": [self.way(1, (0, 0), (1, 0)), self.way(3, (1, 0), (1, 1)),
                                         {"type": "node", "ref": 9, "role": "stop"}]},
            {"id": tarka, "members": [self.way(1, (0, 0), (1, 0)), self.way(2, (1, 0), (2, 0), role="forward")]},
        ]
        lines = fg.route_lines(relations)
        self.assertEqual(lines["Tarka Line"], [[(0, 0), (1, 0)], [(1, 0), (2, 0)]])
        self.assertEqual(lines["Dartmoor Line"], [[(1, 0), (1, 1)]])

    def test_stations_are_kept_only_near_the_lines(self):
        line = [[(-3.98, 50.99), (-3.98, 51.01)]]
        self.assertLess(fg.metres_to_line((-3.981, 51.00), line, 250), 100)        # ~70 m off
        self.assertEqual(fg.metres_to_line((-3.97, 51.00), line, 250), fg.math.inf)  # ~700 m off


class Outline(unittest.TestCase):
    def rel(self, *ways):
        return {"members": [{"type": "way", "ref": ref, "role": "outer",
                             "geometry": [{"lon": x, "lat": y} for x, y in pts]} for ref, pts in ways]}

    def test_borders_shared_by_neighbouring_areas_drop_out(self):
        # Two squares side by side share the way at x = 1.
        left = self.rel((1, [(0, 0), (1, 0)]), (2, [(1, 0), (1, 1)]), (3, [(1, 1), (0, 1), (0, 0)]))
        right = self.rel((2, [(1, 0), (1, 1)]), (4, [(1, 1), (2, 1), (2, 0), (1, 0)]))
        rings = fg.outline_of([left, right])
        self.assertEqual(len(rings), 1)
        ring = rings[0]
        self.assertEqual(ring[0], ring[-1])
        # The outer corners, plus the two points along its edges where the squares met.
        self.assertEqual(set(ring), {(0, 0), (1, 0), (2, 0), (2, 1), (1, 1), (0, 1)})


class Roads(unittest.TestCase):
    def test_major_roads(self):
        self.assertEqual(fg.major_ref("A39"), "A39")
        self.assertEqual(fg.major_ref("A377"), "A377")
        self.assertEqual(fg.major_ref("A3124"), None)
        self.assertEqual(fg.major_ref("B3227;A361"), "A361")
        self.assertEqual(fg.major_ref("A3125"), None)


if __name__ == "__main__":
    unittest.main()
