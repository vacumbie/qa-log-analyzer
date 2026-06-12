"""tests/test_diagnostic.py"""

from pathlib import Path

from parser.diagnostic import parse_diagnostic_log
from api.routes.parse import _result_to_dict

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_parses_device_info():
    result = parse_diagnostic_log(FIXTURE_DIR / "diagnostic_sample.txt")
    assert result.log_format == "diagnostic"
    assert result.device.callsign == "RSO_HagenM"
    assert result.device.app_version == "2.2.1"
    assert result.device.build_number == "15"
    assert result.device.radio_firmware == "3.1.11"


def test_parses_received_messages():
    result = parse_diagnostic_log(FIXTURE_DIR / "diagnostic_sample.txt")
    assert len(result.received_messages) > 0
    msg = result.received_messages[0]
    assert msg.data_type in ("broadcast", "1to1")
    assert msg.hop_count is not None
    assert msg.rssi_raw is not None
    assert msg.rssi_dbm == msg.rssi_raw - 256


def test_pli_vs_chat_split():
    result = parse_diagnostic_log(FIXTURE_DIR / "diagnostic_sample.txt")
    pli  = result.pli_messages
    chat = result.chat_messages
    assert len(pli) + len(chat) == len(result.received_messages)
    assert all(m.message_type == "location" for m in pli)
    assert all(m.message_type == "text" for m in chat)


def test_session_timestamps():
    result = parse_diagnostic_log(FIXTURE_DIR / "diagnostic_sample.txt")
    assert result.session_start != ""
    assert result.session_end   != ""
    assert result.session_start <= result.session_end


def test_system_samples():
    result = parse_diagnostic_log(FIXTURE_DIR / "diagnostic_sample.txt")
    assert len(result.system_samples) > 0
    sample = result.system_samples[0]
    assert sample.battery_pct is not None
    assert sample.pa_temp_c is not None


def test_no_parse_errors():
    # The sample fixture's Received Message blocks include originator callsign
    # and GID, so the firmware-3.1.11 omission limitation must NOT fire here.
    result = parse_diagnostic_log(FIXTURE_DIR / "diagnostic_sample.txt")
    assert result.parse_errors == [], f"Unexpected errors: {result.parse_errors}"


# ── Firmware 3.1.11 originator-identity omission (DATA LIMITATION) ─────────────
# 3.1.11 is known to drop originator callsign + GID from Received Message blocks.
# The limitation is surfaced only when it actually manifests (data-driven), so a
# log that includes the identity fields stays clean (covered by test_no_parse_errors).

def test_missing_identity_limitation_emitted():
    result = parse_diagnostic_log(FIXTURE_DIR / "diagnostic_3111_no_identity_sample.txt")
    limits = [e for e in result.parse_errors if e.startswith("DATA LIMITATION —")]
    assert any("omits originator callsign and GID" in e for e in limits), result.parse_errors
    # The affected messages still parse — identity fields are simply empty.
    assert all(not m.originator_callsign and not m.originator_gid
               for m in result.received_messages)


def test_no_missing_identity_limitation_when_present():
    result = parse_diagnostic_log(FIXTURE_DIR / "diagnostic_sample.txt")
    assert not any("omits originator callsign and GID" in e for e in result.parse_errors)


def test_partial_identity_limitation_reports_correct_count():
    """Mixed session: 1 of 2 Received Messages omits identity. The limitation must
    fire AND report the true affected count, not all-or-nothing."""
    result = parse_diagnostic_log(FIXTURE_DIR / "diagnostic_3111_partial_identity_sample.txt")
    limits = [e for e in result.parse_errors if e.startswith("DATA LIMITATION —")]
    affected = [e for e in limits if "omits originator callsign and GID" in e]
    assert len(affected) == 1, result.parse_errors
    assert "1 of 2 received messages affected" in affected[0], affected[0]


def test_avg_rssi_is_na_for_health_score():
    """Diagnostic logs carry no GRIP session-level RSSI aggregate, so the Health
    Score RSSI dimension is N/A (avg_rssi is None) — excluded from the score
    denominator rather than scored as a free pass."""
    summary = _result_to_dict(parse_diagnostic_log(FIXTURE_DIR / "diagnostic_sample.txt"))["summary"]
    assert summary["avg_rssi"] is None


def test_missing_file_returns_error():
    result = parse_diagnostic_log(Path("nonexistent_file.txt"))
    assert len(result.parse_errors) > 0
