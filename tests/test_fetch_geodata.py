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
        self.assertEqual(fg.major_ref("A30"), "A30")
        self.assertEqual(fg.major_ref("A377"), "A377")
        self.assertEqual(fg.major_ref("A39"), None)
        self.assertEqual(fg.major_ref("A361"), None)
        self.assertEqual(fg.major_ref("B3227;A377"), "A377")

    def test_the_a30_stops_east_of_exeter(self):
        line = [(-3.6, 50.7), (-3.5, 50.7), (-3.48, 50.71), (-3.3, 50.75)]
        self.assertEqual(fg.west_of([line], -3.49), [[(-3.6, 50.7), (-3.5, 50.7)]])


class Gaps(unittest.TestCase):
    def test_an_unnamed_way_between_two_stretches_of_a_river_joins_it(self):
        by_name = {"River Yeo": [[(0, 0), (1, 0)], [(2, 0), (3, 0)]], "": [[(5, 5), (6, 6)]]}
        streams = [("", [(1, 0), (1.5, 0.1), (2, 0)]), ("Some Brook", [(1, 0), (2, 0)]), ("", [(9, 9), (8, 8)])]
        fg.bridge_gaps(by_name, streams)
        self.assertIn([(1, 0), (1.5, 0.1), (2, 0)], by_name["River Yeo"])
        self.assertEqual(streams, [("Some Brook", [(1, 0), (2, 0)]), ("", [(9, 9), (8, 8)])])
        self.assertEqual(by_name[""], [[(5, 5), (6, 6)]])

    def test_a_chain_of_unnamed_ways_joined_part_way_along(self):
        # As on the Little Dart: the gap runs down one unnamed way, onto
        # another part-way along, and on to where the named river resumes.
        by_name = {"Little Dart River": [[(0, 0), (1, 0)], [(4, 0), (5, 0)]]}
        streams = [("", [(1, 0), (2, 0)]),
                   ("", [(2, 5), (2, 1), (2, 0), (3, 0)]),   # joined at (2, 0)
                   ("", [(3, 0), (4, 0)])]
        fg.bridge_gaps(by_name, streams)
        self.assertEqual(by_name["Little Dart River"][2:], [[(1, 0), (2, 0)], [(2, 0), (3, 0)], [(3, 0), (4, 0)]])
        self.assertEqual(streams, [("", [(2, 5), (2, 1), (2, 0)])])  # the stretch above the join stays a stream

    def test_a_gap_too_many_ways_long_isnt_bridged(self):
        n = fg.MAX_BRIDGE_WAYS + 1
        by_name = {"River Yeo": [[(0, 0), (1, 0)], [(n + 1, 0), (n + 2, 0)]]}
        streams = [("", [(i, 0), (i + 1, 0)]) for i in range(1, n + 1)]
        fg.bridge_gaps(by_name, streams)
        self.assertEqual(len(by_name["River Yeo"]), 2)



class Lines(unittest.TestCase):
    def test_lines_join_end_to_start_and_keep_their_direction(self):
        a, b = [(0, 0), (1, 0)], [(1, 0), (2, 0)]
        self.assertEqual(fg.merge_lines([b, a]), [[(0, 0), (1, 0), (2, 0)]])
        # Two lines that meet end to end, both flowing in: not joined, since
        # one would have to run backwards.
        self.assertEqual(len(fg.merge_lines([[(0, 0), (1, 0)], [(2, 0), (1, 0)]])), 2)

    def test_a_river_is_cut_where_it_first_crosses_the_coastline(self):
        coast = fg.Coastline([{"geometry": [{"lon": 2, "lat": -1}, {"lon": 2, "lat": 1}]}])
        line = [(0, 0), (1, 0), (3, 0), (4, 0)]
        self.assertEqual(coast.cut(line), [(0, 0), (1, 0), (2.0, 0.0)])
        self.assertEqual(coast.cut([(0, 5), (1, 5)]), [(0, 5), (1, 5)])   # never crosses it

    def test_touches_the_catchment(self):
        from monitor.geo import LandMask
        land = LandMask([[(0, 50), (0.1, 50), (0.1, 50.1), (0, 50.1), (0, 50)]], 0)
        self.assertTrue(fg.touches([[(0.05, 50.05), (0.5, 50.05)]], land))
        self.assertFalse(fg.touches([[(0.5, 50.05), (0.6, 50.05)]], land))


# Near 51 degrees north, where 0.001 degrees of latitude is about 110 m.
X, Y = -4.0, 51.0


def at(dx, dy):
    """A point dx, dy thousandths of a degree from (X, Y)."""
    return (round(X + dx / 1000, 6), round(Y + dy / 1000, 6))


class Mouths(unittest.TestCase):
    MOUTH = at(10, 0)

    def test_the_line_that_reaches_the_mouth_ends_at_its_nearest_point(self):
        line = [at(0, 0), at(5, 0), at(10, 1), at(15, 3), at(20, 5)]   # passes 110 m from the mouth
        self.assertEqual(fg.cut_at_mouth(line, self.MOUTH, set()), line[:3])

    def test_a_tidal_line_that_never_reaches_the_mouth_is_below_it_and_dropped(self):
        estuary = [at(25, 5), at(30, 6)]
        self.assertEqual(fg.cut_at_mouth(estuary, self.MOUTH, set(estuary)), [])

    def test_any_other_line_far_from_the_mouth_is_left_whole(self):
        headwater = [at(-40, -30), at(-35, -28)]
        self.assertEqual(fg.cut_at_mouth(headwater, self.MOUTH, set()), headwater)


class GaugeStreams(unittest.TestCase):
    def setUp(self):
        # A river running east along y = 0, and a stream running down to it
        # from the north along x = 5: three ways, joined end to start.
        self.by_name = {"River Taw": [[at(0, 0), at(5, 0), at(10, 0)]]}
        self.upper = ("", [at(5, 20), at(5, 12)])
        self.middle = ("", [at(5, 12), at(5, 6)])
        self.lower = ("", [at(5, 6), at(5, 0)])
        self.elsewhere = ("", [at(50, 50), at(51, 51)])

    def test_a_gauge_on_an_unnamed_stream_draws_it_down_to_the_river_under_the_agencys_name(self):
        streams = [self.upper, self.middle, self.lower, self.elsewhere]
        names = fg.promote_gauge_streams(self.by_name, streams, [(*at(5.2, 9), "Landkey Brook")])
        self.assertEqual(names, {"Landkey Brook"})
        self.assertCountEqual(self.by_name["Landkey Brook"], [self.middle[1], self.lower[1], self.upper[1]])
        self.assertEqual(streams, [self.elsewhere])

    def test_a_gauge_already_on_a_river_promotes_nothing(self):
        streams = [self.lower, self.elsewhere]
        names = fg.promote_gauge_streams(self.by_name, streams, [(*at(5, 0.2), "River Taw")])
        self.assertEqual(names, set())
        self.assertEqual(streams, [self.lower, self.elsewhere])

    def test_a_gauge_far_from_any_stream_promotes_nothing(self):
        streams = [self.middle, self.lower]
        self.assertEqual(fg.promote_gauge_streams(self.by_name, streams, [(*at(30, 30), "Somewhere")]), set())

    def test_osms_name_wins_and_brings_the_rest_of_the_stream_with_it(self):
        named_lower = ("Bradiford Water", self.lower[1])
        detached = ("Bradiford Water", [at(70, 70), at(71, 71)])
        streams = [self.middle, named_lower, detached]
        fg.promote_gauge_streams(self.by_name, streams, [(*at(5.2, 3), "Bradiford Stream")])
        self.assertIn(detached[1], self.by_name["Bradiford Water"])
        self.assertNotIn("Bradiford Stream", self.by_name)

    def test_upstream_it_follows_the_longest_branch_and_stops_after_a_few_kilometres(self):
        short = ("", [at(4, 13), at(5, 12)])       # joins at the top of the middle way
        streams = [self.upper, short, self.middle, self.lower]
        fg.promote_gauge_streams(self.by_name, streams, [(*at(5.2, 9), "Brook")])
        self.assertIn(self.upper[1], self.by_name["Brook"])
        self.assertEqual(streams, [short])
        far = [("", [at(5, 12 + 10 * (k + 1)), at(5, 12 + 10 * k)]) for k in range(6)]   # 1.1 km each
        streams = far + [self.middle, self.lower]
        by_name = {"River Taw": [[at(0, 0), at(5, 0), at(10, 0)]]}
        fg.promote_gauge_streams(by_name, streams, [(*at(5.2, 9), "Long Brook")])
        self.assertEqual(len(streams), 3)   # three ways, 3.3 km, then it stops

    def test_one_gauges_chain_stops_where_it_meets_anothers_stream(self):
        tributary = ("", [at(-5, 6), at(5, 6)])     # joins the stream at the top of the lower way
        streams = [self.middle, self.lower, tributary]
        fg.promote_gauge_streams(self.by_name, streams, [(*at(5.2, 3), "Main Brook"), (*at(0, 6.2), "Side Brook")])
        self.assertCountEqual(self.by_name["Main Brook"], [self.lower[1], self.middle[1]])
        self.assertEqual(self.by_name["Side Brook"], [tributary[1]])


if __name__ == "__main__":
    unittest.main()
