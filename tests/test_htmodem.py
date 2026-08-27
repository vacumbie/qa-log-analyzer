"""tests/test_htmodem.py"""

from pathlib import Path

from parser.htmodem import parse_htmodem_log, is_htmodem_log
from api.routes.parse import _detect_format

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURE_DIR / "htmodem_sample.log"
EDGE_FIXTURE = FIXTURE_DIR / "htmodem_edge_cases.log"


def _content(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


# ── Real sample fixture ────────────────────────────────────────────────────────

def test_log_format():
    r = parse_htmodem_log(FIXTURE)
    assert r.log_format == "htmodem"


def test_content_detection():
    assert is_htmodem_log(_content("htmodem_sample.log")) is True


def test_detect_format_routes_to_htmodem():
    assert _detect_format("ht-modem.log", _content("htmodem_sample.log")) == "htmodem"


def test_content_detection_rejects_unrelated_content():
    assert is_htmodem_log("just some random text\nwith no ctime prefix at all\n") is False


def test_session_bounds():
    r = parse_htmodem_log(FIXTURE)
    assert r.session_start.startswith("2026-08-12 05:13:23")
    assert r.session_end.startswith("2026-08-12 05:49:44")


def test_fpga_version_ok():
    r = parse_htmodem_log(FIXTURE)
    assert r.htmodem_result.fpga_version_ok is True


def test_libiio_and_filter_bank():
    hm = parse_htmodem_log(FIXTURE).htmodem_result
    assert hm.libiio_version == "0.26"
    assert hm.filter_bank == "BFTC-415+"
    assert hm.filter_range_mhz == "330-500MHZ"


def test_found_devices_disambiguation_real_sample():
    """Both occurrences in the real sample happen to be 4, but they must be
    captured as two distinct fields, not overwritten/collapsed into one."""
    hm = parse_htmodem_log(FIXTURE).htmodem_result
    assert hm.iio_devices_found == 4
    assert hm.ad5592_devices_found == 4


def test_ad936x_cascade_collapsed_to_one_count():
    hm = parse_htmodem_log(FIXTURE).htmodem_result
    assert hm.ad936x_init_error_count == 43  # cross-validated against grep count


def test_ad936x_data_limitation_surfaced():
    r = parse_htmodem_log(FIXTURE)
    assert any(
        "AD936X" in e and "43" in e for e in r.parse_errors
    )


def test_calibration_offsets():
    hm = parse_htmodem_log(FIXTURE).htmodem_result
    assert hm.clock_cal_offset == -237
    assert hm.si4460_cal_offset == -109


def test_gpsd_error_flagged():
    r = parse_htmodem_log(FIXTURE)
    hm = r.htmodem_result
    assert hm.gpsd_connect_error is True
    assert any("gpsd" in e for e in r.parse_errors)


def test_tx_packet_counts_match_router_cross_reference():
    """59 dropped packets here should match output.modem_xmit_failed 59 seen
    in the corresponding ht-router.log capture from the same session."""
    hm = parse_htmodem_log(FIXTURE).htmodem_result
    assert len(hm.tx_packets) == 63
    assert hm.queued_count == 4
    assert hm.dropped_count == 59
    assert hm.orphaned_drop_count == 0


def test_tx_packet_fields_populated():
    hm = parse_htmodem_log(FIXTURE).htmodem_result
    p = hm.tx_packets[0]
    assert p.packet_id == 4
    assert p.data_length == 90
    assert p.symbol_count == 368
    assert p.sample_count == 736
    assert p.bch_val == "0x02eb"


def test_temp_samples_present_and_in_celsius():
    hm = parse_htmodem_log(FIXTURE).htmodem_result
    assert len(hm.temp_samples) == 218
    # raw log values are Celsius, in the high-40s range for this sample
    assert 40 < hm.temp_samples[0].lpd_c < 55


# ── Edge cases (synthetic fixture) ─────────────────────────────────────────────

def test_edge_content_detection():
    assert is_htmodem_log(_content("htmodem_edge_cases.log")) is True


def test_missing_fpga_line_surfaces_data_limitation():
    r = parse_htmodem_log(EDGE_FIXTURE)
    assert r.htmodem_result.fpga_version_ok is None
    assert any("FPGA Version is correct" in e for e in r.parse_errors)


def test_found_devices_before_ad5592_init_only():
    hm = parse_htmodem_log(EDGE_FIXTURE).htmodem_result
    assert hm.iio_devices_found == 2
    assert hm.ad5592_devices_found is None


def test_orphaned_drop_with_no_preceding_packet():
    """A CSMA-full drop line appearing before any TX packet block is counted
    separately, not fabricated into a packet record."""
    r = parse_htmodem_log(EDGE_FIXTURE)
    hm = r.htmodem_result
    assert hm.orphaned_drop_count == 1
    assert any("could not be attributed to a specific TX packet" in e for e in r.parse_errors)


def test_drop_attributed_to_most_recent_packet():
    hm = parse_htmodem_log(EDGE_FIXTURE).htmodem_result
    packets = {p.packet_id: p for p in hm.tx_packets}
    assert packets[1].queued is True
    assert packets[1].numinqueue == 1
    assert packets[2].queued is False


def test_no_ad936x_failure_when_never_mentioned():
    hm = parse_htmodem_log(EDGE_FIXTURE).htmodem_result
    assert hm.ad936x_init_error_count == 0


def test_no_temp_samples_surfaces_data_limitation():
    r = parse_htmodem_log(EDGE_FIXTURE)
    assert r.htmodem_result.temp_samples == []
    assert any("temperature" in e.lower() for e in r.parse_errors)


def test_freq_and_power_changes_captured():
    hm = parse_htmodem_log(EDGE_FIXTURE).htmodem_result
    assert len(hm.freq_changes) == 2
    directions = {f.direction for f in hm.freq_changes}
    assert directions == {"RX", "TX"}
    assert len(hm.power_changes) == 1
    assert hm.power_changes[0].xmit_level == 30.0


# ── Malformed input handling ───────────────────────────────────────────────────

def test_missing_file_returns_error(tmp_path):
    r = parse_htmodem_log(tmp_path / "nonexistent.log")
    assert len(r.parse_errors) > 0
    # Matches fw_log.py's convention: a read failure returns before the
    # format-specific result object is ever created, so it stays None.
    assert r.htmodem_result is None


def test_empty_file_returns_no_data_gracefully(tmp_path):
    empty_file = tmp_path / "empty.log"
    empty_file.write_text("")
    r = parse_htmodem_log(empty_file)
    assert r.log_format == "htmodem"
    assert r.htmodem_result.tx_packets == []
    assert r.session_start == ""


# ── RF telemetry ("Packet Transmitted") — real second sample ──────────────────

SAMPLE2 = FIXTURE_DIR / "htmodem_sample2.log"


def test_transmitted_confirmations_parsed_from_second_sample():
    hm = parse_htmodem_log(SAMPLE2).htmodem_result
    transmitted = [p for p in hm.tx_packets if p.transmitted]
    assert len(transmitted) == 2542


def test_retransmission_preserved_not_overwritten():
    """42 packets in this real capture get a second 'Packet Transmitted'
    confirmation — a genuine RF retry, not a duplicate log line. Both must
    survive, not just the latest."""
    hm = parse_htmodem_log(SAMPLE2).htmodem_result
    retransmitted = [p for p in hm.tx_packets if p.retransmit_count > 0]
    assert len(retransmitted) == 42
    p = next(p for p in hm.tx_packets if p.packet_id == 285)
    assert len(p.transmissions) == 2
    assert p.transmissions[0].rev_val == 2942
    assert p.transmissions[1].rev_val == 2935


def test_transmission_confirmation_fields():
    hm = parse_htmodem_log(SAMPLE2).htmodem_result
    p = next(p for p in hm.tx_packets if p.transmitted)
    t = p.transmissions[0]
    assert isinstance(t.rev_val, int)
    assert isinstance(t.fwd_val, int)
    assert isinstance(t.s11_db, int)
    assert isinstance(t.temp_val, int)


def test_orphaned_transmitted_line_counted_not_fabricated():
    hm = parse_htmodem_log(SAMPLE2).htmodem_result
    assert hm.orphaned_transmitted_count == 1


def test_retransmission_note_in_parse_errors():
    result = parse_htmodem_log(SAMPLE2)
    assert any("42 packet(s)" in e and "retransmission" in e for e in result.parse_errors)


def test_untransmitted_packet_has_empty_transmissions_list():
    """A packet that was queued but never got a 'Packet Transmitted' line
    (e.g. file cut off) has an empty list, not a fabricated confirmation."""
    hm = parse_htmodem_log(FIXTURE).htmodem_result  # original sample, all-dropped-or-queued
    for p in hm.tx_packets:
        if not p.transmitted:
            assert p.transmissions == []
