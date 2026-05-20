"""tests/test_rsdk.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parser.rsdk import parse_rsdk_log

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_parses_platform_ios():
    result = parse_rsdk_log(FIXTURE_DIR / "rsdk_sample_ios.txt")
    assert result.log_format == "rsdk"
    assert result.device.platform == "ios"


def test_ble_failures_detected():
    result = parse_rsdk_log(FIXTURE_DIR / "rsdk_sample_ios.txt")
    assert len(result.ble_fail_events) > 0
    event = result.ble_fail_events[0]
    assert event.radio_serial != ""
    assert 0 <= event.hour <= 23


def test_ble_failures_deduplicated():
    """Duplicate log lines must not double-count failures."""
    result = parse_rsdk_log(FIXTURE_DIR / "rsdk_sample_ios.txt")
    # All events should have unique timestamps (dedup removes exact copies)
    timestamps = [e.timestamp for e in result.ble_fail_events]
    assert len(timestamps) == len(set(timestamps)), "Duplicate BLE failure events found"


def test_system_samples_present():
    result = parse_rsdk_log(FIXTURE_DIR / "rsdk_sample_ios.txt")
    assert len(result.system_samples) > 0


def test_session_timestamps():
    result = parse_rsdk_log(FIXTURE_DIR / "rsdk_sample_ios.txt")
    assert result.session_start != ""
    assert result.session_end   != ""


def test_no_parse_errors():
    result = parse_rsdk_log(FIXTURE_DIR / "rsdk_sample_ios.txt")
    assert result.parse_errors == [], f"Unexpected errors: {result.parse_errors}"


def test_missing_file_returns_error():
    result = parse_rsdk_log(Path("nonexistent_file.txt"))
    assert len(result.parse_errors) > 0
