"""Shared fixtures for Floodwatch tests."""
import io
import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_station_level():
    """A typical river level station dict matching LEVEL_STATIONS format."""
    return {
        "id": "50140",
        "label": "Umberleigh",
        "rloi": "3106",
        "lat": 50.99542,
        "lon": -3.985089,
        "river": "River Taw",
        "type": "level",
    }


@pytest.fixture
def sample_station_rainfall():
    """A typical rainfall station dict matching RAINFALL_STATIONS format."""
    return {
        "id": "50199",
        "label": "Lapford Bowerthy",
        "lat": 50.873373,
        "lon": -3.798545,
        "type": "rainfall",
    }


@pytest.fixture
def sample_station_tidal():
    """The Barnstaple tidal station with custom measure_id key."""
    return {
        "id": "50198",
        "label": "Barnstaple (Tidal)",
        "rloi": "9013",
        "lat": 51.080046,
        "lon": -4.064537,
        "river": "River Taw",
        "type": "tidal",
        "measure_id": "50198-level-tidal_level-i-15_min-mAOD",
    }


@pytest.fixture
def sample_readings():
    """A list of reading dicts with dateTime and value."""
    return [
        {"dateTime": "2026-02-10T10:00:00Z", "value": 0.523},
        {"dateTime": "2026-02-10T10:15:00Z", "value": 0.521},
        {"dateTime": "2026-02-10T10:30:00Z", "value": 0.519},
        {"dateTime": "2026-02-10T10:45:00Z", "value": 0.518},
        {"dateTime": "2026-02-10T11:00:00Z", "value": 0.516},
    ]


@pytest.fixture
def sample_api_response():
    """A sample EA API JSON response loaded from fixtures."""
    with open(FIXTURES_DIR / "sample_readings.json") as f:
        return json.load(f)


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Create a temporary data directory and monkeypatch DATA_DIR in both modules."""
    d = tmp_path / "data"
    d.mkdir()

    import fetch_data
    import serve
    monkeypatch.setattr(fetch_data, "DATA_DIR", str(d))
    monkeypatch.setattr(serve, "DATA_DIR", str(d))

    return d


def make_mock_urlopen(response_data, status=200):
    """Create a mock urlopen context manager that returns JSON data."""
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(response_data).encode("utf-8")
    mock_response.status = status
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response
