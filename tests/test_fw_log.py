"""
tests/test_fw_log.py
Tests for parser/fw_log.py — goTenna relay firmware log parser.
"""

import pytest
from pathlib import Path

from parser.fw_log import parse_fw_log, is_fw_log

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURE_DIR / "fw_log_sample.log"


# ── Fixture availability ──────────────────────────────────────────────────────

def test_fixture_exists():
    assert FIXTURE.exists(), f"Fixture missing: {FIXTURE}"


# ── Format detection ──────────────────────────────────────────────────────────

def test_is_fw_log_detects_correctly():
    content = FIXTURE.read_text(encoding="utf-8")
    assert is_fw_log(content) is True


def test_is_fw_log_rejects_non_fw():
    assert is_fw_log('{"logId": 123, "message": {"type": "pli"}}') is False
    assert is_fw_log("some random text\nwithout bracket lines") is False


def test_log_format():
    result = parse_fw_log(FIXTURE)
    assert result.log_format == "fw_log"


# ── Device identity ───────────────────────────────────────────────────────────

def test_origin_hash_captured():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.origin_hash == "0f07"


def test_fw_format_version_captured():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.fw_format_version == "0x10"


# ── Session timestamps ────────────────────────────────────────────────────────

def test_session_timestamps_populated():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.first_ts_ms > 0
    assert result.fw_log_result.last_ts_ms > result.fw_log_result.first_ts_ms
    assert result.fw_log_result.duration_ms > 0


# ── RF configuration ──────────────────────────────────────────────────────────

def test_rf_config_present():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.rf_config is not None


def test_rf_device_type():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.rf_config.device_type == "goTenna Pro"


def test_rf_region():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.rf_config.region == 1


def test_rf_tx_power():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.rf_config.tx_power == 3


def test_rf_bit_rate():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.rf_config.bit_rate == 19200


def test_rf_frequencies():
    result = parse_fw_log(FIXTURE)
    freqs = result.fw_log_result.rf_config.frequencies_hz
    assert 464550000 in freqs
    assert 469550000 in freqs
    assert 469500000 in freqs


def test_rf_control_channels():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.rf_config.control_channels == [0]


def test_rf_data_channels():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.rf_config.data_channels == [1, 2]


# ── Bucket history ────────────────────────────────────────────────────────────

def test_buckets_present():
    result = parse_fw_log(FIXTURE)
    assert len(result.fw_log_result.buckets) == 12


def test_bucket_most_recent_correct():
    """bucket[11] = 0-6 hours ago — most recent window."""
    result = parse_fw_log(FIXTURE)
    b11 = next(b for b in result.fw_log_result.buckets if b.bucket_index == 11)
    assert b11.rx == 100
    assert b11.relayed == 30
    assert b11.tx == 1
    assert b11.hrs_start == 0
    assert b11.hrs_end == 6


def test_bucket_index_9_parsed():
    """bucket[09] = 12-18 hours ago — verify a mid-history window parses correctly."""
    result = parse_fw_log(FIXTURE)
    b09 = next(b for b in result.fw_log_result.buckets if b.bucket_index == 9)
    assert b09.rx == 21
    assert b09.relayed == 4
    assert b09.tx == 0


def test_buckets_sorted_descending():
    """Buckets returned newest first (index 11 → 0)."""
    result = parse_fw_log(FIXTURE)
    indices = [b.bucket_index for b in result.fw_log_result.buckets]
    assert indices == sorted(indices, reverse=True)


# ── Routing decisions ─────────────────────────────────────────────────────────

def test_routing_present():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.routing is not None


def test_routing_transmit_count():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.routing.transmit == 1


def test_routing_echo_count():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.routing.echo == 1


def test_routing_vine_count():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.routing.vine == 1


def test_routing_skip_rx_count():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.routing.skip_rx == 1


def test_routing_skip_tx_count():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.routing.skip_tx == 1


# ── Neighbors ─────────────────────────────────────────────────────────────────

def test_neighbors_captured():
    result = parse_fw_log(FIXTURE)
    assert "e1a5" in result.fw_log_result.neighbor_hashes
    assert "83e5" in result.fw_log_result.neighbor_hashes


def test_neighbors_deduplicated():
    result = parse_fw_log(FIXTURE)
    hashes = result.fw_log_result.neighbor_hashes
    assert len(hashes) == len(set(hashes))


# ── Energy samples ────────────────────────────────────────────────────────────

def test_energy_samples_present():
    result = parse_fw_log(FIXTURE)
    assert len(result.fw_log_result.energy_samples) == 3


def test_energy_values_are_negative_dbm():
    result = parse_fw_log(FIXTURE)
    for e in result.fw_log_result.energy_samples:
        assert e < 0, f"Energy sample {e} should be negative dBm"


# ── Errors and warnings ───────────────────────────────────────────────────────

def test_battery_error_count():
    """Battery stabilization errors counted separately as known firmware quirk."""
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.battery_error_count == 2


def test_other_errors_counted():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.error_counts.get("USB", 0) == 1


def test_warnings_counted():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.warn_counts.get("RELAY", 0) == 1


def test_warn_message_captured():
    result = parse_fw_log(FIXTURE)
    assert any("fullFlood" in m for m in result.fw_log_result.warn_messages)


# ── Debug lines skipped ───────────────────────────────────────────────────────

def test_debug_lines_skipped():
    """DEBUG lines must not be parsed — skipped_debug count must be > 0."""
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.skipped_debug > 0


def test_debug_not_in_parsed():
    """parsed_lines + skipped_debug should equal the total non-empty lines."""
    result = parse_fw_log(FIXTURE)
    fw = result.fw_log_result
    # Total bracket lines = parsed + skipped
    assert fw.parsed_lines > 0
    assert fw.skipped_debug > 0


# ── RHC polls ─────────────────────────────────────────────────────────────────

def test_rhc_poll_count():
    result = parse_fw_log(FIXTURE)
    assert result.fw_log_result.rhc_poll_count == 1


# ── Data limitations ──────────────────────────────────────────────────────────

def test_data_limitations_present():
    result = parse_fw_log(FIXTURE)
    limits = [e for e in result.parse_errors if e.startswith("DATA LIMITATION")]
    assert len(limits) == 3


def test_timestamp_limitation_present():
    result = parse_fw_log(FIXTURE)
    assert any("relative ms from boot" in e for e in result.parse_errors)


def test_serial_limitation_present():
    result = parse_fw_log(FIXTURE)
    assert any("binary RHC" in e for e in result.parse_errors)


def test_battery_limitation_present():
    result = parse_fw_log(FIXTURE)
    assert any("Battery stabilization" in e for e in result.parse_errors)


# ── Error handling ────────────────────────────────────────────────────────────

def test_missing_file_returns_error():
    result = parse_fw_log(Path("nonexistent_fw.log"))
    assert len(result.parse_errors) > 0
    assert result.log_format == "fw_log"


# ── Serialization round-trip ──────────────────────────────────────────────────
# The parser tests above stop at the ParseResult boundary. A field can still be
# dropped in _result_to_dict() — the layer the UI actually reads. These tests
# guard the full models -> parser -> _result_to_dict -> UI contract.

# Keys FwLogTab reads off r.fw_log (ui/src/App.jsx).
_FW_LOG_KEYS = {
    "origin_hash", "fw_format_version", "rf_config", "duration_ms", "buckets",
    "energy_summary", "routing", "neighbor_hashes", "rhc_poll_count",
    "battery_error_count", "error_counts", "error_messages", "warn_counts",
    "warn_messages", "parsed_lines", "skipped_debug",
}
_ROUTING_KEYS = {"transmit", "echo", "vine", "flood", "skip_rx", "skip_tx"}


def test_serialized_fw_log_has_all_ui_keys():
    from api.routes.parse import _result_to_dict
    base = _result_to_dict(parse_fw_log(FIXTURE))
    assert _FW_LOG_KEYS.issubset(base["fw_log"].keys())


def test_serialized_routing_includes_skip_tx():
    """skip_tx is parsed and rendered in FwLogTab — it must survive serialization."""
    from api.routes.parse import _result_to_dict
    base = _result_to_dict(parse_fw_log(FIXTURE))
    assert _ROUTING_KEYS.issubset(base["fw_log"]["routing"].keys())
    assert base["fw_log"]["routing"]["skip_tx"] == 1


def test_serialized_fw_log_is_json_safe():
    import json
    from api.routes.parse import _result_to_dict
    base = _result_to_dict(parse_fw_log(FIXTURE))
    json.dumps(base)  # raises if any value is not JSON-serializable
