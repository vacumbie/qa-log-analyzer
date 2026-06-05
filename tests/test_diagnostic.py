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
    result = parse_diagnostic_log(FIXTURE_DIR / "diagnostic_sample.txt")
    assert result.parse_errors == [], f"Unexpected errors: {result.parse_errors}"


def test_avg_rssi_is_na_for_health_score():
    """Diagnostic logs carry no GRIP session-level RSSI aggregate, so the Health
    Score RSSI dimension is N/A (avg_rssi is None) — excluded from the score
    denominator rather than scored as a free pass."""
    summary = _result_to_dict(parse_diagnostic_log(FIXTURE_DIR / "diagnostic_sample.txt"))["summary"]
    assert summary["avg_rssi"] is None


def test_missing_file_returns_error():
    result = parse_diagnostic_log(Path("nonexistent_file.txt"))
    assert len(result.parse_errors) > 0
