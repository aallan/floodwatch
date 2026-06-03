#!/usr/bin/env python3
"""
One-time historical backfill for CSO sites.

Queries Water UK's "Storm Overflow Annual Returns — All Years" FeatureServer
for the Taw catchment, joins old WaSC permit references to the new DEFRA
permit IDs used by the live feed, and writes two CSVs the frontend reads
once at startup:

  data/cso_sites_meta.csv     id, name, asset_type, shellfish, bathing
  data/cso_annual_history.csv id, year, hours, spills

Re-runnable: producing the same outputs from the same upstream data is
idempotent. Schemas changing upstream would require code changes here, not
silent partial outputs.

Note: 2020 data exists in a separate FeatureServer with a sparser schema
and patchier EDM coverage - we skip it. Years 2021-2025 are covered.
"""

import csv
import json
import os
import sys
import tempfile
from collections import defaultdict
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Reuse constants + helpers from the live fetcher to keep the river
# allowlist in a single place — no duplication, no drift.
from fetch_data import (
    CSO_RIVER_ALLOWLIST,
    CSO_RIVER_EXCLUDE,
    DATA_DIR,
)

# All-Years summary FeatureServer published by The Rivers Trust / Water UK.
# Covers 2021-2025. Schema is snake_case (different from the per-year tidy
# datasets that use camelCase). The lookup of old/new permit IDs is built
# in via `unique_id` (2024+ only) and `wasc_supplementary_permit_ref_opt`
# (persistent across the 2024 DEFRA rename).
ALL_YEARS_URL = (
    "https://services1.arcgis.com/JZM7qJpmv7vJ0Hzx/arcgis/rest/services/edm_annual_returns_all_years_public/FeatureServer/0/query"
)


def _build_where() -> str:
    """SQL WHERE filtering to South West Water sites in the Taw catchment."""
    field = "receiving_water_environment_common_name_ea_condat"
    likes = " OR ".join(f"UPPER({field}) LIKE '%{r}%'" for r in CSO_RIVER_ALLOWLIST)
    nots = " AND ".join(f"UPPER({field}) NOT LIKE '%{e}%'" for e in CSO_RIVER_EXCLUDE)
    return f"water_company_name='South West Water' AND ({likes}) AND ({nots})"


def _post(url: str, params: dict[str, str]) -> dict[str, Any]:
    """POST form-encoded params. ArcGIS returns 404 (not 414) on long GETs,
    so the catchment WHERE clause must go in the body."""
    body = urlencode(params).encode()
    req = Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    with urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_catchment_history() -> list[dict[str, Any]]:
    """Pull every catchment row from the All-Years FeatureServer.

    Returns ~370 attribute dicts (74 sites x ~5 years).
    """
    params = {
        "where": _build_where(),
        "outFields": ",".join(
            [
                "annual_return_year",
                "unique_id",
                "old_unique_id_pre_2024",
                "wasc_supplementary_permit_ref_opt",
                "site_name_ea_condat",
                "site_name_wasc_op_name",
                "storm_discharge_asset_type",
                "receiving_water_environment_common_name_ea_condat",
                "shellfish_water",
                "bathing_water",
                "total_spill_duration_hrs_calculated",
                "counted_spills_12_24hr_calculated",
            ]
        ),
        "returnGeometry": "false",
        "resultRecordCount": "2000",
        "f": "json",
    }
    try:
        data = _post(ALL_YEARS_URL, params)
    except (HTTPError, URLError, TimeoutError) as e:
        print(f"ERROR: All-Years FeatureServer unreachable: {e}", file=sys.stderr)
        sys.exit(1)
    return [f["attributes"] for f in data.get("features", [])]


def build_wasc_to_new_id(rows: list[dict[str, Any]]) -> dict[str, str]:
    """Build a {wasc_supplementary_permit_ref_opt → unique_id} mapping
    from rows where both are populated (2024+ rows).

    Used to back-fill the modern SBB-style ID onto historical rows that
    only carry the persistent WaSC permit reference.
    """
    mapping = {}
    for r in rows:
        wasc = r.get("wasc_supplementary_permit_ref_opt")
        new = r.get("unique_id")
        if wasc and new:
            mapping[wasc] = new
    return mapping


def resolve_id(row: dict[str, Any], wasc_to_new: dict[str, str]) -> str | None:
    """Get the live-feed-compatible permit ID for a historical row.

    Preference order:
      1. unique_id (set on 2024+ rows directly)
      2. wasc_to_new mapping via wasc_supplementary_permit_ref_opt
      3. None — site exists historically but has no live-feed counterpart
    """
    if row.get("unique_id"):
        return row["unique_id"]
    wasc = row.get("wasc_supplementary_permit_ref_opt")
    if wasc and wasc in wasc_to_new:
        return wasc_to_new[wasc]
    return None


def _latest_non_empty(rows: list[dict[str, Any]], field: str) -> str:
    """First non-empty value of `field` in `rows`. Caller pre-sorts rows
    by year descending so 'first non-empty' means 'most recent known'.
    'Unknown' is treated as no-data per the upstream convention."""
    for r in rows:
        v = r.get(field)
        if v not in (None, "", "Unknown"):
            return str(v)
    return ""


def aggregate_metadata(rows: list[dict[str, Any]], wasc_to_new: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Reduce per-(site, year) rows to one metadata record per site.

    Asset type and site name can theoretically vary year-to-year; we keep
    the most recent non-empty value (latest annual_return_year wins).
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        permit_id = resolve_id(r, wasc_to_new)
        if permit_id:
            grouped[permit_id].append(r)

    meta: dict[str, dict[str, Any]] = {}
    for permit_id, site_rows in grouped.items():
        # Sort by year descending so _latest_non_empty walks newest-first.
        site_rows.sort(key=lambda r: r.get("annual_return_year") or "", reverse=True)
        meta[permit_id] = {
            "id": permit_id,
            # site_name_ea_condat is the EA's name; fall back to the WaSC's
            # operator name if EA has nothing recorded.
            "name": _latest_non_empty(site_rows, "site_name_ea_condat") or _latest_non_empty(site_rows, "site_name_wasc_op_name"),
            "asset_type": _latest_non_empty(site_rows, "storm_discharge_asset_type"),
            "shellfish_water": _latest_non_empty(site_rows, "shellfish_water"),
            "bathing_water": _latest_non_empty(site_rows, "bathing_water"),
        }
    return meta


def aggregate_annual(rows: list[dict[str, Any]], wasc_to_new: dict[str, str]) -> list[dict[str, Any]]:
    """Reduce per-row data to one (site, year) record with hours + spills."""
    out = []
    for r in rows:
        permit_id = resolve_id(r, wasc_to_new)
        if not permit_id:
            continue
        year = r.get("annual_return_year")
        if not year:
            continue
        hours = r.get("total_spill_duration_hrs_calculated")
        spills = r.get("counted_spills_12_24hr_calculated")
        out.append(
            {
                "id": permit_id,
                "year": year,
                "hours": "" if hours is None else round(float(hours), 1),
                "spills": "" if spills is None else int(spills),
            }
        )
    out.sort(key=lambda x: (x["id"], x["year"]))
    return out


def _atomic_write(filepath: str, write_fn) -> None:
    """Write file atomically — same pattern as fetch_data._atomic_write_csv."""
    dir_path = os.path.dirname(filepath) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="") as f:
            write_fn(f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, filepath)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def save_sites_meta(meta: dict[str, dict[str, Any]]) -> None:
    path = os.path.join(DATA_DIR, "cso_sites_meta.csv")

    def write_fn(f):
        cols = ["id", "name", "asset_type", "shellfish_water", "bathing_water"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for permit_id in sorted(meta):
            w.writerow(meta[permit_id])

    _atomic_write(path, write_fn)
    print(f"  Wrote {len(meta)} sites to {path}")


def save_annual_history(rows: list[dict[str, Any]]) -> None:
    path = os.path.join(DATA_DIR, "cso_annual_history.csv")

    def write_fn(f):
        w = csv.DictWriter(f, fieldnames=["id", "year", "hours", "spills"])
        w.writeheader()
        w.writerows(rows)

    _atomic_write(path, write_fn)
    print(f"  Wrote {len(rows)} (site, year) records to {path}")


def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    print("=== CSO historical backfill (2021-2025 annual returns) ===")

    rows = fetch_catchment_history()
    print(f"  Fetched {len(rows)} historical records from All-Years FeatureServer")

    wasc_to_new = build_wasc_to_new_id(rows)
    print(f"  Built {len(wasc_to_new)} WaSC permit-ref → new-ID mappings")

    meta = aggregate_metadata(rows, wasc_to_new)
    annual = aggregate_annual(rows, wasc_to_new)

    unresolved = sum(1 for r in rows if resolve_id(r, wasc_to_new) is None)
    if unresolved:
        print(f"  WARNING: {unresolved} rows could not be resolved to a live-feed ID — skipped")

    save_sites_meta(meta)
    save_annual_history(annual)
    print("=== Done ===")


if __name__ == "__main__":
    main()
