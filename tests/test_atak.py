"""
tests/test_atak.py
Tests for parser/atak.py — ATAK plug-in log parser.
"""

import json
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

# Synthetic fixture reproducing the '--- RSDK LOGS ---' divider pattern (main
# array closes mid-file, more bare sdk_log records follow) plus Frequency
# SET command attempts (QUEUED/COMPLETED/FAILED) and a relayModeUpdated
# event — all first observed 2026-06-04 across 7 real field logs
# (BAMA/FONZ-B/HOTLIPS/BIRD/CL_B/DARE/gt_Sassy_B_Net).
FREQ_DIVIDER_FIXTURE = FIXTURE_DIR / "atak_frequency_and_divider_sample.json"

# Edge-case companion to FREQ_DIVIDER_FIXTURE: clientRequest records whose
# optional fields are absent or whose status falls outside the observed
# vocabulary, plus relayModeUpdated with the flag OFF and with the flag
# missing entirely. The three non-radio-config commands (Gid, Location,
# GetDeviceAlert) are copied verbatim from the real KNOT field log in docs/ --
# they are the command types that actually share the clientRequest shape, and
# must not be misread as frequency attempts or mode polls.
CLIENT_REQUEST_EDGE_FIXTURE = FIXTURE_DIR / "atak_client_request_edge_cases.json"

# Same '--- RSDK LOGS ---' layout as the real KNOT log (array close on the last
# in-array record line, blank line, divider, blank line, bare sdk records),
# but the final record is cut off mid-object -- the abrupt-app-kill/rotation
# shape. Pins that skipping divider lines and stripping the array-close bracket
# did not turn the loader into a blanket error suppressor.
TRUNCATED_RECORD_FIXTURE = FIXTURE_DIR / "atak_truncated_final_record.json"

# Mixed-action commands, modelled on the real MESMER log (2026-06-04), which
# carries both Frequency action=GET and NetworkMode action=SET -- neither of
# which had been observed when the frequency/mode parsing was first written.
# A GET is a query, not a change attempt, and a mode SET is a change command,
# not a poll; the UI splits on `action` to label them, so `action` must survive
# serialization. The last record omits `action` entirely: unknown, not SET.
MIXED_ACTION_FIXTURE = FIXTURE_DIR / "atak_mixed_action_commands.json"

# Synthetic ATAK plugin v3.0 build ebb7b8c5 log (2026-10-02 shape). All
# identities and positions are fake. Named in the real build's filename form --
# a space before the time and dotted milliseconds -- deliberately: _FILENAME_RE
# does not match that form (deferred, see parsing-requirements.md), so this
# fixture proves callsign/GID still resolve from content, exactly as they must
# for the real files. Contains: a CONNECTING health record with serialNumber
# "Unknown" ahead of real-serial records; cotDispatchedToAtak EXTERNAL/INTERNAL
# pairs (a PLI and an iOS-created u-d-c-c circle whose <creator> carries the
# real logs' time='1970-01-01…' placeholder), an unpaired b-t-f GeoChat and the
# BROADCAST token-request; received, sent-broadcast and sent-private messages
# with the new identity fields; one older-shape message without them; and the
# '--- RSDK LOGS ---' sdk section.
V3_EBB7B8C5_FIXTURE = FIXTURE_DIR / "diagnostic_ALPHA_90000000000001_2026-10-02 13_26_58.66.log"
ALPHA_UUID = "ANDROID-0000000000000001"
BRAVO_UUID = "ANDROID-0000000000000002"
CHARLIE_UUID = "00000000-0000-4000-8000-000000000003"   # iOS-style sender UUID

# Radio-serial source fixtures (ATAK rule 19). Serials are distinct per source
# -- health PNE000000001, deviceConnected PNE000000002, sdkError deviceState
# PNE000000003 -- so each test can tell which source won.
SERIAL_SOURCES_DISAGREE = FIXTURE_DIR / "atak_v3_serial_sources_disagree.json"
SERIAL_FROM_DEVICE_CONNECTED = FIXTURE_DIR / "atak_v3_serial_from_device_connected.json"
SERIAL_FROM_SDK_DEVICE_STATE = FIXTURE_DIR / "atak_v3_serial_from_sdk_device_state.json"
SERIAL_UNKNOWN_EVERYWHERE = FIXTURE_DIR / "atak_v3_serial_unknown_everywhere.json"

# JSON-null serialNumber variants of the fixtures above. No real log has been
# seen with a null serial -- these exist because record.get("serialNumber", "")
# returns None (not the "" default) when the key is present but null, and that
# None once leaked through to device.radio_serial and serialized as null.
SERIAL_NULL_THEN_REAL = FIXTURE_DIR / "atak_v3_serial_null_then_real.json"
SERIAL_NULL_EVERYWHERE = FIXTURE_DIR / "atak_v3_serial_null_everywhere.json"
SERIAL_NULL_ON_DEVICE_CONNECTED = FIXTURE_DIR / "atak_v3_serial_null_on_device_connected.json"


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


def test_v3_named_fixture_exists():
    """Unlike NAMED_FIXTURE (real data, intentionally uncommitted), the v3
    fixture is synthetic and must be present — otherwise the two filename
    tests below would pass on filename-string parsing of a missing file,
    never actually reading the log."""
    assert V3_NAMED_FIXTURE.exists(), f"Fixture missing: {V3_NAMED_FIXTURE}"


def test_v3_named_fixture_actually_parses():
    """Guard against the false-positive path: _parse_filename runs on the
    path name before the file is read, so a missing fixture would still yield
    a callsign/GID while the read silently errors. Confirm the file was really
    read — no 'Could not read file' entry — so the filename assertions below
    reflect a genuine parse."""
    result = parse_atak_log(V3_NAMED_FIXTURE)
    assert not any("Could not read file" in e for e in result.parse_errors)
    assert len(result.atak_messages) > 0


def test_callsign_from_v3_filename_without_atak_segment():
    """v3.0 plugin filenames drop the ATAK_ segment; callsign must still
    extract from diagnostic_<CALLSIGN>_<GID>_<DATE>_<TIME>.log."""
    result = parse_atak_log(V3_NAMED_FIXTURE)
    assert result.device.callsign == "KESTREL"


def test_gid_from_v3_filename_without_atak_segment():
    result = parse_atak_log(V3_NAMED_FIXTURE)
    assert result.device.gid == "11223"


def test_v3_filename_callsign_wins_over_sender_callsign():
    """Filename is the primary callsign source; the senderCallsign fallback
    must NOT override it. The KESTREL fixture's own sent message reports
    senderCallsign=KESTREL, but a matching filename is what sets device.callsign
    — proven here because a received message carries a different callsign
    (TALON) yet device.callsign stays the filename-derived KESTREL."""
    result = parse_atak_log(V3_NAMED_FIXTURE)
    received = [m for m in result.atak_messages if not m.is_sender]
    assert received[0].sender_callsign == "TALON"
    assert result.device.callsign == "KESTREL"


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


def test_pli_interval_serialized_for_ui():
    """UI-data-path guard: the Originator PLI fix reads m.pli_interval from the
    serialized atak_messages, not the dataclass. Confirm the 5s cadence
    survives _result_to_dict() — a serialization drop would silently revert the
    fix to gap inference, which has no 5s bucket."""
    msgs = _result_to_dict(parse_atak_log(V3_5S_PLI_FIXTURE))["atak_messages"]
    sent_pli = [m for m in msgs if m["message_type"] == "pli" and m["is_sender"]]
    assert len(sent_pli) == 3
    assert all(m["pli_interval"] == "5" for m in sent_pli)


def test_rsdk_logs_divider_not_a_parse_error():
    """Some field logs append a second, unwrapped section after the main
    array closes (a '--- RSDK LOGS ---' divider followed by more bare
    sdk_log records). That divider — and the mid-file array-close artifact
    on the line before it — must not be logged as parse errors; only the
    informational DATA LIMITATION entries should remain."""
    result = parse_atak_log(FREQ_DIVIDER_FIXTURE)
    hard_errors = [e for e in result.parse_errors if not e.startswith("DATA LIMITATION")]
    assert hard_errors == []


def test_relay_mode_updated_event_captured():
    result = parse_atak_log(FREQ_DIVIDER_FIXTURE)
    relay_events = [e for e in result.atak_events if e.event_type == "relayModeUpdated"]
    assert len(relay_events) == 1
    assert relay_events[0].relay_mode_enabled is True


def test_frequency_set_attempts_extracted_with_statuses():
    """Frequency SET command attempts come from SDK Logging 2.0
    clientRequest records, not the app-level frequencyUpdated event — this
    is the raw radio-command layer, and observed statuses are QUEUED,
    COMPLETED, and FAILED."""
    result = parse_atak_log(FREQ_DIVIDER_FIXTURE)
    attempts = result.atak_frequency_set_attempts
    assert len(attempts) == 3
    statuses = [a.status for a in attempts]
    assert statuses == ["QUEUED", "COMPLETED", "FAILED"]
    # Every command in this fixture happens to be a SET; mixed SET/GET traffic
    # is covered by test_frequency_get_commands_kept_and_tagged_with_their_action
    assert all(a.action == "SET" for a in attempts)
    # Hz -> MHz conversion: 464550000hz -> 464.55 MHz
    assert attempts[0].channels[0]["frequency"] == 464.55
    assert attempts[0].channels[0]["isControlChannel"] is True


def test_client_request_additional_info_captured():
    """additionalInfo can live under message.event OR message.clientRequest
    — both shapes must feed counts_by_info, not just the older .event shape."""
    result = parse_atak_log(FREQ_DIVIDER_FIXTURE)
    info = result.atak_sdk_error_summary.counts_by_info
    assert "Request is not valid for reason atakplugin.gotennaproag.fh1$c" in info
    assert "Gatt write back off reached skipping write" in info


def test_network_mode_and_tether_mode_queries_extracted():
    """NetworkMode/TetherMode clientRequest records are usually GET-polls of
    current state — distinct from AtakFrequencySetAttempt. Every record in THIS
    fixture is a GET; action=SET also occurs in real logs and is covered by
    test_mode_change_commands_distinguishable_from_polls. Status vocabulary keeps
    growing (QUEUED/COMPLETED/FAILED/CANCELLED/TIMEOUT observed) — don't assume
    a fixed set."""
    result = parse_atak_log(FREQ_DIVIDER_FIXTURE)
    queries = result.atak_radio_mode_queries
    assert len(queries) == 2

    listen_only = next(q for q in queries if q.mode_type == "listenOnly")
    assert listen_only.value is True
    assert listen_only.status == "COMPLETED"
    assert listen_only.action == "GET"

    tether = next(q for q in queries if q.mode_type == "tether")
    assert tether.value is False
    assert tether.status == "CANCELLED"
    assert tether.battery_threshold == 20


def test_health_mode_listen_only_captured():
    """The health record's own `mode` field is the confirmed-state signal —
    LISTEN_ONLY has been observed in real field logs, not just NORMAL."""
    result = parse_atak_log(FREQ_DIVIDER_FIXTURE)
    modes = [h.mode for h in result.atak_health_samples]
    assert "LISTEN_ONLY" in modes


def test_every_channel_in_a_multichannel_set_is_retained():
    """A SET command carries the whole channel plan, not just the control
    channel. Asserting only channels[0] would pass even if the regex stopped
    after the first match and silently dropped the rest of the plan."""
    result = parse_atak_log(FREQ_DIVIDER_FIXTURE)
    queued = result.atak_frequency_set_attempts[0]
    freqs = [c["frequency"] for c in queued.channels]
    assert freqs == [464.55, 469.55, 469.5]


def test_non_control_channels_flagged_false():
    """isControlChannel comes from a YES/NO literal in the raw command string.
    A NO must become False -- not True, and not the bare string. Only the
    first channel is the control channel in the observed plans."""
    result = parse_atak_log(FREQ_DIVIDER_FIXTURE)
    flags = [c["isControlChannel"] for c in result.atak_frequency_set_attempts[0].channels]
    assert flags == [True, False, False]


def test_failed_attempt_keeps_its_own_channel_plan():
    """A FAILED attempt is still a real attempt with real requested channels --
    its single-channel plan must survive, not be blanked because the command
    did not succeed."""
    result = parse_atak_log(FREQ_DIVIDER_FIXTURE)
    failed = next(a for a in result.atak_frequency_set_attempts if a.status == "FAILED")
    assert failed.channels == [{"frequency": 445.5, "isControlChannel": True}]


def test_all_post_divider_sdk_records_consumed():
    """Every record after the divider must reach the sdkError aggregate --
    including the three whose rawRequest the frequency and mode branches
    ignore. A record dropped by the loader would show up as a lower total."""
    result = parse_atak_log(FREQ_DIVIDER_FIXTURE)
    assert result.atak_sdk_error_summary.total_count == 6


def test_frequency_set_attempts_serialized_for_ui():
    """UI-data-path guard: the Originator Frequency card reads
    atak_frequency_set_attempts from the serialized dict, including the nested
    channel dicts. A missing _result_to_dict() block would leave the card
    silently empty with the parser still green."""
    d = _result_to_dict(parse_atak_log(FREQ_DIVIDER_FIXTURE))
    attempts = d["atak_frequency_set_attempts"]
    assert [a["status"] for a in attempts] == ["QUEUED", "COMPLETED", "FAILED"]
    assert attempts[1]["channels"][0] == {"frequency": 464.55, "isControlChannel": True}


def test_radio_mode_queries_serialized_for_ui():
    """UI-data-path guard: the Radio Mode card groups poll counts by mode_type
    and status from the serialized dict, not the dataclass."""
    d = _result_to_dict(parse_atak_log(FREQ_DIVIDER_FIXTURE))
    queries = d["atak_radio_mode_queries"]
    assert {(q["mode_type"], q["status"]) for q in queries} == {
        ("listenOnly", "COMPLETED"), ("tether", "CANCELLED")
    }


def test_relay_mode_enabled_serialized_for_ui():
    """UI-data-path guard: the Radio Mode card builds relay segments from
    relay_mode_enabled on the serialized atak_events."""
    d = _result_to_dict(parse_atak_log(FREQ_DIVIDER_FIXTURE))
    relay = [e for e in d["atak_events"] if e["event_type"] == "relayModeUpdated"]
    assert relay[0]["relay_mode_enabled"] is True


def test_relay_mode_turned_off_recorded_as_false():
    """An explicit isRelayModeEnabled=false is a confirmed OFF, and must be
    stored as False -- distinct from the absent-flag case below, which is
    unknown. The pair is what keeps the UI from rendering unknown as OFF."""
    result = parse_atak_log(CLIENT_REQUEST_EDGE_FIXTURE)
    relay = [e for e in result.atak_events if e.event_type == "relayModeUpdated"]
    assert relay[0].relay_mode_enabled is False


def test_relay_mode_missing_flag_stays_none():
    """An event with no isRelayModeEnabled is unknown, not OFF. Coercing it to
    False would let the UI merge an unknown stretch into a confirmed
    relay-mode-off segment."""
    result = parse_atak_log(CLIENT_REQUEST_EDGE_FIXTURE)
    relay = [e for e in result.atak_events if e.event_type == "relayModeUpdated"]
    assert relay[1].relay_mode_enabled is None


def test_unobserved_client_request_status_preserved_verbatim():
    """The status vocabulary is documented as an open set -- QUEUED, COMPLETED,
    FAILED, CANCELLED and TIMEOUT are what has been seen, not what is allowed.
    TIMED_OUT below is deliberately a value never observed in any log: a value
    outside the known set must pass through unchanged rather than be normalized,
    bucketed as unknown, or dropped."""
    result = parse_atak_log(CLIENT_REQUEST_EDGE_FIXTURE)
    listen_only = next(q for q in result.atak_radio_mode_queries
                       if q.mode_type == "listenOnly")
    assert listen_only.status == "TIMED_OUT"


def test_missing_client_request_status_is_empty_not_dropped():
    """A clientRequest with no status key at all still describes a real
    attempt -- it must be captured with an empty status, not skipped."""
    result = parse_atak_log(CLIENT_REQUEST_EDGE_FIXTURE)
    assert len(result.atak_frequency_set_attempts) == 1
    assert result.atak_frequency_set_attempts[0].status == ""


def test_tether_query_without_battery_threshold_stays_none():
    """batteryThreshold is optional in the TetherMode command string. Absent
    must mean None (unknown), never 0 -- a 0 percent threshold is a
    meaningful, wrong reading."""
    result = parse_atak_log(CLIENT_REQUEST_EDGE_FIXTURE)
    tether = next(q for q in result.atak_radio_mode_queries if q.mode_type == "tether")
    assert tether.battery_threshold is None


def test_non_radio_config_client_requests_ignored():
    """Gid, Location and GetDeviceAlert share the clientRequest shape but are
    not radio-config commands. They must land in neither list -- misclassifying
    them would inflate the SET-attempt and poll counts with unrelated traffic."""
    result = parse_atak_log(CLIENT_REQUEST_EDGE_FIXTURE)
    assert len(result.atak_frequency_set_attempts) == 1
    assert len(result.atak_radio_mode_queries) == 2


def test_no_client_request_records_yields_empty_lists():
    """A log with no clientRequest records must serialize both keys as empty
    lists -- present and empty, so the UI fallback is never the thing keeping
    the card alive."""
    d = _result_to_dict(parse_atak_log(ENHANCED))
    assert d["atak_frequency_set_attempts"] == []
    assert d["atak_radio_mode_queries"] == []


def test_truncated_final_record_still_reported_as_parse_error():
    """The loader skips lines that do not open a JSON object (section dividers)
    and strips a trailing array-close bracket. Neither may swallow genuine
    corruption: a record cut off mid-object must still be surfaced."""
    result = parse_atak_log(TRUNCATED_RECORD_FIXTURE)
    hard_errors = [e for e in result.parse_errors if not e.startswith("DATA LIMITATION")]
    assert len(hard_errors) == 1
    assert "JSON parse error" in hard_errors[0]


def test_valid_records_around_a_truncated_one_still_parsed():
    """One corrupt trailing line must not cost the rest of the session -- the
    pre-divider health record and the post-divider SET attempt both survive."""
    result = parse_atak_log(TRUNCATED_RECORD_FIXTURE)
    assert len(result.atak_health_samples) == 1
    assert [a.status for a in result.atak_frequency_set_attempts] == ["COMPLETED"]


def test_frequency_get_commands_kept_and_tagged_with_their_action():
    """A Frequency command can be action=GET (asking what the radio is on) as
    well as action=SET. GETs must be kept -- dropping them would lose real
    observations -- but tagged with their own action, since counting a query as
    a change attempt is what the MESMER log exposed (12 of its 28 are GETs)."""
    result = parse_atak_log(MIXED_ACTION_FIXTURE)
    actions = [a.action for a in result.atak_frequency_set_attempts]
    assert actions == ["SET", "GET", "GET", ""]


def test_mode_change_commands_distinguishable_from_polls():
    """NetworkMode/TetherMode records are mostly GET polls, but action=SET does
    occur and those are real mode-change commands. Both land in one list, so
    `action` is the only thing separating a change command from a poll -- if it
    were dropped, a confirmed mode change would be counted as a poll."""
    result = parse_atak_log(MIXED_ACTION_FIXTURE)
    pairs = [(q.mode_type, q.action) for q in result.atak_radio_mode_queries]
    assert pairs == [("listenOnly", "SET"), ("listenOnly", "GET"), ("tether", "SET")]


def test_command_action_survives_serialization():
    """UI-data-path guard: the Freq/RSSI and Modes cards bucket by `action` to
    label SET attempts vs GET queries and polls vs change cmds. If `action` were
    missing from _result_to_dict() every record would collapse into one bucket
    and the labels would silently lie again."""
    d = _result_to_dict(parse_atak_log(MIXED_ACTION_FIXTURE))
    assert [a["action"] for a in d["atak_frequency_set_attempts"]] == \
        ["SET", "GET", "GET", ""]
    assert [q["action"] for q in d["atak_radio_mode_queries"]] == \
        ["SET", "GET", "SET"]


def test_command_with_no_action_is_empty_not_assumed_set():
    """A command string with no action= at all is unknown, not SET. Defaulting
    it to SET would overstate change attempts; the UI gives it its own
    'action unknown' bucket."""
    result = parse_atak_log(MIXED_ACTION_FIXTURE)
    no_action = result.atak_frequency_set_attempts[-1]
    assert no_action.action == ""
    assert no_action.status == "QUEUED"       # still a real, retained record


def test_real_timeout_status_passes_through():
    """TIMEOUT is a real observed status (MESMER, 2026-06-04) that surfaced only
    after QUEUED/COMPLETED/FAILED/CANCELLED were documented -- direct evidence
    the vocabulary is open. It must survive verbatim, like any other value."""
    result = parse_atak_log(MIXED_ACTION_FIXTURE)
    statuses = {a.status for a in result.atak_frequency_set_attempts}
    assert "TIMEOUT" in statuses


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


# ── ATAK plugin v3.0 build ebb7b8c5 — identity from a real-form filename ──────

def test_v3_ebb7b8c5_fixture_exists():
    assert V3_EBB7B8C5_FIXTURE.exists(), f"Fixture missing: {V3_EBB7B8C5_FIXTURE}"


def test_ebb7b8c5_callsign_resolves_from_own_sent_message():
    """The real build's filename form (space + dotted ms) does not match
    _FILENAME_RE, so callsign must come from the device's own sent
    senderCallsign. Received messages name other callsigns (BRAVO, CHARLIE) --
    picking one of those would mislabel the whole device."""
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    assert result.device.callsign == "ALPHA"


def test_ebb7b8c5_gid_resolves_from_health_record():
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    assert result.device.gid == "90000000000001"


# ── Build ebb7b8c5 — radio serial: "Unknown" is a placeholder (ATAK rule 19) ──

def test_unknown_serial_on_first_health_record_not_used_as_radio_serial():
    """The first health record (CONNECTING) logs serialNumber "Unknown" before
    the radio reports in. Before the fix, first-record-wins made every
    build ebb7b8c5 device report its radio as "Unknown"."""
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    assert result.device.radio_serial == "PNE000000001"


def test_connecting_health_sample_keeps_unknown_serial_as_logged():
    """Only the device-level identity skips the placeholder -- the per-sample
    record stays exactly as logged, so the Battery chart still sees it."""
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    first = result.atak_health_samples[0]
    assert first.connection_state == "CONNECTING"
    assert first.serial_number == "Unknown"


def test_health_samples_after_connect_carry_the_real_serial():
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    later_serials = []
    for sample in result.atak_health_samples[1:]:
        later_serials.append(sample.serial_number)
    assert later_serials == ["PNE000000001", "PNE000000001", "PNE000000001"]


def test_health_serial_wins_over_earlier_device_connected_and_sdk_serials():
    """Priority is health > deviceConnected > sdkError deviceState, regardless
    of record order. deviceConnected (PNE000000002) is logged *before* the first
    real health serial here, as in the real logs -- a first-seen-wins
    implementation would pick it."""
    result = parse_atak_log(SERIAL_SOURCES_DISAGREE)
    assert result.device.radio_serial == "PNE000000001"


def test_device_connected_serial_used_when_health_only_reports_unknown():
    """Every health record is CONNECTING/"Unknown". deviceConnected
    (PNE000000002) must win over the sdkError deviceState (PNE000000003)."""
    result = parse_atak_log(SERIAL_FROM_DEVICE_CONNECTED)
    assert result.device.radio_serial == "PNE000000002"


def test_sdk_device_state_serial_used_when_no_other_source_has_one():
    """No deviceConnected event and no real health serial. The retained sdkError
    sample itself carries "Unknown" (precondition below), so the fallback must
    skip it and take the real serial from the distinct serial_numbers."""
    result = parse_atak_log(SERIAL_FROM_SDK_DEVICE_STATE)
    assert result.atak_sdk_error_summary.sample.serial_number == "Unknown"
    assert result.device.radio_serial == "PNE000000003"


def test_radio_serial_stays_empty_when_no_source_has_a_real_serial():
    """"" means unknown; "Unknown" would read as an actual serial in the UI."""
    result = parse_atak_log(SERIAL_UNKNOWN_EVERYWHERE)
    assert result.device.radio_serial == ""


def test_resolved_radio_serial_serialized_for_ui():
    d = _result_to_dict(parse_atak_log(V3_EBB7B8C5_FIXTURE))
    assert d["device"]["radio_serial"] == "PNE000000001"


def test_unknown_serial_on_health_sample_survives_serialization():
    """The as-logged placeholder must reach the API too -- not be blanked or
    back-filled with the resolved serial on the way out."""
    samples = _result_to_dict(parse_atak_log(V3_EBB7B8C5_FIXTURE))["atak_health_samples"]
    assert samples[0]["serial_number"] == "Unknown"


def test_health_samples_carry_one_real_serial_beside_the_placeholder():
    """The exact input the Battery chart's multi-serial warning sees for a
    single-radio ebb7b8c5 session: one real serial plus the "Unknown"
    reconnect placeholder. hasMultiSerial in ChartPanel.jsx must count that as
    ONE radio; this pins the API side of that contract (the JSX predicate
    itself has no test runner to guard it)."""
    samples = _result_to_dict(parse_atak_log(V3_EBB7B8C5_FIXTURE))["atak_health_samples"]
    serials = {s["serial_number"] for s in samples}
    assert serials == {"Unknown", "PNE000000001"}


# ── Radio serial: JSON null is a placeholder too (ATAK rule 19) ───────────────

def test_null_serial_on_first_health_record_not_used_as_radio_serial():
    """A null serial on the CONNECTING record must not claim the device serial;
    the later real health serial wins. Regression guard only -- this also passed
    before None joined _SERIAL_PLACEHOLDERS, because a None radio_serial is
    falsy and the next real serial overwrote it."""
    result = parse_atak_log(SERIAL_NULL_THEN_REAL)
    assert result.device.radio_serial == "PNE000000001"


def test_null_serial_health_sample_keeps_none_as_logged():
    """Pins current behaviour: the per-sample serial_number is stored exactly as
    the JSON had it, so a null serialNumber stays None on the sample (only the
    device-level identity treats it as a placeholder). Not a judgement that None
    is the ideal per-sample value -- change this test deliberately if that
    contract changes."""
    result = parse_atak_log(SERIAL_NULL_THEN_REAL)
    first = result.atak_health_samples[0]
    assert first.connection_state == "CONNECTING"
    assert first.serial_number is None


def test_radio_serial_is_empty_string_not_none_when_every_source_is_null():
    """Health, deviceConnected and sdkError deviceState all carry null. "" is the
    'unknown' value per rule 19; None would serialize as null."""
    result = parse_atak_log(SERIAL_NULL_EVERYWHERE)
    assert result.device.radio_serial == ""


def test_null_radio_serial_serializes_as_empty_string_not_null():
    d = _result_to_dict(parse_atak_log(SERIAL_NULL_EVERYWHERE))
    assert d["device"]["radio_serial"] == ""


def test_null_device_connected_serial_skipped_in_favour_of_sdk_device_state():
    """Health only reports "Unknown" and deviceConnected's serial is null, so the
    fallback must move past deviceConnected to the sdkError deviceState serial
    (PNE000000003) rather than stopping at the null."""
    result = parse_atak_log(SERIAL_NULL_ON_DEVICE_CONNECTED)
    assert result.device.radio_serial == "PNE000000003"


# ── Build ebb7b8c5 — cotDispatchedToAtak events (ATAK rule 20) ───────────────

def _cot_dispatches(events):
    """cotDispatchedToAtak events from parsed AtakEvents or serialized dicts."""
    dispatches = []
    for e in events:
        event_type = e["event_type"] if isinstance(e, dict) else e.event_type
        if event_type == "cotDispatchedToAtak":
            dispatches.append(e)
    return dispatches


def _raw_cot_xml_in_file(path):
    """Every cotXml string exactly as it appears in the fixture, in file order.
    Read straight from the JSON so the comparison does not go through the
    parser under test."""
    raw = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if '"cotDispatchedToAtak"' not in line:
            continue
        line = line.lstrip("[").rstrip(",").rstrip("]")
        raw.append(json.loads(line)["event"]["cotXml"])
    return raw


def test_every_cot_dispatch_captured():
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    assert len(_cot_dispatches(result.atak_events)) == 8


def test_cot_dispatch_counts_by_type_and_destination():
    """The ATAK tab card counts by (cot_type, destination). A PLI and a drawn
    map object (u-d-c-c circle) pair evenly EXTERNAL/INTERNAL; GeoChat (b-t-f)
    does not -- one chat here was dispatched EXTERNAL only, matching the real
    logs' uneven b-t-f split."""
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    counts = {}
    for e in _cot_dispatches(result.atak_events):
        key = (e.cot_type, e.destination)
        counts[key] = counts.get(key, 0) + 1
    assert counts == {
        ("token-request", "BROADCAST"): 1,
        ("a-f-G-U-C", "EXTERNAL"): 1,
        ("a-f-G-U-C", "INTERNAL"): 1,
        ("b-t-f", "EXTERNAL"): 2,
        ("b-t-f", "INTERNAL"): 1,
        ("u-d-c-c", "EXTERNAL"): 1,
        ("u-d-c-c", "INTERNAL"): 1,
    }


def test_broadcast_destination_is_the_token_request():
    """BROADCAST has only ever been seen on the single token-request at session
    start. Destination is an open set -- it must pass through verbatim."""
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    broadcast = [e for e in _cot_dispatches(result.atak_events) if e.destination == "BROADCAST"]
    assert len(broadcast) == 1
    assert broadcast[0].cot_type == "token-request"


def test_unpaired_geochat_dispatch_is_kept():
    """CHARLIE's chat was dispatched EXTERNAL with no INTERNAL twin. An
    implementation that de-duplicated or paired dispatches would lose it."""
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    charlie_destinations = []
    for e in _cot_dispatches(result.atak_events):
        if e.cot_type == "b-t-f" and "senderCallsign='CHARLIE'" in e.cot_xml:
            charlie_destinations.append(e.destination)
    assert charlie_destinations == ["EXTERNAL"]


def test_cot_xml_preserved_verbatim():
    """The raw XML is kept so the JSON and CSV exports lose nothing. Any strip,
    unescape, truncation or reformat would break this equality."""
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    parsed = [e.cot_xml for e in _cot_dispatches(result.atak_events)]
    assert parsed == _raw_cot_xml_in_file(V3_EBB7B8C5_FIXTURE)


def test_lifecycle_events_have_empty_cot_fields():
    """cot_* fields belong to cotDispatchedToAtak only. A deviceConnected or
    deviceDisconnected carrying a cot_type would be counted on the CoT card."""
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    lifecycle = [e for e in result.atak_events if e.event_type != "cotDispatchedToAtak"]
    assert [e.event_type for e in lifecycle] == ["deviceDisconnected", "deviceConnected"]
    for e in lifecycle:
        assert (e.cot_type, e.destination, e.cot_xml) == ("", "", "")


def test_cot_dispatches_do_not_displace_lifecycle_fields():
    """Adding a branch to _handle_event must not disturb the existing ones --
    the deviceConnected serial is a radio-serial fallback source."""
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    connected = [e for e in result.atak_events if e.event_type == "deviceConnected"]
    assert connected[0].serial_number == "PNE000000001"


def test_cot_fields_serialized_for_api():
    """UI-data-path guard: the CoT Dispatched card and the CSV export read the
    serialized atak_events, not the dataclass."""
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    serialized = _cot_dispatches(_result_to_dict(result)["atak_events"])
    parsed = _cot_dispatches(result.atak_events)
    assert len(serialized) == len(parsed) == 8
    for s, p in zip(serialized, parsed):
        assert (s["cot_type"], s["destination"], s["cot_xml"]) == (p.cot_type, p.destination, p.cot_xml)


def test_older_logs_serialize_cot_keys_as_empty_strings():
    """Pre-ebb7b8c5 logs have no cotDispatchedToAtak. The keys must still be
    present (one row schema for the CSV export) and empty, never null."""
    events = _result_to_dict(parse_atak_log(ENHANCED))["atak_events"]
    assert len(events) > 0
    for e in events:
        assert (e["cot_type"], e["destination"], e["cot_xml"]) == ("", "", "")


# ── Build ebb7b8c5 — new message identity fields (ATAK rule 21) ──────────────

def _message(result, log_id):
    for m in result.atak_messages:
        if m.log_id == log_id:
            return m
    raise AssertionError(f"no message with logId {log_id} in fixture")


RECEIVED_PLI_FROM_BRAVO = -700000001
SENT_PLI_BROADCAST = 700000002
SENT_PRIVATE_CHAT_TO_CHARLIE = -700000005
SENT_BROADCAST_CHAT = 700000006
OLDER_STYLE_PLI_FROM_DELTA = 700000007


def test_received_message_names_the_local_device_as_receiver():
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    received = _message(result, RECEIVED_PLI_FROM_BRAVO)
    assert received.receiver_callsign == "ALPHA"
    assert received.receiver_uuid == ALPHA_UUID


def test_received_message_carries_sender_uuid():
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    assert _message(result, RECEIVED_PLI_FROM_BRAVO).sender_uuid == BRAVO_UUID


def test_received_message_from_ios_sender_keeps_non_android_uuid():
    """UUIDs are not always ANDROID-*; an iOS sender's plain UUID must pass
    through untouched."""
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    from_charlie = [m for m in result.atak_messages if m.sender_gid == 90000000000003]
    assert from_charlie[0].sender_uuid == CHARLIE_UUID


def test_message_schema_version_captured():
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    assert _message(result, RECEIVED_PLI_FROM_BRAVO).version == 1


def test_sent_broadcast_keeps_receiver_fields_exactly_as_logged():
    """A broadcast has no single receiver: the log writes receiverCallsign ""
    and receiverGid 0. Both are stored as logged -- receiver_gid is the literal
    0, NOT converted to None. That is current behaviour, pinned here so any
    change to it is a deliberate decision (open question: 0 here is a
    "no receiver" placeholder, like sent-message rssi 0)."""
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    sent = _message(result, SENT_BROADCAST_CHAT)
    assert sent.receiver_callsign == ""
    assert sent.receiver_uuid == ""
    assert sent.receiver_gid == 0


def test_sent_pli_broadcast_logs_blank_sender_uuid():
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    assert _message(result, SENT_PLI_BROADCAST).sender_uuid == ""


def test_sent_non_pli_broadcast_keeps_its_sender_uuid():
    """In the real logs only sent PLI broadcasts blank senderUUID; sent chat,
    mapObject and fileTransfer broadcasts carry the local device's UUID. The
    parser must not assume "sent means blank"."""
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    assert _message(result, SENT_BROADCAST_CHAT).sender_uuid == ALPHA_UUID


def test_sent_private_message_names_its_receiver():
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    sent = _message(result, SENT_PRIVATE_CHAT_TO_CHARLIE)
    assert sent.receiver_callsign == "CHARLIE"
    assert sent.receiver_uuid == CHARLIE_UUID
    assert sent.receiver_gid == 90000000000003


def test_older_style_message_defaults_new_strings_to_empty():
    """A record without the ebb7b8c5 fields gets "" -- never a value borrowed
    from a neighbouring record or the device itself."""
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    older = _message(result, OLDER_STYLE_PLI_FROM_DELTA)
    assert (older.receiver_callsign, older.receiver_uuid, older.sender_uuid) == ("", "", "")


def test_older_style_message_version_is_none_not_guessed():
    """Every observed version is 1, which makes defaulting to 1 tempting.
    Absent must stay None."""
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    assert _message(result, OLDER_STYLE_PLI_FROM_DELTA).version is None


def test_pre_ebb7b8c5_fixtures_get_no_invented_identity_fields():
    """Sweep the real-shaped older fixtures: none of their messages carry the
    new fields, so all must come through as "" / None."""
    for fixture in (FIXTURE, ENHANCED):
        for m in parse_atak_log(fixture).atak_messages:
            assert (m.receiver_callsign, m.receiver_uuid, m.sender_uuid) == ("", "", ""), fixture.name
            assert m.version is None, fixture.name


def test_new_message_fields_serialized_for_api():
    msgs = _result_to_dict(parse_atak_log(V3_EBB7B8C5_FIXTURE))["atak_messages"]
    received = next(m for m in msgs if m["log_id"] == RECEIVED_PLI_FROM_BRAVO)
    assert received["receiver_callsign"] == "ALPHA"
    assert received["receiver_uuid"] == ALPHA_UUID
    assert received["sender_uuid"] == BRAVO_UUID
    assert received["version"] == 1


def test_absent_message_version_serializes_as_null():
    msgs = _result_to_dict(parse_atak_log(V3_EBB7B8C5_FIXTURE))["atak_messages"]
    older = next(m for m in msgs if m["log_id"] == OLDER_STYLE_PLI_FROM_DELTA)
    assert older["version"] is None


# ── Build ebb7b8c5 — parse_errors ────────────────────────────────────────────
# DATA LIMITATION decision (vera): none of the three ebb7b8c5 changes warrants a
# new entry. The "Unknown" serial is a placeholder handled without loss (the
# sample keeps it; the device resolves a real one); cot_xml is parsed in full and
# serialized; absent message fields are an older schema, not missing data.
# The only entry this fixture should raise is the pre-existing sdkError one.

def test_ebb7b8c5_fixture_reports_no_hard_parse_errors():
    """The '--- RSDK LOGS ---' section and the long single-quoted XML strings
    must not produce JSON parse errors."""
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    hard_errors = [e for e in result.parse_errors if not e.startswith("DATA LIMITATION")]
    assert hard_errors == []


def test_ebb7b8c5_fixture_raises_only_the_sdk_volume_limitation():
    result = parse_atak_log(V3_EBB7B8C5_FIXTURE)
    limits = [e for e in result.parse_errors if e.startswith("DATA LIMITATION —")]
    assert len(limits) == 1
    assert "sdkError" in limits[0]


def test_unknown_serial_is_not_reported_as_a_parse_error():
    """Even when no source has a real serial, "Unknown" is expected
    reconnection behaviour (CLAUDE.md known limitations), not an error."""
    result = parse_atak_log(SERIAL_UNKNOWN_EVERYWHERE)
    assert result.parse_errors == []
