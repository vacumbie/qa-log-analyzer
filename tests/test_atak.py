"""
tests/test_atak.py
Tests for parser/atak.py — ATAK plug-in log parser.
"""

import pytest
from pathlib import Path

from parser.atak import parse_atak_log

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURE_DIR / "atak_sample.log"

# Named ATAK log fixture for filename parsing tests
NAMED_FIXTURE = FIXTURE_DIR / "diagnostic_ATAK_HOTEL_90215634664458_2026-03-04_16_42_04_775.log"


# ── Fixture availability ──────────────────────────────────────────────────────

def test_fixture_exists():
    assert FIXTURE.exists(), f"Fixture missing: {FIXTURE}"


# ── Format detection ──────────────────────────────────────────────────────────

def test_log_format():
    result = parse_atak_log(FIXTURE)
    assert result.log_format == "atak"


def test_platform_is_android():
    result = parse_atak_log(FIXTURE)
    assert result.device.platform == "android"


# ── App info ──────────────────────────────────────────────────────────────────

def test_app_info_parsed():
    result = parse_atak_log(FIXTURE)
    assert len(result.atak_app_launches) == 1


def test_app_version_captured():
    result = parse_atak_log(FIXTURE)
    assert result.device.app_version == "2.3.0 (be06682e) - [5.2.0]"


def test_device_model_captured():
    result = parse_atak_log(FIXTURE)
    assert result.device.device_model == "Samsung SM-S711U1"


# ── Device health ─────────────────────────────────────────────────────────────

def test_health_samples_present():
    result = parse_atak_log(FIXTURE)
    assert len(result.atak_health_samples) > 0


def test_system_samples_emitted():
    """Health records should also populate system_samples for cross-format compat."""
    result = parse_atak_log(FIXTURE)
    assert len(result.system_samples) > 0


def test_connecting_sentinel_suppressed():
    """systemTemperature=0 during CONNECTING state must be treated as None."""
    result = parse_atak_log(FIXTURE)
    connecting = [h for h in result.atak_health_samples if h.connection_state == "CONNECTING"]
    assert len(connecting) > 0
    for h in connecting:
        assert h.system_temp_c is None, "system_temp_c=0 during CONNECTING should be None"
        assert h.transmit_power_differential is None, "tpd=255 should be None"


def test_connected_health_values():
    """CONNECTED state records should have real battery and temperature values."""
    result = parse_atak_log(FIXTURE)
    connected = [h for h in result.atak_health_samples if h.connection_state == "CONNECTED"]
    assert len(connected) > 0
    for h in connected:
        assert h.battery_pct is not None
        assert h.pa_temp_c is not None
        assert h.firmware_version == "3.2.10"


def test_radio_serial_captured():
    result = parse_atak_log(FIXTURE)
    assert result.device.radio_serial == "PNE234100406"


def test_radio_firmware_captured():
    result = parse_atak_log(FIXTURE)
    assert result.device.radio_firmware == "3.2.10"


# ── Messages ──────────────────────────────────────────────────────────────────

def test_messages_parsed():
    result = parse_atak_log(FIXTURE)
    assert len(result.atak_messages) > 0


def test_pli_messages_present():
    result = parse_atak_log(FIXTURE)
    assert len(result.atak_pli_messages) > 0


def test_sent_messages_present():
    result = parse_atak_log(FIXTURE)
    assert len(result.atak_sent_messages) > 0


def test_received_messages_present():
    result = parse_atak_log(FIXTURE)
    assert len(result.atak_received_messages) > 0


def test_chat_message_parsed():
    result = parse_atak_log(FIXTURE)
    chats = result.atak_chat_messages
    assert len(chats) > 0


def test_map_object_parsed():
    result = parse_atak_log(FIXTURE)
    pins = [m for m in result.atak_messages if m.message_object_type == "PIN"]
    assert len(pins) > 0


def test_rssi_on_sent_is_zero():
    """Sent messages always have rssi=0 — a placeholder, not a real reading."""
    result = parse_atak_log(FIXTURE)
    for m in result.atak_sent_messages:
        assert m.rssi == 0
        assert not m.rssi_is_valid


def test_rssi_on_received_is_valid():
    result = parse_atak_log(FIXTURE)
    received = [m for m in result.atak_received_messages if m.rssi != 0]
    assert len(received) > 0
    for m in received:
        assert m.rssi_is_valid


def test_negative_delivery_time_preserved():
    """Negative delivery times (clock skew) must be kept, not discarded."""
    result = parse_atak_log(FIXTURE)
    negative = [m for m in result.atak_messages if m.delivery_time_ms is not None and m.delivery_time_ms < 0]
    assert len(negative) > 0


def test_unique_sender_gids():
    result = parse_atak_log(FIXTURE)
    assert len(result.atak_unique_sender_gids) > 1


# ── Events ────────────────────────────────────────────────────────────────────

def test_events_parsed():
    result = parse_atak_log(FIXTURE)
    assert len(result.atak_events) > 0


def test_device_connected_event():
    result = parse_atak_log(FIXTURE)
    connected = [e for e in result.atak_events if e.event_type == "deviceConnected"]
    assert len(connected) > 0
    assert connected[0].serial_number != ""


def test_device_disconnected_event():
    result = parse_atak_log(FIXTURE)
    disconnected = [e for e in result.atak_events if e.event_type == "deviceDisconnected"]
    assert len(disconnected) > 0


def test_power_level_updated_event():
    result = parse_atak_log(FIXTURE)
    power = [e for e in result.atak_events if e.event_type == "powerLevelUpdated"]
    assert len(power) > 0
    assert power[0].power_watts == 5.0


def test_pli_setting_updated_event():
    result = parse_atak_log(FIXTURE)
    pli = [e for e in result.atak_events if e.event_type == "pliSettingUpdated"]
    assert len(pli) > 0
    assert pli[0].pli_interval_sec == 60
    assert pli[0].pli_auto_send is True


# ── Session timestamps ────────────────────────────────────────────────────────

def test_session_timestamps_populated():
    result = parse_atak_log(FIXTURE)
    assert result.session_start != ""
    assert result.session_end != ""
    assert result.session_start <= result.session_end


# ── GID from messages ─────────────────────────────────────────────────────────

def test_device_gid_captured():
    result = parse_atak_log(FIXTURE)
    assert result.device.gid == "90215634664458"


# ── Filename parsing ──────────────────────────────────────────────────────────

def test_callsign_from_filename():
    """Callsign should be extracted from standard ATAK log filename."""
    if not NAMED_FIXTURE.exists():
        pytest.skip("Named fixture not available")
    result = parse_atak_log(NAMED_FIXTURE)
    assert result.device.callsign == "HOTEL"


def test_gid_from_filename():
    """GID should be extracted from standard ATAK log filename."""
    if not NAMED_FIXTURE.exists():
        pytest.skip("Named fixture not available")
    result = parse_atak_log(NAMED_FIXTURE)
    assert result.device.gid == "90215634664458"


# ── Error handling ────────────────────────────────────────────────────────────

def test_no_parse_errors():
    result = parse_atak_log(FIXTURE)
    assert result.parse_errors == []


def test_missing_file_returns_error():
    result = parse_atak_log(Path("nonexistent_file.log"))
    assert len(result.parse_errors) > 0
    assert result.log_format == "atak"
