"""tests/test_relay_manager.py"""

from pathlib import Path

from parser.relay_manager import parse_relay_manager_log

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURE_DIR / "relay_manager_sample.txt"


def test_log_format_and_platform():
    result = parse_relay_manager_log(FIXTURE)
    assert result.log_format == "relay_manager"
    assert result.device.platform == "android"


def test_app_pid_detected():
    """The relayHealthRequestCall line carries the Relay Manager PID."""
    result = parse_relay_manager_log(FIXTURE)
    assert result.relay_manager_app_pid == "16170"


def test_environment_is_stage():
    """The na.relaymanager(<pid>) io_stats marker identifies a stage log."""
    result = parse_relay_manager_log(FIXTURE)
    assert result.relay_manager_environment == "stage"


def test_device_serial_and_ble_address():
    result = parse_relay_manager_log(FIXTURE)
    assert result.device.radio_serial == "PNE234200715"
    assert result.relay_manager_ble_address == "FB:6C:DB:3B:3A:9A"


def test_subtype_network_polling():
    """Dominant notification type 72 (BLE poll heartbeat) → networkPolling."""
    result = parse_relay_manager_log(FIXTURE)
    assert result.relay_manager_subtype == "networkPolling"


def test_health_requests_parsed():
    result = parse_relay_manager_log(FIXTURE)
    assert len(result.relay_health_requests) == 2
    # The BLE write line immediately after each command attaches its payload.
    assert all(hr.ble_payload for hr in result.relay_health_requests)


def test_notification_counts():
    result = parse_relay_manager_log(FIXTURE)
    assert result.relay_manager_notification_counts == {72: 3}


def test_named_events_parsed():
    result = parse_relay_manager_log(FIXTURE)
    event_types = {e.event_type for e in result.relay_manager_events}
    assert event_types == {"health_response_ready", "battery_state_changed", "device_alert"}


def test_session_timestamps():
    result = parse_relay_manager_log(FIXTURE)
    assert result.session_start != ""
    assert result.session_end != ""


def test_data_limitations_surfaced():
    """Relay Manager always surfaces its standing data limitations, never silently
    drops them — BLE payloads are captured but not decoded, and only one node is
    observed per session."""
    result = parse_relay_manager_log(FIXTURE)
    # Canonical em-dash prefix, consistent with the other four parsers.
    limits = [e for e in result.parse_errors if e.startswith("DATA LIMITATION —")]
    assert any("BLE payload not decoded" in e for e in limits)
    assert any("Single relay node observed" in e for e in limits)


def test_missing_file_returns_error():
    result = parse_relay_manager_log(Path("nonexistent_file.txt"))
    assert len(result.parse_errors) > 0
