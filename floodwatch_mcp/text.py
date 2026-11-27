"""The words the server says about itself: its instructions, and the
attribution each source asks for (from the About page's sources table).

Station, river and overflow names come from third parties, so they appear
only as data in tool results, never here.
"""

INSTRUCTIONS = (
    "Floodwatch watches the River Taw catchment in north Devon, England: river levels, the tide, rain, "
    "flood and weather warnings, forecasts, storm overflows, drought, and power cuts. These tools read the same "
    "data its map shows. "
    "Floodwatch is not an official warning service. The Environment Agency's flood warnings, which "
    "flood_warnings relays, are the authority on flood risk, and anyone at risk should follow them. "
    "Units are named in the field: levels in metres (level_m, with the gauge's datum in unit), rain in "
    "millimetres (rain_mm), river flow in cubic metres a second (flow_m3s). Times are ISO 8601 in UK time "
    "(Europe/London), with the offset given. "
    "Gauges report every 15 minutes or so, and a gauge whose state is stale has stopped reporting, so its last "
    "reading may be hours old. A river level gauge's state is high above the top of its typical range, approach "
    "within 30% of that top, normal within the range, low below it, and unknown where it has no typical range; "
    "a rain gauge's is raining if it has had rain in the past hour and dry if not, and a tidal gauge's is tidal, "
    "as the tide has no typical range. "
    "Compare generated, when Floodwatch last refreshed the data, and conditions' latest_reading, its newest "
    "reading at any gauge, with the current time: delayed is true when that reading is more than an hour old. "
    "Start with list_stations for gauge IDs. "
    "Every result carries an attribution line naming its sources and their licences; cite it when you pass the "
    "data on."
)

OGL = "Open Government Licence v3.0"

READINGS = ("Gauge readings: Environment Agency flood and river level data from the real-time data API (Beta), "
            f"{OGL}.")
FLOOD_WARNINGS = f"Flood warnings: Environment Agency real-time flood-monitoring API, {OGL}."
WEATHER_WARNINGS = (f"Weather warnings: Met Office. Contains public sector information licensed under the {OGL}.")
RAIN_FORECAST = "Rain forecast: Open-Meteo (open-meteo.com), CC BY 4.0."
FLOW_FORECAST = ("River flow forecast: GloFAS, Copernicus Emergency Management Service, via Open-Meteo's flood API "
                 "(open-meteo.com), CC BY 4.0, scaled with mean flows from the UK National River Flow Archive. "
                 f"Measured flow: Environment Agency Hydrology API, {OGL}.")
OVERFLOWS = "Storm overflows: South West Water's storm overflow activity feed, CC BY 4.0."
OVERFLOW_ANNUAL = ("Yearly totals: Event Duration Monitoring annual returns, © Environment Agency copyright "
                   f"and/or database right, {OGL}.")
DROUGHT = f"Drought: Environment Agency, Dry weather and drought in England, via GOV.UK, {OGL}."
POWER_CUTS = ("Power cuts: National Grid Electricity Distribution live power cuts. Supported by NGED Open Data, "
              "NGED Open Data Licence.")
