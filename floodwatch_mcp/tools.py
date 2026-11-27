"""The nine tools: the website's own JSON, reshaped for agents.

Every answer comes from what the map shows, read through Site. Times become
ISO 8601 in UK time, units go into field names, and each result says when
Floodwatch refreshed the data and whose it is.
"""

import time
from datetime import datetime
from zoneinfo import ZoneInfo

from stdmcp import Tool, ToolError

from . import text
from .site import NotFound, Site

INSTRUCTIONS = text.INSTRUCTIONS
UK = ZoneInfo("Europe/London")
ID_PATTERN = "[A-Za-z0-9_-]{1,24}"
RAW_DAYS = 7          # beyond this, history is thinned to one reading an hour
KIND_NAMES = {"level": "a river level gauge", "tidal": "a tidal gauge", "rain": "a rain gauge"}
OVERFLOW_STATES = ["spilling", "recent", "quiet", "offline"]
OVERFLOW_STATUS = {1: "spilling", 0: "quiet", -1: "offline"}


def iso(ts):
    """Epoch seconds as ISO 8601 in UK time, or None."""
    return None if ts is None else datetime.fromtimestamp(ts, UK).isoformat()


def _schema(properties=None, required=()):
    schema = {"type": "object", "properties": properties or {}, "additionalProperties": False}
    if required:
        schema["required"] = list(required)
    return schema


def _id(description):
    return {"type": "string", "pattern": ID_PATTERN, "description": description}


STATION_ID = _id("A gauge ID, from list_stations.")


def _hourly(readings, rain):
    """One reading an hour: a rain gauge's total for the hour, at its start,
    and otherwise the last reading in the hour."""
    hours = {}
    for ts, value in readings:
        hour = ts // 3600 * 3600
        if rain:
            t, total = hours.get(hour, (hour, 0))
            hours[hour] = (t, total + value)
        else:
            hours[hour] = (ts, value)
    return [[t, round(v, 3)] for t, v in hours.values()]


def make_tools(site: Site, clock=time.time) -> tuple:
    """The tools, reading from site; clock gives the time now, for tests."""

    def live():
        return site.json("/data/live.json")

    def station(station_id, data=None):
        data = data or live()
        for s in data["stations"]:
            if s["id"] == station_id:
                return s
        raise ToolError(f"No gauge with ID {station_id}. list_stations gives the IDs.")

    def now_iso():
        return iso(int(clock()))

    # ---------------------------------------------------------------- gauges

    def list_stations():
        data = live()
        out = []
        for s in data["stations"]:
            entry = {"id": s["id"], "name": s["name"], "kind": s["kind"]}
            if s.get("river"):
                entry["river"] = s["river"]
            entry.update(lat=s["lat"], lon=s["lon"], unit=s.get("unit"))
            if s["kind"] == "level":
                entry["typical_range_m"] = s.get("typical")
            entry["flow_forecast"] = bool(s.get("flow"))
            out.append(entry)
        return {"generated": iso(data["generated"]), "attribution": text.READINGS, "stations": out}

    def conditions(station_id=None, kind=None):
        data = live()
        stations = [station(station_id, data)] if station_id else data["stations"]
        if kind:
            stations = [s for s in stations if s["kind"] == kind]
        out = []
        for s in stations:
            entry = {"id": s["id"], "name": s["name"], "kind": s["kind"]}
            if s.get("river"):
                entry["river"] = s["river"]
            entry["time"] = iso(s.get("ts"))
            if s["kind"] == "rain":
                entry.update(rain_mm_1h=s.get("h1"), rain_mm_24h=s.get("h24"))
            else:
                entry.update(level_m=s.get("value"), unit=s.get("unit"), trend=s.get("trend"))
            entry.update(state=s.get("state"), stale=s.get("state") == "stale")
            out.append(entry)
        counts = {
            "high": sum(s["state"] == "high" for s in out),
            "approach": sum(s["state"] == "approach" for s in out),
            "rising": sum(s.get("trend") == "rising" for s in out),
            "stale": sum(s["stale"] for s in out),
        }
        return {"generated": iso(data["generated"]), "attribution": text.READINGS, "counts": counts, "stations": out}

    def station_history(station_id, days=7):
        s = station(station_id)
        try:
            d = site.json(f"/api/stations/{station_id}/readings?days={days}")
        except NotFound:
            raise ToolError(f"No gauge with ID {station_id}. list_stations gives the IDs.") from None
        rain = d["kind"] == "rain"
        readings = d["readings"]
        if d.get("bucket"):
            interval = "hourly" if d["bucket"] == 3600 else f"every {d['bucket'] // 3600} hours"
        elif days > RAW_DAYS:
            readings, interval = _hourly(readings, rain), "hourly"
        else:
            interval = "15 minutes"
        field = "rain_mm" if rain else "level_m"
        out = {"generated": now_iso(), "attribution": text.READINGS,
               "station": {"id": d["id"], "name": d["name"], "kind": d["kind"], "unit": d["unit"]},
               "days": days}
        if d["kind"] == "level":
            out.update(typical_range_m=d.get("typical"), record_high_m=d.get("record"))
        out["interval"] = interval
        out["latest_state"] = s.get("state")
        out["readings"] = [{"time": iso(t), field: v} for t, v in readings]
        return out

    # ---------------------------------------------------------------- warnings

    def flood_warnings():
        floods, weather = site.json("/data/warnings.json"), site.json("/data/weather.json")
        return {
            "generated": iso(min(floods["generated"], weather["generated"])),
            "attribution": f"{text.FLOOD_WARNINGS} {text.WEATHER_WARNINGS}",
            "flood_warnings": [{
                "id": w["id"], "severity": w["label"], "severity_level": w["severity"], "area": w.get("area"),
                "description": w.get("description"), "river": w.get("river"), "message": w.get("message"),
                "since": iso(w.get("since")), "updated": iso(w.get("updated")), "tidal": w.get("tidal"),
            } for w in floods["warnings"]],
            "weather_warnings": [{
                "level": w["level"], "weather": w["weather"], "title": w.get("title"), "areas": w.get("areas"),
                "from": iso(w.get("from")), "to": iso(w.get("to")), "published": iso(w.get("published")),
                "link": w.get("link"),
            } for w in weather["warnings"]],
        }

    # ---------------------------------------------------------------- forecasts

    def rain_forecast(station_id):
        s = station(station_id)
        if s["kind"] != "rain":
            raise ToolError(f"{station_id} is {KIND_NAMES.get(s['kind'], 'not a rain gauge')}; rain_forecast needs "
                            "a rain gauge. list_stations shows each gauge's kind.")
        d = site.json(f"/api/forecast/rain/{station_id}")
        hours = [{"time": iso(t), "rain_mm": mm, "probability_pct": p} for t, mm, p in d["hours"]]
        return {"generated": now_iso(), "attribution": text.RAIN_FORECAST,
                "station": {"id": s["id"], "name": s["name"]},
                "total_rain_mm": round(sum(h["rain_mm"] for h in hours), 1), "hours": hours}

    def flow_forecast(station_id):
        data = live()
        s = station(station_id, data)
        if not s.get("flow"):
            have = ", ".join(f"{g['id']} ({g['name']})" for g in data["stations"] if g.get("flow"))
            raise ToolError(f"{station_id} has no flow forecast. Gauges with one: {have or 'none at present'}.")
        d = site.json(f"/api/forecast/flow/{station_id}")
        now = int(clock())
        measured = d.get("measured") or []
        return {
            "generated": iso(now), "attribution": text.FLOW_FORECAST,
            "station": {"id": s["id"], "name": s["name"]}, "river": d.get("river"),
            "normal_flow_m3s": d.get("normal"), "high_flow_m3s": d.get("high"),
            "measured": {"time": iso(measured[-1][0]), "flow_m3s": measured[-1][1]} if measured else None,
            "scaled_to_measured": d.get("anchor") is not None,
            "days": [{"date": datetime.fromtimestamp(t, UK).date().isoformat(), "flow_m3s": mean,
                      "ensemble_min_m3s": lo, "ensemble_max_m3s": hi, "forecast": t + 86400 > now}
                     for t, mean, lo, hi in d.get("scaled") or d["days"]],
        }

    # ---------------------------------------------------------------- overflows

    def storm_overflows(state=None, overflow_id=None):
        data = site.json("/data/overflows.json")
        if overflow_id:
            summary = next((o for o in data["overflows"] if o["id"] == overflow_id), None)
            if summary is None:
                raise ToolError(f"No overflow with ID {overflow_id}. storm_overflows without arguments lists them.")
            try:
                d = site.json(f"/api/overflows/{overflow_id}")
            except NotFound:
                raise ToolError(f"No overflow with ID {overflow_id}. storm_overflows without arguments "
                                "lists them.") from None
            return {"generated": iso(data["generated"]),
                    "attribution": f"{text.OVERFLOWS} {text.OVERFLOW_ANNUAL}",
                    "overflow": {
                        "id": d["id"], "name": d.get("name"), "asset_type": d.get("asset_type"),
                        "water": d.get("water"), "state": summary.get("state") or OVERFLOW_STATUS.get(d["status"]),
                        "since": iso(d.get("status_start")), "last_seen": iso(d.get("last_seen")),
                        "spills_last_30_days": [{"start": iso(a), "end": iso(b)} for a, b in d.get("events", [])],
                        "annual": [{"year": y, "spill_hours": h, "spills": n} for y, h, n in d.get("annual", [])],
                        "log_started": iso(d.get("log_started")),
                    }}
        counts = {k: sum(o["state"] == k for o in data["overflows"]) for k in OVERFLOW_STATES}
        out = [{"id": o["id"], "name": o.get("name"), "water": o.get("water"), "state": o["state"],
                "at_works": bool(o.get("works")), "since": iso(o.get("since")),
                "last_spill_ended": iso(o.get("last_end"))}
               for o in data["overflows"] if state is None or o["state"] == state]
        return {"generated": iso(data["generated"]), "attribution": text.OVERFLOWS, "counts": counts,
                "overflows": out}

    # ---------------------------------------------------------------- the rest

    def drought():
        d = site.json("/data/drought.json")
        report = d.get("report")
        if report and report.get("published"):
            report = {**report, "published": datetime.fromisoformat(report["published"]).astimezone(UK).isoformat()}
        return {"generated": iso(d["generated"]), "attribution": text.DROUGHT, "report": report,
                "stages": d.get("stages", []), "hosepipe_bans": d.get("bans", [])}

    def power_cuts():
        d = site.json("/data/powercuts.json")
        return {
            "generated": iso(d["generated"]), "attribution": text.POWER_CUTS, "updated": iso(d.get("updated")),
            "power_cuts": [{
                "id": c["id"], "place": c.get("place"), "lat": c["lat"], "lon": c["lon"],
                "customers_off": c.get("off"), "customers_predicted_off": c.get("predicted"),
                "customers_restored": c.get("restored"), "planned": c.get("planned"),
                "category": c.get("category"), "status": c.get("status"), "start": iso(c.get("start")),
                "estimated_restoration": iso(c.get("etr")), "postcodes": c.get("postcodes", []),
            } for c in d["power_cuts"]],
        }

    return (
        Tool("list_stations", "List gauges",
             "Lists every river level, tidal and rain gauge with its ID, kind, river, location, unit and typical "
             "range. Use it first to find the station_id the other tools need.",
             _schema(), list_stations),
        Tool("conditions", "Current conditions",
             "Gives the latest reading, trend and state at each gauge, as the map shows them, with counts of how "
             "many are high, near the top of their range, rising or stale. Use it to answer how the rivers and "
             "rain are now.",
             _schema({"station_id": _id("Only this gauge, from list_stations."),
                      "kind": {"type": "string", "enum": ["level", "tidal", "rain"],
                               "description": "Only gauges of this kind."}}),
             conditions),
        Tool("flood_warnings", "Flood and weather warnings",
             "Lists the Environment Agency flood warnings and alerts in force in the area, and Met Office weather "
             "warnings covering Devon. Use it whenever someone asks about flood risk; these warnings are the "
             "authority.",
             _schema(), flood_warnings),
        Tool("station_history", "Gauge history",
             "Gives one gauge's readings over the past days, with its typical range and record high for a river "
             "level gauge. Readings are every 15 minutes up to a week, and hourly beyond.",
             _schema({"station_id": STATION_ID,
                      "days": {"type": "integer", "minimum": 1, "maximum": 30, "default": 7,
                               "description": "How many days back, 1 to 30."}}, ["station_id"]),
             station_history),
        Tool("rain_forecast", "Rain forecast",
             "Gives the forecast rain, hour by hour, for the next 48 hours at a rain gauge. Use list_stations to "
             "find a gauge whose kind is rain.",
             _schema({"station_id": _id("A rain gauge's ID, from list_stations.")}, ["station_id"]),
             rain_forecast),
        Tool("flow_forecast", "River flow forecast",
             "Gives modelled river flow for the past week and the fortnight ahead at a gauge that has a flow "
             "forecast, scaled to the measured flow as the site's chart shows it, with normal and high flow to "
             "compare. list_stations shows which gauges have one.",
             _schema({"station_id": _id("A gauge with a flow forecast, from list_stations.")}, ["station_id"]),
             flow_forecast),
        Tool("storm_overflows", "Storm overflows",
             "Lists storm overflows and whether each is spilling, spilled in the last 48 hours, quiet or offline, "
             "or gives one overflow's spills over the past 30 days and its yearly totals. Use it for questions "
             "about sewage spills into rivers.",
             _schema({"state": {"type": "string", "enum": OVERFLOW_STATES,
                                "description": "Only overflows in this state."},
                      "overflow_id": _id("One overflow's ID, from the list, for its detail.")}),
             storm_overflows),
        Tool("drought", "Drought status",
             "Gives the latest Environment Agency drought report for the area, its drought stages and any "
             "hosepipe bans. Use it for questions about dry weather or water restrictions.",
             _schema(), drought),
        Tool("power_cuts", "Power cuts",
             "Lists the live power cuts in the area, with the nearest place, how many customers are off and the "
             "estimated restoration time.",
             _schema(), power_cuts),
    )


TOOLS = make_tools(Site())
