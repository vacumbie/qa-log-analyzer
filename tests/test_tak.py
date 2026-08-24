"""tests/test_tak.py"""

import json
from pathlib import Path

from parser.tak import parse_tak_log, is_tak_log

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURE_DIR / "tak_stream_sample.json"
EDGE_FIXTURE = FIXTURE_DIR / "tak_stream_edge_cases.json"
CLEAN_FIXTURE = FIXTURE_DIR / "tak_stream_clean_pli_only.json"
ZERO_COORD_FIXTURE = FIXTURE_DIR / "tak_stream_zero_coordinate_positions.json"
PARTIAL_COORD_FIXTURE = FIXTURE_DIR / "tak_stream_partial_coordinates.json"
UNKNOWN_CAT_FIXTURE = FIXTURE_DIR / "tak_stream_unknown_categories.json"
ATAK_FIXTURE = FIXTURE_DIR / "atak_sample.json"


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


def test_content_detection_rejects_real_atak_log():
    """ATAK plugin logs are also JSON arrays, so the signature keys are the only
    thing keeping them out of the TAK parser. Guards against widening them."""
    assert is_tak_log(ATAK_FIXTURE.read_text(encoding="utf-8")) is False


# ── Edge cases (synthetic fixture) ─────────────────────────────────────────────

def test_no_gps_fix_flagged():
    """lat=0/lon=0 is the CoT 'no fix' sentinel, not a real position at (0,0)."""
    result = parse_tak_log(EDGE_FIXTURE)
    no_fix = [e for e in result.tak_events if not e.has_gps_fix]
    # LEON (PLI), the WebTAK Marker, ANGOL (Chat), and the Other control record
    # all report 0/0
    assert len(no_fix) == 4
    assert all(e.lat == 0.0 and e.lon == 0.0 for e in no_fix)


def test_no_fix_events_property_covers_pli_and_marker():
    """tak_no_fix_events is scoped to PLI/Marker — a no-fix Chat or control
    record isn't a 'missing position' in the same sense as a device report,
    but a WebTAK Marker with no fix is."""
    result = parse_tak_log(EDGE_FIXTURE)
    no_fix_categories = {e.category for e in result.tak_no_fix_events}
    assert no_fix_categories == {"PLI", "Marker"}


def test_no_fix_events_property_excludes_chat_and_other():
    """A Chat body and the t-x-takp-v control record both carry 0/0 but neither
    is a device position report, so neither belongs in tak_no_fix_events."""
    result = parse_tak_log(EDGE_FIXTURE)
    no_fix_uids = {e.uid for e in result.tak_no_fix_events}
    assert not any("GeoChat" in uid for uid in no_fix_uids)
    assert len(result.tak_no_fix_events) == 2


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
    assert any("no usable position" in e for e in result.parse_errors)
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


def test_json_object_root_error_names_the_shape_problem(tmp_path):
    """The hard-stop message has to say what was wrong — there is no partial
    recovery path here, so this string is all the QA engineer gets."""
    bad_file = tmp_path / "wrong_shape.json"
    bad_file.write_text('{"not": "an array"}')
    result = parse_tak_log(bad_file)
    assert "root is not an array" in result.parse_errors[0]


def test_empty_array_reports_no_events_found(tmp_path):
    """A valid-but-empty stream is not an error condition to swallow silently."""
    empty = tmp_path / "tak-stream-empty.json"
    empty.write_text("[]")
    result = parse_tak_log(empty)
    assert any("No valid CoT event records" in e for e in result.parse_errors)


def test_empty_array_leaves_session_bounds_unset(tmp_path):
    empty = tmp_path / "tak-stream-empty.json"
    empty.write_text("[]")
    result = parse_tak_log(empty)
    assert result.session_start == "" and result.session_end == ""


# ── Coordinate-zero sentinel discrimination ───────────────────────────────────
# The (0,0) pair is the sentinel — a single zero coordinate is a real position.
# has_gps_fix is defined once in the parser and consumed as-is by the UI, so
# these tests are the only thing standing between a device on the equator or the
# prime meridian and being dropped off the map.

def test_zero_longitude_is_a_real_position_on_the_prime_meridian():
    result = parse_tak_log(ZERO_COORD_FIXTURE)
    tema = next(e for e in result.tak_events if e.callsign == "TEMA")
    assert tema.has_gps_fix is True


def test_zero_longitude_position_is_preserved_not_blanked():
    result = parse_tak_log(ZERO_COORD_FIXTURE)
    tema = next(e for e in result.tak_events if e.callsign == "TEMA")
    assert (tema.lat, tema.lon) == (5.626081, 0.0)


def test_zero_latitude_is_a_real_position_on_the_equator():
    result = parse_tak_log(ZERO_COORD_FIXTURE)
    sao_tome = next(e for e in result.tak_events if e.callsign == "SAO TOME")
    assert sao_tome.has_gps_fix is True


def test_zero_latitude_position_is_preserved_not_blanked():
    result = parse_tak_log(ZERO_COORD_FIXTURE)
    sao_tome = next(e for e in result.tak_events if e.callsign == "SAO TOME")
    assert (sao_tome.lat, sao_tome.lon) == (0.0, 6.545217)


def test_both_coordinates_zero_is_the_no_fix_sentinel():
    result = parse_tak_log(ZERO_COORD_FIXTURE)
    osu = next(e for e in result.tak_events if e.callsign == "OSU")
    assert osu.has_gps_fix is False


def test_single_zero_coordinates_are_not_counted_as_no_fix():
    """Only the (0,0) record is a no-fix — the equator and prime-meridian
    devices must not inflate the count the UI and parse_errors report."""
    result = parse_tak_log(ZERO_COORD_FIXTURE)
    assert len(result.tak_no_fix_events) == 1


def test_single_zero_coordinates_do_not_inflate_no_fix_parse_error():
    result = parse_tak_log(ZERO_COORD_FIXTURE)
    entry = next(e for e in result.parse_errors if "no usable position" in e)
    assert entry.startswith("1 PLI/Marker event(s)")


# ── The no-fix sentence is scoped, and scoped the same way as the KPI ──────────
# It used to count every category ("5 event(s) reported no GPS fix") while
# summary.no_fix_count counted only PLI/Marker (1). Both numbers were right for
# what they measured, but the sentence read as five devices losing GPS when one
# did. The UI fixed its half first; these pin the parser's.

def test_no_fix_sentence_count_matches_the_summary_scope():
    """The regression guard that matters: the sentence's leading number and
    len(tak_no_fix_events) — which is what summary.no_fix_count serializes —
    must be the same number, whatever the fixture."""
    result = parse_tak_log(FIXTURE)
    entry = next(e for e in result.parse_errors if "no usable position" in e)
    assert entry.startswith(f"{len(result.tak_no_fix_events)} PLI/Marker event(s)")


def test_no_fix_sentence_names_the_other_categories_separately():
    """The 4 Chat/server-control events are still reported — dropping them would
    trade one misleading number for a missing one — but named as a category that
    never carries a position, not as lost fixes."""
    result = parse_tak_log(FIXTURE)
    entry = next(e for e in result.parse_errors if "no usable position" in e)
    assert "1 PLI/Marker event(s)" in entry
    assert "A further 4 Chat/server-control event(s)" in entry
    assert "not a lost GPS fix" in entry


def test_no_fix_sentence_omits_the_other_clause_when_there_are_none():
    """The zero-coordinate fixture is PLI-only, so the trailing clause must not
    appear at all rather than reading 'A further 0'."""
    result = parse_tak_log(ZERO_COORD_FIXTURE)
    entry = next(e for e in result.parse_errors if "no usable position" in e)
    assert "A further" not in entry


def test_chat_only_no_position_reports_nothing():
    """Every Chat record lacks a position; an entry firing on that alone would
    appear in every log with chat in it and stop meaning anything."""
    result = parse_tak_log(FIXTURE)
    chat_no_fix = [e for e in result.tak_events
                   if not e.has_gps_fix and e.category == "Chat"]
    assert chat_no_fix, "fixture must contain no-position Chat records"
    assert not any(e.startswith(f"{len(chat_no_fix)} Chat") for e in result.parse_errors)


# ── Unrecognised categories ───────────────────────────────────────────────────
# The category set is computed server-side and can grow. An unrecognised value
# used to count in none of the four buckets, so they silently stopped summing to
# total_events — the KPI row showed 4 category cards that no longer added up.

def test_unrecognized_category_is_stored_verbatim():
    """Never mapped through an allow-list — the value is the useful part."""
    result = parse_tak_log(UNKNOWN_CAT_FIXTURE)
    categories = {e.category for e in result.tak_events}
    assert "Alert" in categories and "Route" in categories


def test_unrecognized_category_gets_its_own_bucket():
    result = parse_tak_log(UNKNOWN_CAT_FIXTURE)
    unrecognized = [e for e in result.tak_events if e.is_unrecognized_category]
    assert {e.callsign for e in unrecognized} == {"ALERTER", "ROUTEMAKER"}


def test_unrecognized_category_is_not_folded_into_server_control():
    """Folding would hide a new category behind a label reading 'server
    control' — the same call already made for ATAK's unparsed action values."""
    result = parse_tak_log(UNKNOWN_CAT_FIXTURE)
    assert not any(e.is_server_control for e in result.tak_events
                   if e.callsign in ("ALERTER", "ROUTEMAKER"))


def test_null_category_falls_back_to_other_not_none():
    """An explicit null would otherwise put None in a field annotated str and
    count in no bucket at all."""
    result = parse_tak_log(UNKNOWN_CAT_FIXTURE)
    event = next(e for e in result.tak_events if e.callsign == "NULLCAT")
    assert event.category == "Other"
    assert event.is_unrecognized_category is False


def test_unrecognized_category_error_names_the_values():
    result = parse_tak_log(UNKNOWN_CAT_FIXTURE)
    entry = next(e for e in result.parse_errors if "unrecognised event category" in e)
    assert "'Alert'" in entry and "'Route'" in entry


def test_unrecognized_category_error_silent_on_a_known_only_stream():
    result = parse_tak_log(CLEAN_FIXTURE)
    assert not any("unrecognised event category" in e for e in result.parse_errors)


# ── Partial coordinate pairs ──────────────────────────────────────────────────
# A CoT <point> carries lat and lon together. One without the other used to be
# coerced to 0.0, which produced a position in the Gulf of Guinea that passed
# the (0,0)-pair sentinel test and was plotted as a real fix — the exact bug the
# zero-coordinate rule above makes invisible, since lat == 0 is now legitimate.

def test_null_latitude_with_real_longitude_is_not_a_fix():
    result = parse_tak_log(PARTIAL_COORD_FIXTURE)
    event = next(e for e in result.tak_events if e.callsign == "HALFLAT")
    assert event.has_gps_fix is False


def test_null_latitude_is_not_defaulted_to_zero():
    """The whole point: 0.0 here would be a fabricated position on the equator,
    indistinguishable from the genuine equator positions the parser must keep."""
    result = parse_tak_log(PARTIAL_COORD_FIXTURE)
    event = next(e for e in result.tak_events if e.callsign == "HALFLAT")
    assert event.lat is None


def test_absent_longitude_key_is_not_a_fix():
    result = parse_tak_log(PARTIAL_COORD_FIXTURE)
    event = next(e for e in result.tak_events if e.callsign == "NOLON")
    assert event.has_gps_fix is False and event.lon is None


def test_present_coordinate_is_discarded_with_its_missing_partner():
    """Keeping the half that arrived would imply a position the record doesn't
    describe — a longitude line, not a point."""
    result = parse_tak_log(PARTIAL_COORD_FIXTURE)
    event = next(e for e in result.tak_events if e.callsign == "NOLON")
    assert event.lat is None


def test_non_numeric_coordinate_is_treated_as_missing():
    result = parse_tak_log(PARTIAL_COORD_FIXTURE)
    event = next(e for e in result.tak_events if e.callsign == "BADCOORD")
    assert event.has_gps_fix is False and event.lat is None


def test_partial_coordinate_records_are_still_parsed():
    """The position is unusable; the event itself — callsign, category, timing —
    is not, and dropping the record would lose real observations."""
    result = parse_tak_log(PARTIAL_COORD_FIXTURE)
    assert len(result.tak_events) == 4


def test_real_fix_alongside_partial_records_keeps_its_position():
    result = parse_tak_log(PARTIAL_COORD_FIXTURE)
    event = next(e for e in result.tak_events if e.callsign == "GOODFIX")
    assert event.has_gps_fix is True
    assert (event.lat, event.lon) == (30.153401, -85.664712)


def test_missing_coordinates_reported_separately_from_the_no_fix_sentinel():
    """A (0,0) sentinel means the device had no fix; a missing coordinate means
    the record was incomplete. Two distinct entries, so a malformed export is
    never misattributed to GPS trouble in the field — even though both make
    has_gps_fix False and both are excluded from the map."""
    result = parse_tak_log(PARTIAL_COORD_FIXTURE)
    assert any("carry only one of lat/lon" in e for e in result.parse_errors)
    assert any("no usable position" in e for e in result.parse_errors)


def test_incomplete_pairs_count_toward_the_positional_no_fix_total():
    """All three partial records are PLI/Marker, so they belong in the same
    PLI/Marker-scoped total the KPI shows — the sentence names both causes
    rather than claiming they were all sentinels."""
    result = parse_tak_log(PARTIAL_COORD_FIXTURE)
    entry = next(e for e in result.parse_errors if "no usable position" in e)
    assert entry.startswith("3 PLI/Marker event(s)")
    assert "incomplete lat/lon pair" in entry


def test_missing_coordinate_error_counts_every_affected_record():
    result = parse_tak_log(PARTIAL_COORD_FIXTURE)
    entry = next(e for e in result.parse_errors if "carry only one of lat/lon" in e)
    assert entry.startswith("3 event(s)")


def test_missing_coordinate_error_silent_when_every_pair_is_complete():
    result = parse_tak_log(CLEAN_FIXTURE)
    assert not any("carry only one of lat/lon" in e for e in result.parse_errors)


# ── Missing server receipt time ───────────────────────────────────────────────

def test_missing_received_at_yields_null_latency_not_zero():
    """No receivedAt means server latency is unknown, not instant."""
    result = parse_tak_log(EDGE_FIXTURE)
    event = next(e for e in result.tak_events if e.callsign == "NORECEIPT")
    assert event.latency_ms is None


def test_missing_received_at_leaves_received_at_empty():
    result = parse_tak_log(EDGE_FIXTURE)
    event = next(e for e in result.tak_events if e.callsign == "NORECEIPT")
    assert event.received_at == ""


def test_missing_received_at_event_is_still_parsed():
    """An unknown latency must not cost the event its position or identity."""
    result = parse_tak_log(EDGE_FIXTURE)
    event = next(e for e in result.tak_events if e.callsign == "NORECEIPT")
    assert event.has_gps_fix is True and event.lat == 30.153401


def test_null_latency_excluded_from_latency_values():
    """tak_latency_ms_values feeds avg/min/max — a None must drop out entirely
    rather than being averaged in as a zero."""
    result = parse_tak_log(EDGE_FIXTURE)
    assert len(result.tak_latency_ms_values) == len(result.tak_events) - 1


# ── Skipped-record accounting ─────────────────────────────────────────────────

def test_unparseable_time_record_is_skipped():
    """A non-ISO 'time' (dd/mm/yyyy) can't be ordered against receivedAt, so the
    record is dropped rather than guessed at."""
    result = parse_tak_log(EDGE_FIXTURE)
    assert "ANDROID-badclock" not in {e.uid for e in result.tak_events}


def test_non_dict_record_is_skipped():
    """A null element in the array must not crash the loop or become an event."""
    result = parse_tak_log(EDGE_FIXTURE)
    assert len(result.tak_events) == 8


def test_non_dict_record_gets_no_per_record_parse_error():
    """Only the two time-field failures name a record index; the malformed null
    is reported through the aggregate count alone."""
    result = parse_tak_log(EDGE_FIXTURE)
    per_record = [e for e in result.parse_errors if e.startswith("Record ")]
    assert len(per_record) == 2


def test_skipped_total_counts_malformed_and_missing_time_together():
    result = parse_tak_log(EDGE_FIXTURE)
    assert any("3 of 11 record(s)" in e for e in result.parse_errors)


# ── Emissions are data-driven: silent when the condition is absent ─────────────
# Each parse_errors entry in parse_tak_log is conditional. A clean PLI-only
# stream is the negative control — if any of them fire here, they would fire on
# every log and stop meaning anything.

def test_clean_stream_reports_no_operational_parse_errors():
    """Scoped to the operational entries — the ones that mean something went
    wrong with this file. The unextracted-XML limitation is deliberately not in
    that set: it fires on any stream whose records carry <status>/<takv>/<track>,
    which a clean stream does. Asserting `parse_errors == []` here would instead
    certify that a real, documented gap goes unreported."""
    operational = [e for e in parse_tak_log(CLEAN_FIXTURE).parse_errors
                   if not e.startswith("DATA LIMITATION —")]
    assert operational == []


def test_chat_data_limitation_silent_when_no_chat_records():
    result = parse_tak_log(CLEAN_FIXTURE)
    assert not any("Chat message bodies" in e for e in result.parse_errors)


# ── Unextracted raw-XML telemetry ─────────────────────────────────────────────
# <status battery>, <takv> and <track> are parsed by nobody and live only in
# raw_cot, which the API doesn't serialize. CLAUDE.md documented them as
# surfaced via a DATA LIMITATION entry before one existed; these pin that it
# does, and that it names only what a given stream actually carries.

def test_unextracted_xml_limitation_fires_when_telemetry_is_present():
    result = parse_tak_log(CLEAN_FIXTURE)
    assert any("Telemetry present in the raw CoT XML" in e for e in result.parse_errors)


def test_unextracted_xml_limitation_counts_each_element():
    result = parse_tak_log(CLEAN_FIXTURE)
    entry = next(e for e in result.parse_errors if "Telemetry present" in e)
    assert "battery percentage (6 event(s))" in entry
    assert "device model / OS / TAK version (6 event(s))" in entry
    assert "speed and course (6 event(s))" in entry


def test_unextracted_xml_limitation_names_only_what_is_present():
    """The edge-case fixture carries one <status battery> and no <takv>/<track>,
    so a stream must not be told telemetry was dropped that it never had."""
    result = parse_tak_log(EDGE_FIXTURE)
    entry = next(e for e in result.parse_errors if "Telemetry present" in e)
    assert "battery percentage (1 event(s))" in entry
    assert "device model" not in entry
    assert "speed and course" not in entry


def test_unextracted_xml_limitation_silent_when_no_telemetry(tmp_path):
    """Envelope-only records — a bare <event><point/></event> with no <detail>
    child — must produce no entry at all, or it would fire on every log."""
    bare = tmp_path / "tak-stream-bare.json"
    bare.write_text(json.dumps([{
        "callsign": "BARE", "category": "PLI", "lat": 30.1, "lon": -85.6,
        "nodeType": "Android", "time": "2026-07-30T19:24:54Z",
        "receivedAt": "2026-07-30T19:24:55Z", "type": "a-f-G-U-C",
        "uid": "ANDROID-bare",
        "raw": '<event uid="ANDROID-bare"><point lat="30.1" lon="-85.6"/></event>',
    }]))
    result = parse_tak_log(bare)
    assert not any("Telemetry present" in e for e in result.parse_errors)


def test_no_fix_error_silent_when_every_event_has_a_fix():
    result = parse_tak_log(CLEAN_FIXTURE)
    assert not any("no GPS fix" in e for e in result.parse_errors)


def test_negative_latency_error_silent_when_no_clock_skew():
    result = parse_tak_log(CLEAN_FIXTURE)
    assert not any("negative server latency" in e for e in result.parse_errors)


def test_skipped_record_error_silent_when_all_records_are_valid():
    result = parse_tak_log(CLEAN_FIXTURE)
    assert not any("skipped" in e for e in result.parse_errors)


def test_server_info_is_none_without_a_handshake_record():
    """tak_server_info comes only from a t-x-takp-v control record. A stream
    captured after the handshake has none — that must stay None, not an empty
    TakServerInfo the UI would render as a blank version."""
    result = parse_tak_log(CLEAN_FIXTURE)
    assert result.tak_server_info is None


def test_clean_stream_still_parses_every_event():
    result = parse_tak_log(CLEAN_FIXTURE)
    assert len(result.tak_events) == 6
