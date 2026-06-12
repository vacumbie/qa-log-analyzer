"""tests/test_rsdk.py"""

from pathlib import Path

from parser.rsdk import parse_rsdk_log
from api.routes.parse import _result_to_dict

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
    # The GRIP fixture carries incoming hop/rssi data, so no DATA LIMITATION is
    # emitted — this asserts a genuinely clean parse with no spurious errors.
    result = parse_rsdk_log(FIXTURE_DIR / "rsdk_grip_sample.txt")
    assert result.parse_errors == [], f"Unexpected errors: {result.parse_errors}"


# ── GRIP hop count / RSSI availability (DATA LIMITATION) ──────────────────────
# Hop count and RSSI only exist on GRIP_Receiver incoming message-fields lines.
# When a session has none, the parser must surface that honestly in parse_errors.

def test_grip_limitation_emitted_when_no_incoming_grip():
    """No GRIP messages at all → limitation fires. This fixture also carries
    ReceivedDataImpl(hopCount=0, rssi=0) lines; those SDK sentinel zeros must NOT
    be mistaken for GRIP RF data and suppress the limitation."""
    result = parse_rsdk_log(FIXTURE_DIR / "rsdk_sample_ios.txt")
    assert result.grip_messages == []
    limits = [e for e in result.parse_errors if e.startswith("DATA LIMITATION —")]
    assert any("GRIP hop count and RSSI" in e for e in limits), result.parse_errors


def test_grip_limitation_fires_with_outgoing_only_grip():
    """The discrimination the fix exists for: outgoing GRIP (GRIP_SENDER) carries
    no hop/RSSI, so a session with only outgoing GRIP messages must still surface
    the limitation — having grip_messages is not enough; they must be incoming."""
    result = parse_rsdk_log(FIXTURE_DIR / "rsdk_grip_outgoing_only.txt")
    assert len(result.grip_messages) > 0
    assert all(g.direction == "outgoing" for g in result.grip_messages)
    assert all(g.hops is None and g.rssi is None for g in result.grip_messages)
    assert any("GRIP hop count and RSSI" in e for e in result.parse_errors), result.parse_errors


def test_no_grip_limitation_when_incoming_present():
    result = parse_rsdk_log(FIXTURE_DIR / "rsdk_grip_sample.txt")
    assert not any("GRIP hop count and RSSI" in e for e in result.parse_errors)


# ── Health Score RSSI dimension input (summary.avg_rssi) ──────────────────────
# avg_rssi is computed in _result_to_dict() from GRIP incoming RSSI, so these
# assert against the serialized summary the UI Health tab consumes.

def test_avg_rssi_from_grip_incoming():
    """rsdk logs with GRIP_Receiver incoming RSSI populate avg_rssi (mean of the
    incoming rssi values) so the Health Score RSSI dimension is scored, not free-passed."""
    result = parse_rsdk_log(FIXTURE_DIR / "rsdk_grip_sample.txt")
    assert [g.rssi for g in result.grip_messages] == [-80, -90]
    summary = _result_to_dict(result)["summary"]
    assert summary["avg_rssi"] == -85.0


def test_avg_rssi_none_without_grip():
    """Without GRIP incoming RSSI, avg_rssi is None → the RSSI dimension is N/A
    (excluded from the score), never a free pass."""
    summary = _result_to_dict(parse_rsdk_log(FIXTURE_DIR / "rsdk_sample_ios.txt"))["summary"]
    assert summary["avg_rssi"] is None


def test_missing_file_returns_error():
    result = parse_rsdk_log(Path("nonexistent_file.txt"))
    assert len(result.parse_errors) > 0
