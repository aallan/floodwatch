"""floodwatch_mcp.tools: the nine tools, against trimmed copies of the site's JSON."""

import json
import re
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import stdmcp
from stdmcp.tools import validate
from floodwatch_mcp import text
from floodwatch_mcp.site import NotFound
from floodwatch_mcp.tools import INSTRUCTIONS, TOOLS, make_tools

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "mcp"
NOW = 1_795_740_000  # Fri 27 Nov 2026 00:40 UTC
ISO = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")


def load(name):
    return json.loads((FIXTURES / name).read_text())


class FixtureSite:
    """Serves the fixtures as the site would, 404s included."""

    def __init__(self):
        self.paths = []
        self.readings = load("readings.json")

    def json(self, path):
        self.paths.append(path)
        url = urlsplit(path)
        parts = url.path.strip("/").split("/")
        if parts[0] == "data":
            return load(parts[1])
        if parts[:2] == ["api", "stations"] and parts[3] == "readings":
            if parts[2] != self.readings["id"]:
                raise NotFound("no such station")
            days = int(parse_qs(url.query)["days"][0])
            return {**self.readings, "days": days}
        if parts[:3] == ["api", "forecast", "rain"]:
            if parts[3] != "50106":
                raise NotFound("no such rain gauge")
            return load("rain_forecast.json")
        if parts[:3] == ["api", "forecast", "flow"]:
            if parts[3] != "50140":
                raise NotFound("no flow forecast for this gauge")
            return load("flow_forecast.json")
        if parts[:2] == ["api", "overflows"]:
            if parts[2] != "SBB00054":
                raise NotFound("no such overflow")
            return load("overflow_detail.json")
        raise NotFound("not found")


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.site = FixtureSite()
        self.tools = {t.name: t for t in make_tools(self.site, clock=lambda: NOW)}

    def call(self, name, **args):
        """Call a tool as the protocol layer does: validate, fill defaults, then call."""
        tool = self.tools[name]
        result = tool.handler(**validate(tool.input_schema, args))
        json.dumps(result)  # must be JSON as it stands
        return result

    def error(self, name, **args):
        with self.assertRaises(stdmcp.ToolError) as cm:
            self.call(name, **args)
        return str(cm.exception)

    # ------------------------------------------------------------ the registry

    def test_tool_order_is_fixed(self):
        names = ["list_stations", "conditions", "flood_warnings", "station_history", "rain_forecast",
                 "flow_forecast", "storm_overflows", "drought", "power_cuts"]
        self.assertEqual([t.name for t in TOOLS], names)
        self.assertEqual(list(self.tools), names)

    def test_schemas(self):
        pattern = "[A-Za-z0-9_-]{1,24}"
        cond = self.tools["conditions"].input_schema
        self.assertEqual(cond["properties"]["station_id"]["pattern"], pattern)
        self.assertEqual(cond["properties"]["kind"]["enum"], ["level", "tidal", "rain"])
        self.assertEqual(cond.get("required", []), [])
        hist = self.tools["station_history"].input_schema
        self.assertEqual(hist["required"], ["station_id"])
        self.assertEqual(hist["properties"]["days"], {"type": "integer", "minimum": 1, "maximum": 30, "default": 7,
                                                      "description": hist["properties"]["days"]["description"]})
        for name in ("rain_forecast", "flow_forecast"):
            schema = self.tools[name].input_schema
            self.assertEqual(schema["required"], ["station_id"])
            self.assertEqual(schema["properties"]["station_id"]["pattern"], pattern)
        ov = self.tools["storm_overflows"].input_schema
        self.assertEqual(ov["properties"]["state"]["enum"], ["spilling", "recent", "quiet", "offline"])
        self.assertEqual(ov["properties"]["overflow_id"]["pattern"], pattern)
        for name in ("list_stations", "flood_warnings", "drought", "power_cuts"):
            self.assertEqual(self.tools[name].input_schema,
                             {"type": "object", "properties": {}, "additionalProperties": False})
        for t in TOOLS:
            self.assertEqual(t.input_schema["type"], "object")
            self.assertIs(t.input_schema["additionalProperties"], False)

    def test_descriptions_are_plain(self):
        for t in TOOLS:
            self.assertTrue(t.title and t.description, t.name)
            self.assertNotIn("\u2014", t.description + t.title, t.name)
            self.assertLessEqual(t.description.count(". "), 2, t.name)

    def test_every_result_has_generated_and_attribution(self):
        calls = [("list_stations", {}), ("conditions", {}), ("flood_warnings", {}),
                 ("station_history", {"station_id": "50140"}), ("rain_forecast", {"station_id": "50106"}),
                 ("flow_forecast", {"station_id": "50140"}), ("storm_overflows", {}),
                 ("storm_overflows", {"overflow_id": "SBB00054"}), ("drought", {}), ("power_cuts", {})]
        for name, args in calls:
            with self.subTest(name=name, args=args):
                r = self.call(name, **args)
                self.assertRegex(r["generated"], ISO)
                self.assertIsInstance(r["attribution"], str)
                self.assertTrue(r["attribution"])

    def test_instructions_name_no_third_party_strings(self):
        names = [s["name"] for s in load("live.json")["stations"]]
        names += [o["name"] for o in load("overflows.json")["overflows"] if o.get("name")]
        names += [w["area"] for w in load("warnings.json")["warnings"]]
        self.assertTrue(names)
        for name in names:
            self.assertNotIn(name.lower(), INSTRUCTIONS.lower())
        self.assertIs(INSTRUCTIONS, text.INSTRUCTIONS)
        for needed in ("North Devon", "not an official warning service", "Environment Agency", "flood_warnings",
                       "Europe/London", "15 minutes", "stale", "approach", "30%", "attribution", "level_m",
                       "rain_mm", "flow_m3s"):
            self.assertIn(needed, INSTRUCTIONS)
        self.assertNotIn("\u2014", INSTRUCTIONS)

    # ------------------------------------------------------------ gauges

    def test_list_stations(self):
        r = self.call("list_stations")
        self.assertEqual(r["generated"], "2026-11-23T19:55:00+00:00")
        self.assertEqual(r["attribution"], text.READINGS)
        by = {s["id"]: s for s in r["stations"]}
        self.assertEqual(len(by), 8)
        self.assertEqual(by["50140"], {
            "id": "50140", "name": "Umberleigh", "kind": "level", "river": "River Taw",
            "lat": 50.99542, "lon": -3.98509, "unit": "m", "typical_range_m": [0.181, 2.8],
            "flow_forecast": True})
        self.assertFalse(by["50132"]["flow_forecast"])
        self.assertEqual(by["50198"]["kind"], "tidal")
        self.assertNotIn("typical_range_m", by["50198"])
        self.assertEqual(by["50106"]["kind"], "rain")
        self.assertNotIn("river", by["50106"])

    def test_conditions(self):
        r = self.call("conditions")
        self.assertEqual(r["counts"], {"high": 1, "approach": 1, "rising": 2, "stale": 1})
        by = {s["id"]: s for s in r["stations"]}
        self.assertEqual(len(by), 8)
        self.assertEqual(by["50132"], {
            "id": "50132", "name": "Newnham Bridge", "kind": "level", "river": "River Taw",
            "time": "2026-11-23T19:45:00+00:00", "level_m": 2.71, "unit": "m", "trend": "rising",
            "state": "high", "stale": False})
        self.assertEqual(by["50125"]["state"], "stale")
        self.assertTrue(by["50125"]["stale"])
        self.assertIsNone(by["50125"]["trend"])
        self.assertEqual(by["50189"]["state"], "approach")
        self.assertEqual(by["50198"]["state"], "tidal")
        self.assertEqual(by["50198"]["level_m"], 1.989)
        self.assertEqual(by["50106"]["rain_mm_1h"], 0.3)
        self.assertEqual(by["50106"]["rain_mm_24h"], 6.0)
        self.assertEqual(by["50106"]["state"], "raining")
        self.assertNotIn("level_m", by["50106"])

    def test_conditions_filters(self):
        r = self.call("conditions", kind="rain")
        self.assertEqual({s["id"] for s in r["stations"]}, {"50106", "E82120"})
        self.assertEqual(r["counts"], {"high": 0, "approach": 0, "rising": 0, "stale": 0})
        r = self.call("conditions", station_id="50140")
        self.assertEqual([s["id"] for s in r["stations"]], ["50140"])
        self.assertEqual(r["counts"]["rising"], 1)

    def test_unknown_station(self):
        msg = "No gauge with ID nope. list_stations gives the IDs."
        self.assertEqual(self.error("conditions", station_id="nope"), msg)
        self.assertEqual(self.error("station_history", station_id="nope"), msg)
        self.assertEqual(self.error("rain_forecast", station_id="nope"), msg)
        self.assertEqual(self.error("flow_forecast", station_id="nope"), msg)

    def test_bad_arguments_are_refused_before_the_handler(self):
        for name, args in [("station_history", {"station_id": "../x"}), ("station_history", {"station_id": "50140",
                                                                                              "days": 31}),
                           ("conditions", {"kind": "river"}), ("storm_overflows", {"state": "leaking"}),
                           ("drought", {"x": 1})]:
            with self.assertRaises(ValueError):
                validate(self.tools[name].input_schema, args)

    # ------------------------------------------------------------ warnings

    def test_flood_warnings(self):
        r = self.call("flood_warnings")
        self.assertEqual(r["generated"], "2026-11-23T20:08:20+00:00")  # the older of the two files
        self.assertIn(text.FLOOD_WARNINGS, r["attribution"])
        self.assertIn(text.WEATHER_WARNINGS, r["attribution"])
        [w] = r["flood_warnings"]
        self.assertEqual(w["severity"], "Flood warning")
        self.assertEqual(w["severity_level"], 2)
        self.assertEqual(w["area"], "River Taw at Umberleigh")
        self.assertEqual(w["since"], "2026-11-23T16:06:40+00:00")
        self.assertNotIn("geometry", w)
        [m] = r["weather_warnings"]
        self.assertEqual(m["level"], "Yellow")
        self.assertEqual(m["weather"], "rain")
        self.assertEqual(m["from"], "2026-11-27T06:00:00+00:00")
        self.assertNotIn("image", m)

    # ------------------------------------------------------------ history

    def test_station_history(self):
        r = self.call("station_history", station_id="50140")
        self.assertIn("/api/stations/50140/readings?days=7", self.site.paths)
        self.assertEqual(r["attribution"], text.READINGS)
        self.assertEqual(r["station"], {"id": "50140", "name": "Umberleigh", "kind": "level", "unit": "m"})
        self.assertEqual(r["days"], 7)
        self.assertEqual(r["typical_range_m"], [0.181, 2.8])
        self.assertEqual(r["record_high_m"], 5.003)
        self.assertEqual(r["interval"], "15 minutes")
        self.assertEqual(len(r["readings"]), 8)
        self.assertEqual(r["readings"][-1], {"time": "2026-11-23T19:45:00+00:00", "level_m": 1.201})

    def test_station_history_thins_beyond_seven_days(self):
        start = 1_795_132_800  # a UK midnight
        self.site.readings = {**self.site.readings, "readings": [[start + i * 900, i / 100] for i in range(12)]}
        r = self.call("station_history", station_id="50140", days=8)
        self.assertIn("/api/stations/50140/readings?days=8", self.site.paths)
        self.assertEqual(r["interval"], "hourly")
        # The last reading in each hour.
        self.assertEqual([x["level_m"] for x in r["readings"]], [0.03, 0.07, 0.11])
        self.assertEqual(r["readings"][0]["time"], "2026-11-20T00:45:00+00:00")

    def test_station_history_of_rain_adds_up_each_hour(self):
        live = load("live.json")
        self.site.readings = {"id": "50106", "kind": "rain", "name": "South Tawton", "unit": "mm", "typical": None,
                              "record": None, "days": 7, "bucket": None, "first": None,
                              "readings": [[1_795_132_800 + i * 900, 0.2] for i in range(8)]}
        self.assertIn("50106", {s["id"] for s in live["stations"]})
        r = self.call("station_history", station_id="50106", days=10)
        self.assertEqual(r["readings"], [{"time": "2026-11-20T00:00:00+00:00", "rain_mm": 0.8},
                                         {"time": "2026-11-20T01:00:00+00:00", "rain_mm": 0.8}])
        self.assertNotIn("typical_range_m", r)
        r = self.call("station_history", station_id="50106")
        self.assertEqual(len(r["readings"]), 8)
        self.assertEqual(r["readings"][0], {"time": "2026-11-20T00:00:00+00:00", "rain_mm": 0.2})

    def test_station_history_passes_the_sites_own_buckets(self):
        start = 1_795_132_800
        self.site.readings = {**self.site.readings, "bucket": 3600,
                              "readings": [[start + i * 3600, 1.0] for i in range(3)]}
        r = self.call("station_history", station_id="50140", days=30)
        self.assertEqual(r["interval"], "hourly")
        self.assertEqual(len(r["readings"]), 3)

    def test_thirty_days_fits_the_result_limit(self):
        start = 1_795_132_800 - 30 * 86400
        self.site.readings = {**self.site.readings, "days": 30, "bucket": None,
                              "readings": [[start + i * 900, 1.234 + i / 10000] for i in range(30 * 96)]}
        r = self.call("station_history", station_id="50140", days=30)
        self.assertEqual(len(r["readings"]), 30 * 24)
        self.assertLess(len(json.dumps(r, ensure_ascii=False)), 100_000)

    # ------------------------------------------------------------ forecasts

    def test_rain_forecast(self):
        r = self.call("rain_forecast", station_id="50106")
        self.assertEqual(r["attribution"], text.RAIN_FORECAST)
        self.assertEqual(r["generated"], "2026-11-27T00:40:00+00:00")
        self.assertEqual(r["station"], {"id": "50106", "name": "South Tawton"})
        self.assertEqual(len(r["hours"]), 6)
        self.assertEqual(r["hours"][0], {"time": "2026-11-27T11:00:00+00:00", "rain_mm": 0.2, "probability_pct": 100})
        self.assertEqual(r["total_rain_mm"], 1.6)

    def test_rain_forecast_wants_a_rain_gauge(self):
        self.assertEqual(self.error("rain_forecast", station_id="50140"),
                         "50140 is a river level gauge; rain_forecast needs a rain gauge. "
                         "list_stations shows each gauge's kind.")
        self.assertEqual(self.error("rain_forecast", station_id="50198"),
                         "50198 is a tidal gauge; rain_forecast needs a rain gauge. "
                         "list_stations shows each gauge's kind.")

    def test_flow_forecast(self):
        r = self.call("flow_forecast", station_id="50140")
        self.assertEqual(r["attribution"], text.FLOW_FORECAST)
        self.assertEqual(r["station"], {"id": "50140", "name": "Umberleigh"})
        self.assertEqual(r["river"], "River Taw")
        self.assertEqual(r["normal_flow_m3s"], 18.3)
        self.assertEqual(r["high_flow_m3s"], 41.97)
        self.assertEqual(r["measured"], {"time": "2026-11-27T10:15:00+00:00", "flow_m3s": 21.018})
        self.assertTrue(r["scaled_to_measured"])
        # The scaled days, as the chart shows them, not the model's own.
        self.assertEqual(len(r["days"]), 6)
        self.assertEqual(r["days"][2], {"date": "2026-11-27", "flow_m3s": 19.42, "ensemble_min_m3s": 19.42,
                                        "ensemble_max_m3s": 19.58, "forecast": True})
        self.assertFalse(r["days"][1]["forecast"])

    def test_flow_forecast_names_the_gauges_that_have_one(self):
        self.assertEqual(self.error("flow_forecast", station_id="50132"),
                         "50132 has no flow forecast. Gauges with one: 50140 (Umberleigh).")

    # ------------------------------------------------------------ overflows

    def test_storm_overflows(self):
        r = self.call("storm_overflows")
        self.assertEqual(r["attribution"], text.OVERFLOWS)
        self.assertEqual(r["generated"], "2026-11-23T20:08:49+00:00")
        self.assertEqual(r["counts"], {"spilling": 1, "recent": 1, "quiet": 1, "offline": 1})
        by = {o["id"]: o for o in r["overflows"]}
        self.assertEqual(by["SBB00054"], {"id": "SBB00054", "name": "Ashreigny WWTW CSO",
                                          "water": "Trib of Mully Brook", "state": "spilling", "at_works": True,
                                          "since": "2026-11-16T22:37:30+00:00", "last_spill_ended": None})
        self.assertIsNotNone(by["SBB00044"]["last_spill_ended"])
        r = self.call("storm_overflows", state="spilling")
        self.assertEqual([o["id"] for o in r["overflows"]], ["SBB00054"])
        self.assertEqual(r["counts"]["quiet"], 1)  # counts are over them all

    def test_storm_overflow_detail(self):
        r = self.call("storm_overflows", overflow_id="SBB00054")
        self.assertIn(text.OVERFLOWS, r["attribution"])
        self.assertIn(text.OVERFLOW_ANNUAL, r["attribution"])
        o = r["overflow"]
        self.assertEqual(o["state"], "spilling")
        self.assertEqual(o["asset_type"], "Inlet SO at WwTW")
        self.assertEqual(o["spills_last_30_days"][-1], {"start": "2026-11-16T22:37:30+00:00", "end": None})
        self.assertEqual(o["annual"][-1], {"year": 2025, "spill_hours": 1511.3, "spills": 167})
        self.assertEqual(o["log_started"], "2026-06-03T01:00:00+01:00")

    def test_unknown_overflow(self):
        self.assertEqual(self.error("storm_overflows", overflow_id="SBB99999"),
                         "No overflow with ID SBB99999. storm_overflows without arguments lists them.")

    # ------------------------------------------------------------ the rest

    def test_drought(self):
        r = self.call("drought")
        self.assertEqual(r["attribution"], text.DROUGHT)
        self.assertEqual(r["report"]["period"], "13 to 19 November 2026")
        self.assertEqual(r["report"]["published"], "2026-11-20T15:24:16+00:00")
        self.assertEqual([s["stage"] for s in r["stages"]], ["Severe drought", "Drought"])
        self.assertEqual(r["hosepipe_bans"], ["South West Water – whole company area, excluding Bournemouth"])

    def test_power_cuts(self):
        r = self.call("power_cuts")
        self.assertEqual(r["attribution"], text.POWER_CUTS)
        self.assertEqual(r["updated"], "2026-11-23T20:05:00+00:00")
        [c] = r["power_cuts"]
        self.assertEqual(c["place"], "Parracombe")
        self.assertEqual(c["customers_off"], 28)
        self.assertEqual(c["estimated_restoration"], "2026-11-23T21:40:00+00:00")
        self.assertEqual(c["postcodes"], ["EX35 6HW", "EX35 6EQ"])

    def test_site_errors_pass_through(self):
        class Down:
            def json(self, path):
                raise stdmcp.ToolError("Floodwatch is briefly unavailable; try again in a minute.")
        tools = {t.name: t for t in make_tools(Down())}
        with self.assertRaisesRegex(stdmcp.ToolError, "briefly unavailable"):
            tools["drought"].handler()


if __name__ == "__main__":
    unittest.main()
