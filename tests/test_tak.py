"""tests/test_tak.py"""

from pathlib import Path

from parser.tak import parse_tak_log, is_tak_log

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURE_DIR / "tak_stream_sample.json"
EDGE_FIXTURE = FIXTURE_DIR / "tak_stream_edge_cases.json"


# ── Real sample fixture (91 records) ───────────────────────────────────────────

def test_log_format():
    result = parse_tak_log(FIXTURE)
    assert result.log_format == "tak"


def test_all_records_parsed():
    result = parse_tak_log(FIXTURE)
    assert len(result.tak_events) == 91


def test_category_breakdown():
    result = parse_tak_log(FIXTURE)
    counts = {}
    for e in result.tak_events:
        counts[e.category] = counts.get(e.category, 0) + 1
    assert counts == {"PLI": 71, "Marker": 16, "Chat": 3, "Other": 1}


def test_session_timestamps_set():
    result = parse_tak_log(FIXTURE)
    assert result.session_start != ""
    assert result.session_end != ""
    assert result.session_start <= result.session_end


def test_server_info_extracted():
    result = parse_tak_log(FIXTURE)
    assert result.tak_server_info is not None
    assert result.tak_server_info.server_version == "5.6-RELEASE-57-HEAD"
    assert result.tak_server_info.api_version == "3"


def test_content_detection():
    text = FIXTURE.read_text()
    assert is_tak_log(text) is True


def test_content_detection_rejects_non_tak_json():
    assert is_tak_log('[{"logId": 1, "connectionState": "connected"}]') is False


# ── Edge cases (synthetic fixture) ─────────────────────────────────────────────

def test_no_gps_fix_flagged():
    """lat=0/lon=0 is the CoT 'no fix' sentinel, not a real position at (0,0)."""
    result = parse_tak_log(EDGE_FIXTURE)
    no_fix = [e for e in result.tak_events if not e.has_gps_fix]
    # LEON (PLI), ANGOL (Chat), and the Other control record all report 0/0
    assert len(no_fix) == 3
    assert all(e.lat == 0.0 and e.lon == 0.0 for e in no_fix)


def test_no_fix_events_property_excludes_chat_and_other():
    """tak_no_fix_events is scoped to PLI/Marker — a no-fix Chat or control
    record isn't a 'missing position' in the same sense as a device report."""
    result = parse_tak_log(EDGE_FIXTURE)
    no_fix_categories = {e.category for e in result.tak_no_fix_events}
    assert no_fix_categories == {"PLI"}


def test_negative_latency_preserved_not_clamped():
    """A device clock running fast relative to the TAK server produces a
    negative latency — this is the signal of interest, not an error to hide."""
    result = parse_tak_log(EDGE_FIXTURE)
    skew_event = next(e for e in result.tak_events if e.callsign == "CLOCKSKEW")
    assert skew_event.latency_ms is not None
    assert skew_event.latency_ms < 0


def test_record_missing_time_is_skipped_not_crashed():
    result = parse_tak_log(EDGE_FIXTURE)
    uids = {e.uid for e in result.tak_events}
    assert "ANDROID-notime" not in uids
    assert any("skipped" in e for e in result.parse_errors)


def test_null_callsign_and_platform_handled():
    result = parse_tak_log(EDGE_FIXTURE)
    control = next(e for e in result.tak_events if e.category == "Other")
    assert control.callsign is None
    assert control.platform is None


def test_chat_data_limitation_surfaced():
    result = parse_tak_log(EDGE_FIXTURE)
    limits = [e for e in result.parse_errors if e.startswith("DATA LIMITATION —")]
    assert any("Chat message bodies not extracted" in e for e in limits)


def test_no_fix_and_negative_latency_counts_surfaced():
    result = parse_tak_log(EDGE_FIXTURE)
    assert any("no GPS fix" in e for e in result.parse_errors)
    assert any("negative server latency" in e for e in result.parse_errors)


# ── Malformed input handling ───────────────────────────────────────────────────

def test_missing_file_returns_error(tmp_path):
    result = parse_tak_log(tmp_path / "nonexistent.json")
    assert len(result.parse_errors) > 0
    assert result.tak_events == []


def test_non_json_content_returns_error(tmp_path):
    bad_file = tmp_path / "not_json.json"
    bad_file.write_text("this is not json at all {{{")
    result = parse_tak_log(bad_file)
    assert len(result.parse_errors) > 0
    assert result.tak_events == []


def test_json_object_instead_of_array_returns_error(tmp_path):
    bad_file = tmp_path / "wrong_shape.json"
    bad_file.write_text('{"not": "an array"}')
    result = parse_tak_log(bad_file)
    assert len(result.parse_errors) > 0
    assert result.tak_events == []
