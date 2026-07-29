"""
tests/test_atak.py
Tests for parser/atak.py — ATAK plug-in log parser.
"""

import pytest
from pathlib import Path

from parser.atak import parse_atak_log
from api.routes.parse import _result_to_dict

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURE_DIR / "atak_sample.json"

# Synthetic enhanced (SDK Logging 2.0) fixture — covers sdkError aggregation,
# fileName, SUCCESS status, the -99 open-segments sentinel, location fields,
# firmwareUpdate events, deviceDisconnected.location, and originatorUUID.
# .json extension used because ATAK logs are JSON arrays; other formats
# (rsdk, diagnostic) use their native extensions under tests/fixtures/.
ENHANCED = FIXTURE_DIR / "atak_enhanced_sample.json"

# Edge-case fixture: SDK 2.0 summary present but with zero ERROR|BLE entries
# (only ERROR|RADIO), plus two deviceDisconnected events. Pins the rule that a
# genuine zero BLE-error count is reported as 0 and does NOT fall back to the
# disconnect count — the fallback fires only when no SDK 2.0 records exist.
SDK_NO_BLE = FIXTURE_DIR / "atak_sdk_no_ble_sample.json"

# Synthetic radio-swap fixture: one device session whose health samples carry
# two distinct serial numbers (a mid-session radio swap). Pins the per-serial
# data contract the Battery chart depends on — it groups battery_pct by
# serial_number and detects swaps from the distinct serials.
MULTISERIAL = FIXTURE_DIR / "atak_multiserial_sample.json"

# Named ATAK log fixture for filename parsing tests
NAMED_FIXTURE = FIXTURE_DIR / "diagnostic_ATAK_HOTEL_90215634664458_2026-03-04_16_42_04_775.log"

# Synthetic v3.0-naming-convention fixture — no "ATAK_" segment in the filename
# (diagnostic_<CALLSIGN>_<GID>_<DATE>_<TIME>.log), matching the plugin v3.0
# field naming observed 2026-07-28/29. Pins that the filename regex still
# extracts callsign/GID without the old ATAK_ literal.
V3_NAMED_FIXTURE = FIXTURE_DIR / "diagnostic_KESTREL_11223_2026-07-28_09_00_00_000.log"

# Synthetic fixture with a filename that matches neither the old nor new ATAK
# naming convention, and zero connectionState (health) records — the pattern
# observed in early ATAK v3.0 plugin/FW builds. Pins the senderCallsign
# fallback for device.callsign and the missing-health-telemetry DATA
# LIMITATION.
V3_NO_HEALTH_FIXTURE = FIXTURE_DIR / "atak_v3_no_health_sample.json"

# Synthetic fixture with a genuine 5s PLI cadence, self-reported via
# message.interval. Pins the data contract the Originator PLI UI fix depends
# on: sub-15s cadences must round-trip through message.pli_interval, since
# the old frontend gap-inference bucket list ([15,30,60,120,180,300,600])
# had no slot for 5s and silently discarded it as noise — see
# docs/atak_v3_early_integration_notes.md.
V3_5S_PLI_FIXTURE = FIXTURE_DIR / "atak_v3_5s_pli_sample.json"


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
# NAMED_FIXTURE is intentionally not committed — it holds real captured field
# data. These two tests skip when it's absent (the normal case in a clean
# checkout); they only run if someone drops a real ATAK log with that name into
# tests/fixtures/ locally. Do not create a fixture just to make them run.

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


def test_callsign_from_v3_filename_without_atak_segment():
    """v3.0 plugin filenames drop the ATAK_ segment; callsign must still
    extract from diagnostic_<CALLSIGN>_<GID>_<DATE>_<TIME>.log."""
    result = parse_atak_log(V3_NAMED_FIXTURE)
    assert result.device.callsign == "KESTREL"


def test_gid_from_v3_filename_without_atak_segment():
    result = parse_atak_log(V3_NAMED_FIXTURE)
    assert result.device.gid == "11223"


def test_callsign_fallback_from_sender_callsign():
    """When the filename matches neither naming convention, callsign should
    fall back to the device's own senderCallsign on a sent message — same
    pattern as the existing GID fallback."""
    result = parse_atak_log(V3_NO_HEALTH_FIXTURE)
    assert result.device.callsign == "OSPREY"


def test_sender_callsign_captured_on_message():
    result = parse_atak_log(V3_NO_HEALTH_FIXTURE)
    sent = [m for m in result.atak_messages if m.is_sender]
    received = [m for m in result.atak_messages if not m.is_sender]
    assert sent[0].sender_callsign == "OSPREY"
    assert received[0].sender_callsign == "MERLIN"


def test_no_health_data_limitation_fires():
    """A log with zero connectionState records — the pattern seen in early
    ATAK v3.0 builds — must surface a DATA LIMITATION, not fail silently."""
    result = parse_atak_log(V3_NO_HEALTH_FIXTURE)
    assert result.atak_health_samples == []
    limits = [e for e in result.parse_errors if e.startswith("DATA LIMITATION —")]
    assert any("device-health" in e for e in limits)


def test_no_health_data_limitation_absent_when_samples_present():
    """Regression guard: the missing-health-telemetry DATA LIMITATION must
    NOT fire for a log that actually has health samples."""
    result = parse_atak_log(FIXTURE)
    assert len(result.atak_health_samples) > 0
    limits = [e for e in result.parse_errors if "device-health" in e]
    assert limits == []


def test_sub_15s_pli_interval_preserved():
    """A genuine 5s PLI cadence, self-reported via message.interval, must
    come through as pli_interval == '5' — not silently dropped. This is the
    data contract the Originator PLI frontend fix depends on to represent
    cadences the old gap-inference bucket list couldn't."""
    result = parse_atak_log(V3_5S_PLI_FIXTURE)
    sent_pli = [m for m in result.atak_messages if m.message_type == "pli" and m.is_sender]
    assert len(sent_pli) == 3
    assert all(m.pli_interval == "5" for m in sent_pli)


# ── Error handling ────────────────────────────────────────────────────────────

def test_no_parse_errors():
    result = parse_atak_log(FIXTURE)
    assert result.parse_errors == []


def test_missing_file_returns_error():
    result = parse_atak_log(Path("nonexistent_file.log"))
    assert len(result.parse_errors) > 0
    assert result.log_format == "atak"


# ── Enhanced log (SDK Logging 2.0) — sdkError aggregation ─────────────────────

def test_enhanced_fixture_exists():
    assert ENHANCED.exists(), f"Fixture missing: {ENHANCED}"


def test_sdk_error_summary_present():
    result = parse_atak_log(ENHANCED)
    assert result.atak_sdk_error_summary is not None


def test_sdk_error_total_count():
    """All sdkError records are counted, not stored individually.
    Fixture: 3x ERROR|BLE + 2x ERROR|RADIO + 2x BLE|DEBUG = 7 total."""
    result = parse_atak_log(ENHANCED)
    assert result.atak_sdk_error_summary.total_count == 7


def test_sdk_error_not_stored_as_messages():
    """sdkError records must not leak into atak_messages."""
    result = parse_atak_log(ENHANCED)
    # 6 real message records in the fixture; sdkError records excluded
    assert len(result.atak_messages) == 6


def test_sdk_error_counts_by_tag():
    result = parse_atak_log(ENHANCED)
    by_tag = result.atak_sdk_error_summary.counts_by_tag
    assert by_tag["ERROR|BLE"] == 3
    assert by_tag["ERROR|RADIO"] == 2
    assert by_tag["BLE|DEBUG"] == 2


def test_sdk_error_counts_by_info():
    result = parse_atak_log(ENHANCED)
    by_info = result.atak_sdk_error_summary.counts_by_info
    assert by_info["Gatt write back off reached skipping write"] == 3
    assert by_info["Radio command timeout"] == 2


def test_sdk_error_radio_type_captured():
    """radioType (e.g. PRO_X_2) is surfaced only by sdkError deviceState."""
    result = parse_atak_log(ENHANCED)
    assert "PRO_X_2" in result.atak_sdk_error_summary.radio_types


def test_sdk_error_sample_retained():
    result = parse_atak_log(ENHANCED)
    sample = result.atak_sdk_error_summary.sample
    assert sample is not None
    assert sample.platform_type == "ANDROID"
    assert sample.endorsements == "PREMIUM"
    assert sample.additional_info != ""


def test_sdk_error_data_limitation_surfaced():
    """Volume is informational; a DATA LIMITATION must be in parse_errors, using
    the canonical em-dash prefix the UI and compliance checks key off of."""
    result = parse_atak_log(ENHANCED)
    limits = [e for e in result.parse_errors if e.startswith("DATA LIMITATION —")]
    assert any("sdkError" in e for e in limits)


# ── Summary — BLE failure count for the Health Score ──────────────────────────
# ble_fail_count is computed in _result_to_dict(), not the parser, so these
# tests assert against the serialized summary the UI Health tab consumes.

def test_ble_fail_count_from_sdk_errors():
    """Enhanced logs count BLE from ANY tag containing BLE.
    Includes ERROR|BLE (fw 3.2.10+) and BLE|DEBUG (fw 3.1.11/MESMER).
    Fixture: 3x ERROR|BLE + 2x BLE|DEBUG = 5 total."""
    summary = _result_to_dict(parse_atak_log(ENHANCED))["summary"]
    assert summary["ble_fail_count"] == 5


def test_ble_fail_count_falls_back_to_disconnects():
    """Without SDK 2.0 records, BLE failures fall back to deviceDisconnected count."""
    result = parse_atak_log(FIXTURE)
    assert result.atak_sdk_error_summary is None
    disconnects = sum(1 for e in result.atak_events if e.event_type == "deviceDisconnected")
    summary = _result_to_dict(result)["summary"]
    assert summary["ble_fail_count"] == disconnects


def test_ble_debug_tag_counts_as_ble_failure():
    """fw 3.1.11 (MESMER) uses BLE|DEBUG not ERROR|BLE — P1 fix.
    Severity must not gate BLE failure counting."""
    result = parse_atak_log(ENHANCED)
    by_tag = result.atak_sdk_error_summary.counts_by_tag
    assert "BLE|DEBUG" in by_tag
    assert by_tag["BLE|DEBUG"] == 2
    summary = _result_to_dict(result)["summary"]
    assert summary["ble_fail_count"] >= by_tag["BLE|DEBUG"]


def test_ble_fail_count_zero_when_sdk_present_without_ble_errors():
    """A SDK 2.0 summary with no ERROR|BLE entries reports 0 — it does NOT fall
    back to the deviceDisconnected count. The fallback fires only when no SDK 2.0
    records exist at all."""
    result = parse_atak_log(SDK_NO_BLE)
    assert result.atak_sdk_error_summary is not None
    assert "ERROR|BLE" not in result.atak_sdk_error_summary.counts_by_tag
    disconnects = sum(1 for e in result.atak_events if e.event_type == "deviceDisconnected")
    assert disconnects == 2  # fixture has two — proves the fallback was not taken
    summary = _result_to_dict(result)["summary"]
    assert summary["ble_fail_count"] == 0


# ── Enhanced log — fileTransfer fields ────────────────────────────────────────

def test_file_name_on_completed_transfer():
    result = parse_atak_log(ENHANCED)
    completed = [m for m in result.atak_messages if m.is_file_transfer and m.delivery_status == "SUCCESS"]
    assert len(completed) == 1
    assert completed[0].file_name == "goTenna_ATAK_1780506877104.jpg"


def test_file_name_unknown_on_incomplete_transfer():
    result = parse_atak_log(ENHANCED)
    incomplete = [m for m in result.atak_messages if m.is_file_transfer and m.delivery_status == "PARTIALLY_RECEIVED"]
    assert len(incomplete) >= 1
    for m in incomplete:
        assert m.file_name == "UNKNOWN"


def test_success_delivery_status():
    """SUCCESS is sender-side confirmed delivery, distinct from FULLY_RECEIVED."""
    result = parse_atak_log(ENHANCED)
    success = [m for m in result.atak_messages if m.delivery_status == "SUCCESS"]
    assert len(success) == 1
    assert success[0].is_sender is True


def test_open_segments_sentinel_becomes_none():
    """numberOfOpenSegments = -99 is a sentinel → stored as None, never -99."""
    result = parse_atak_log(ENHANCED)
    for m in result.atak_messages:
        assert m.open_segments != -99
    # The cancelled-before-count transfer has open_segments None
    none_open = [m for m in result.atak_messages
                 if m.is_file_transfer and m.open_segments is None]
    assert len(none_open) == 1


def test_positive_open_segments_preserved():
    """A genuine positive open-segment count must be preserved, not nulled."""
    result = parse_atak_log(ENHANCED)
    positive = [m for m in result.atak_messages if m.open_segments == 5]
    assert len(positive) == 1


# ── Enhanced log — location fields ────────────────────────────────────────────

def test_logging_user_location_parsed():
    result = parse_atak_log(ENHANCED)
    pli = [m for m in result.atak_messages if m.is_pli][0]
    assert pli.logging_user_location == {"lat": 40.71, "long": -74.0, "alt": 10.0}


def test_transmitted_location_on_pli():
    result = parse_atak_log(ENHANCED)
    pli = [m for m in result.atak_messages if m.is_pli][0]
    assert pli.transmitted_location is not None
    assert pli.transmitted_location["lat"] == 40.72


def test_transmitted_location_absent_on_text_chat():
    """textChat carries loggingUserLocation but no transmittedLocation."""
    result = parse_atak_log(ENHANCED)
    chat = [m for m in result.atak_messages if m.is_chat][0]
    assert chat.transmitted_location is None
    assert chat.logging_user_location is not None


# ── Enhanced log — originator fields ──────────────────────────────────────────

def test_originator_uuid_populated_when_present():
    result = parse_atak_log(ENHANCED)
    with_uuid = [m for m in result.atak_messages if m.originator_uuid]
    assert any(m.originator_uuid.startswith("ANDROID-") for m in with_uuid)


def test_originator_uuid_empty_when_missing():
    """originatorUUID missing in the record → empty string, not an error."""
    result = parse_atak_log(ENHANCED)
    chat = [m for m in result.atak_messages if m.is_chat][0]
    assert chat.originator_uuid == ""


def test_originator_callsign_always_empty():
    """originatorCallsign is empty in observed samples — confirm parser keeps it."""
    result = parse_atak_log(ENHANCED)
    for m in result.atak_messages:
        assert m.originator_callsign == ""


# ── Enhanced log — events ─────────────────────────────────────────────────────

def test_firmware_update_event_parsed():
    result = parse_atak_log(ENHANCED)
    fw = [e for e in result.atak_events if e.event_type == "firmwareUpdate"]
    assert len(fw) == 1
    assert fw[0].update_status == "STARTED"
    assert fw[0].update_time_ms == 1780500003000


def test_device_disconnected_location_parsed():
    result = parse_atak_log(ENHANCED)
    dd = [e for e in result.atak_events if e.event_type == "deviceDisconnected"]
    assert len(dd) == 1
    assert dd[0].location == {"lat": 40.7128, "long": -74.006, "alt": 12.5}


# ── Enhanced log — mapObject objectType ───────────────────────────────────────

def test_object_type_on_map_object():
    result = parse_atak_log(ENHANCED)
    pins = [m for m in result.atak_messages if m.message_object_type == "PIN"]
    assert len(pins) == 1
    assert pins[0].is_map_object


# ── Multi-serial / radio swap — Battery chart per-serial data contract ────────
# The Battery chart groups battery_pct by serial_number and detects radio swaps
# from distinct serials. The swap logic itself is JSX (no JS test harness here),
# so these tests pin the parser/serialization contract it relies on.

def test_multiserial_fixture_exists():
    assert MULTISERIAL.exists(), f"Fixture missing: {MULTISERIAL}"


def test_two_distinct_serials_in_health_samples():
    result = parse_atak_log(MULTISERIAL)
    serials = {h.serial_number for h in result.atak_health_samples if h.serial_number}
    assert serials == {"PNE234100406", "PNE234299999"}


def test_battery_pct_retained_per_serial():
    """Each serial keeps its own battery readings — the chart draws one line each."""
    result = parse_atak_log(MULTISERIAL)
    by_serial = {}
    for h in result.atak_health_samples:
        if h.serial_number and h.battery_pct is not None:
            by_serial.setdefault(h.serial_number, []).append(h.battery_pct)
    assert by_serial["PNE234100406"] == [80, 72]
    assert by_serial["PNE234299999"] == [96, 90]


def test_serial_number_serialized_per_sample():
    """_result_to_dict() must preserve serial_number on each health sample so the
    UI can group battery lines by radio."""
    samples = _result_to_dict(parse_atak_log(MULTISERIAL))["atak_health_samples"]
    serials = {s["serial_number"] for s in samples if s.get("serial_number")}
    assert serials == {"PNE234100406", "PNE234299999"}
