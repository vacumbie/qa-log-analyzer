"""tests/test_htrouter.py"""

from pathlib import Path

from parser.htrouter import parse_htrouter_log, is_htrouter_log
from api.routes.parse import _detect_format

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURE_DIR / "htrouter_sample.log"          # zero-transmit session, 447 snapshots
FIXTURE2 = FIXTURE_DIR / "htrouter_sample2.log"         # active-transmit session, 1984 snapshots
EDGE_FIXTURE = FIXTURE_DIR / "htrouter_edge_cases.log"


def _content(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


# ── Real sample fixtures ────────────────────────────────────────────────────────

def test_log_format():
    r = parse_htrouter_log(FIXTURE)
    assert r.log_format == "htrouter"


def test_content_detection():
    assert is_htrouter_log(_content("htrouter_sample.log")) is True
    assert is_htrouter_log(_content("htrouter_sample2.log")) is True


def test_detect_format_routes_to_htrouter():
    assert _detect_format("ht-router.log", _content("htrouter_sample.log")) == "htrouter"


def test_content_detection_rejects_unrelated_content():
    assert is_htrouter_log("just some random text with no stat keys\n") is False


def test_snapshot_grouping_not_flat_per_line():
    """The core requirement: ~20 lines per snapshot become ONE record, not 20."""
    r = parse_htrouter_log(FIXTURE)
    hr = r.htrouter_result
    # 447 snapshots from a file with thousands of matching lines confirms
    # grouping happened rather than one record per line.
    assert len(hr.stat_snapshots) == 447
    assert hr.stat_snapshots[0].input_subframe_count is not None
    assert hr.stat_snapshots[0].connected is not None


def test_two_real_files_have_different_snapshot_schemas():
    """Sample 1 never transmitted — these fields must be absent (None), not
    zero, distinguishing 'never happened' from 'happened zero times'."""
    hr1 = parse_htrouter_log(FIXTURE).htrouter_result
    assert all(s.output_modem_xmit_failed is None for s in hr1.stat_snapshots)
    assert all(s.output_overhead is None for s in hr1.stat_snapshots)

    hr2 = parse_htrouter_log(FIXTURE2).htrouter_result
    assert any(s.output_modem_xmit_failed is not None for s in hr2.stat_snapshots)


def test_cumulative_counter_last_value_not_sum():
    """Critical correctness case: these are cumulative session counters.
    Summing across 1984 snapshots would wildly overcount; the real answer
    (verified against raw grep of the file) is the last value: 59."""
    hr = parse_htrouter_log(FIXTURE2).htrouter_result
    assert hr.total_modem_xmit_failed == 59
    assert hr.total_timeouts == 4


def test_router_and_modem_pid_extracted():
    hr = parse_htrouter_log(FIXTURE2).htrouter_result
    assert hr.router_pid == 568
    assert hr.modem_pid == 580


def test_udp_sockets_captured():
    hr = parse_htrouter_log(FIXTURE2).htrouter_result
    assert "0.0.0.0:27348" in hr.udp_sockets
    assert len(hr.udp_sockets) == 6


def test_socket_warnings_counted():
    hr = parse_htrouter_log(FIXTURE2).htrouter_result
    assert hr.socket_warning_count == 15


def test_protocol_messages_input_and_output_both_captured():
    """udp input and udp output use different line formats — both must be
    captured, not just one."""
    hr = parse_htrouter_log(FIXTURE).htrouter_result
    by_dir = {}
    for p in hr.protocol_messages:
        by_dir[p.io_direction] = by_dir.get(p.io_direction, 0) + 1
    assert by_dir["input"] == 1858
    assert by_dir["output"] == 7432
    # input messages carry a peer, output messages don't
    input_msg = next(p for p in hr.protocol_messages if p.io_direction == "input")
    output_msg = next(p for p in hr.protocol_messages if p.io_direction == "output")
    assert input_msg.peer is not None
    assert output_msg.peer is None


def test_protocol_messages_absent_in_other_file():
    """Sample 2 genuinely has zero udp input/output lines — must be 0, not
    a parsing failure."""
    hr = parse_htrouter_log(FIXTURE2).htrouter_result
    assert len(hr.protocol_messages) == 0


def test_forward_events_captured():
    hr = parse_htrouter_log(FIXTURE).htrouter_result
    assert len(hr.forward_events) == 892
    assert hr.forward_events[0].request_type in (43, 48)


def test_transmissions_captured():
    hr = parse_htrouter_log(FIXTURE2).htrouter_result
    assert len(hr.transmissions) == 59
    assert hr.transmissions[0].transmission_id == 8
    assert hr.transmissions[0].duration_ns == 578420


def test_no_unclassified_residual_lines():
    """Every discrete event type actually observed in both real files must be
    tallied somewhere — no silent '_other' catch-all firing on real content."""
    hr1 = parse_htrouter_log(FIXTURE).htrouter_result
    hr2 = parse_htrouter_log(FIXTURE2).htrouter_result
    assert "_other" not in hr1.unparsed_event_counts
    assert "_other" not in hr2.unparsed_event_counts


def test_unparsed_events_tallied_by_type():
    hr = parse_htrouter_log(FIXTURE).htrouter_result
    assert hr.unparsed_event_counts.get("clinfo") == 3716
    assert hr.unparsed_event_counts.get("bcast_hub_forward") == 88


def test_untimestamped_startup_lines_counted():
    hr = parse_htrouter_log(FIXTURE2).htrouter_result
    assert hr.untimestamped_line_count > 0


def test_data_limitations_surfaced():
    r = parse_htrouter_log(FIXTURE2)
    assert any("us_warn" in e or "socket warning" in e for e in r.parse_errors)
    assert any("not yet structurally parsed" in e for e in r.parse_errors)


# ── Edge cases (synthetic fixture) ─────────────────────────────────────────────

def test_edge_detection():
    assert is_htrouter_log(_content("htrouter_edge_cases.log")) is True


def test_edge_pids_extracted():
    hr = parse_htrouter_log(EDGE_FIXTURE).htrouter_result
    assert hr.router_pid == 999
    assert hr.modem_pid == 111


def test_partial_snapshot_discarded_on_reopen():
    """A snapshot in progress when 'reopened log file' fires must be
    discarded entirely, not merged into the next snapshot after the reopen."""
    hr = parse_htrouter_log(EDGE_FIXTURE).htrouter_result
    # The discarded partial snapshot had subframe_count=77 — that value must
    # not appear anywhere in the final snapshot list.
    assert all(s.input_subframe_count != 77 for s in hr.stat_snapshots)


def test_rotation_marker_recorded():
    hr = parse_htrouter_log(EDGE_FIXTURE).htrouter_result
    assert len(hr.rotation_markers) == 1


def test_three_snapshots_first_second_and_trailing():
    hr = parse_htrouter_log(EDGE_FIXTURE).htrouter_result
    assert len(hr.stat_snapshots) == 3
    assert hr.stat_snapshots[0].connected is True
    assert hr.stat_snapshots[1].connected is False
    # Trailing snapshot at EOF has no closing 'connected' line
    assert hr.stat_snapshots[2].connected is None


def test_trailing_incomplete_snapshot_still_captured():
    """A file that ends mid-block is still real data — must be kept, not
    silently discarded just because it never saw a 'connected' line."""
    hr = parse_htrouter_log(EDGE_FIXTURE).htrouter_result
    trailing = hr.stat_snapshots[-1]
    assert trailing.input_subframe_count == 2
    assert trailing.output_total_bytes == 500


def test_edge_socket_warning_counted():
    hr = parse_htrouter_log(EDGE_FIXTURE).htrouter_result
    assert hr.socket_warning_count == 1


# ── Malformed input handling ───────────────────────────────────────────────────

def test_missing_file_returns_error(tmp_path):
    r = parse_htrouter_log(tmp_path / "nonexistent.log")
    assert len(r.parse_errors) > 0
    assert r.htrouter_result is None


def test_empty_file_returns_no_data_gracefully(tmp_path):
    empty_file = tmp_path / "empty.log"
    empty_file.write_text("")
    r = parse_htrouter_log(empty_file)
    assert r.log_format == "htrouter"
    assert r.htrouter_result.stat_snapshots == []
    assert r.session_start == ""


# ── Link-layer error/validity counters — real second/third samples ────────────

SAMPLE3 = FIXTURE_DIR / "htrouter_sample3.log"
SAMPLE4_ROTATED = FIXTURE_DIR / "htrouter_sample4_rotated.log"


def test_link_layer_error_fields_parsed():
    hr = parse_htrouter_log(SAMPLE3).htrouter_result
    s = hr.stat_snapshots[0]
    assert s.input_too_short_link_hdr == 152
    assert s.input_too_short_link_payload == 237
    assert s.input_too_short_link_crc == 2
    assert s.input_wrong_link_version == 579
    assert s.input_crc_present == 1831
    assert s.input_bad_crc == 112
    assert s.input_subframe_no_protocol == 3
    assert s.input_subframe_logical_recv_error == 11
    assert s.input_subframe_family_recv_error == 8


_LINK_LAYER_FIELDS = (
    "input_too_short_link_hdr",
    "input_too_short_link_payload",
    "input_too_short_link_crc",
    "input_wrong_link_version",
    "input_crc_present",
    "input_bad_crc",
    "input_subframe_no_protocol",
    "input_subframe_logical_recv_error",
    "input_subframe_family_recv_error",
)


def test_link_layer_fields_absent_stay_none_never_zero():
    """Same absence convention as output_modem_xmit_failed above: samples 1 and
    2 don't report these counters at all, and that is not the same as reporting
    zero of them. A default of 0 would render a clean green '0 bad CRC' for a
    session where bad CRCs were never measured."""
    for fixture in (FIXTURE, FIXTURE2):
        hr = parse_htrouter_log(fixture).htrouter_result
        for field in _LINK_LAYER_FIELDS:
            assert all(getattr(s, field) is None for s in hr.stat_snapshots), (
                f"{field} should be None throughout {fixture.name}"
            )


def test_link_layer_fields_present_in_the_sessions_that_report_them():
    """The negative control for the test above — if the fields were never
    populated anywhere, an all-None sweep would pass for the wrong reason."""
    for fixture in (SAMPLE3, SAMPLE4_ROTATED):
        hr = parse_htrouter_log(fixture).htrouter_result
        for field in _LINK_LAYER_FIELDS:
            assert any(getattr(s, field) is not None for s in hr.stat_snapshots), (
                f"{field} should be populated somewhere in {fixture.name}"
            )


def test_total_bad_crc_is_the_last_reported_value_not_a_sum():
    """Same cumulative-counter rule as total_modem_xmit_failed, and it lives on
    the model for the same reason: the UI must never re-derive it. Summing
    sample3's 1,077 snapshots would report tens of thousands of bad CRCs."""
    hr = parse_htrouter_log(SAMPLE3).htrouter_result
    reported = [s.input_bad_crc for s in hr.stat_snapshots if s.input_bad_crc is not None]
    assert hr.total_bad_crc == reported[-1]
    assert hr.total_bad_crc == 130
    assert hr.total_bad_crc < sum(reported)


def test_total_bad_crc_is_none_when_no_snapshot_reports_it():
    """Absent stays absent all the way up to the total — a session with no RF
    noise counters must not report 0 bad CRCs, which would read as measured."""
    for fixture in (FIXTURE, FIXTURE2):
        hr = parse_htrouter_log(fixture).htrouter_result
        assert hr.total_bad_crc is None, f"{fixture.name} should report no total"


def test_link_layer_fields_are_cumulative_like_everything_else():
    """Same discipline as output_modem_xmit_failed: verify non-decreasing
    across the session rather than assuming."""
    hr = parse_htrouter_log(SAMPLE3).htrouter_result
    values = [s.input_bad_crc for s in hr.stat_snapshots if s.input_bad_crc is not None]
    assert values == sorted(values)


def test_rotated_log_file_content_detected_and_parsed():
    """A rotated log is the same format as the live one — the content check and
    the parser must both handle it with no special casing."""
    content = SAMPLE4_ROTATED.read_text()
    assert is_htrouter_log(content) is True
    result = parse_htrouter_log(SAMPLE4_ROTATED)
    assert result.log_format == "htrouter"
    assert len(result.htrouter_result.stat_snapshots) > 0


def test_rotation_style_filename_still_detects_as_htrouter():
    """The extension claim, actually exercised: logrotate produces
    'ht-router_log.1', which has no .log suffix at all. _detect_format() is the
    function that reads filenames, so it is the one that has to be asked —
    is_htrouter_log() never sees the name and cannot fail this way."""
    content = SAMPLE4_ROTATED.read_text()
    assert _detect_format("ht-router_log.1", content) == "htrouter"
    assert _detect_format("ht-router.log.1", content) == "htrouter"


def test_rotated_log_and_current_log_are_contiguous_sessions():
    """ht-router_log.1 ends right where ht-router.log begins — documenting
    this relationship, not enforcing any cross-file merge (each file is
    still parsed as its own independent session)."""
    rotated = parse_htrouter_log(SAMPLE4_ROTATED)
    current = parse_htrouter_log(SAMPLE3)
    assert rotated.session_end <= current.session_start
