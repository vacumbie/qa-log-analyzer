"""tests/test_parse_route.py

Exercises the POST /parse route handler (api/routes/parse.py:parse_logs) the way
a real upload hits it — detection, the temp-file write, parser dispatch, and
serialization — by calling the endpoint coroutine directly with constructed
UploadFile objects. The per-parser unit tests call parse_*_log(path) directly and
so bypass this path; this file covers the gap.

Regression guard for the CRLF temp-file bug: the route wrote the decoded upload
text in text mode, which on Windows double-translated CRLF ("\r\n" -> "\r\r\n").
Path.read_text()'s universal-newline decode then read that back as "\n\n", which
prematurely split the blank-line-delimited diagnostic format so every Received
Message block was dropped (0 parsed) for any CRLF upload. The fix writes the temp
file with newline="" so the upload bytes survive verbatim.
"""

import asyncio
import io
from pathlib import Path

import pytest

from fastapi import UploadFile

from api.routes.parse import parse_logs

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _post(filename: str, content: bytes) -> dict:
    """Call the real /parse handler with a single in-memory upload."""
    upload = UploadFile(filename=filename, file=io.BytesIO(content))
    return asyncio.run(parse_logs(files=[upload]))


def _export_client():
    """A TestClient over the export router.

    Mounts the router rather than importing `api.main`, whose flat
    `from routes.export import ...` only resolves with `api/` on sys.path (how
    uvicorn runs it). Importing it here would mean a sys.path hack in tests/,
    which this suite deliberately has none of. `main.py` mounts this same
    router, so the routes under test are the ones that ship.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.routes.export import router as export_router

    app = FastAPI()
    app.include_router(export_router)
    return TestClient(app)


def _diagnostic_bytes(line_ending: str) -> bytes:
    # read_text() normalizes to "\n" regardless of how git checked the fixture
    # out (autocrlf), so re-encoding lets the test control the line ending it
    # uploads rather than depending on the working-tree state.
    text = (FIXTURE_DIR / "diagnostic_sample.txt").read_text(encoding="utf-8")
    return text.replace("\n", line_ending).encode("utf-8")


def test_crlf_diagnostic_upload_parses_blocks():
    """A CRLF-uploaded diagnostic log must parse its Received Message blocks
    through the route — the temp-file write must not corrupt line endings."""
    result = _post("diagnostic_sample.txt", _diagnostic_bytes("\r\n"))["results"][0]
    assert result["log_format"] == "diagnostic"
    assert len(result["received_messages"]) == 2


def test_crlf_and_lf_uploads_agree():
    """Line endings must not change the parse result through the route."""
    crlf = _post("diagnostic_sample.txt", _diagnostic_bytes("\r\n"))["results"][0]
    lf = _post("diagnostic_sample.txt", _diagnostic_bytes("\n"))["results"][0]
    assert len(crlf["received_messages"]) == len(lf["received_messages"]) == 2


# ── TAK server stream ─────────────────────────────────────────────────────────
# The TAK parser tests call parse_tak_log(path) directly, which never touches
# _result_to_dict(). Everything the TAK tab reads is produced there, so a field
# dropped from the serializer would pass the parser suite and break the UI.

def _tak_upload(fixture_name: str) -> dict:
    return _post(fixture_name, (FIXTURE_DIR / fixture_name).read_bytes())["results"][0]


def test_tak_stream_upload_routes_to_the_tak_parser():
    result = _tak_upload("tak_stream_sample.json")
    assert result["log_format"] == "tak"


def test_tak_stream_upload_serializes_every_event():
    result = _tak_upload("tak_stream_sample.json")
    assert len(result["tak_events"]) == 91


def test_tak_event_serialization_exposes_the_expected_field_set():
    """raw_cot is deliberately not serialized — the CoT XML is large and nothing
    in the UI reads it. Pinning the exact key set catches both a dropped field
    and an accidental payload bloat."""
    result = _tak_upload("tak_stream_sample.json")
    assert set(result["tak_events"][0]) == {
        "timestamp", "category", "cot_type", "uid", "callsign", "node_type",
        "platform", "parent_callsign", "lat", "lon", "has_gps_fix",
        "is_unrecognized_category", "received_at", "latency_ms",
    }


def test_tak_unrecognized_flag_serialized_per_event():
    """The UI's time-window recompute re-buckets categories, and must filter on
    this flag rather than repeating the parser's category list — the same reason
    has_gps_fix is serialized per event instead of being re-derived from lat/lon."""
    result = _tak_upload("tak_stream_unknown_categories.json")
    flagged = {e["callsign"] for e in result["tak_events"] if e["is_unrecognized_category"]}
    assert flagged == {"ALERTER", "ROUTEMAKER"}


def test_tak_summary_counts_match_the_capture():
    result = _tak_upload("tak_stream_sample.json")
    summary = result["summary"]
    assert (
        summary["total_events"], summary["pli_count"], summary["marker_count"],
        summary["chat_count"], summary["other_count"],
    ) == (91, 71, 16, 3, 1)


def test_tak_summary_reports_unique_callsigns():
    result = _tak_upload("tak_stream_sample.json")
    assert result["summary"]["unique_callsigns"] == 10


def test_tak_summary_no_fix_count_is_position_scoped():
    """summary.no_fix_count counts PLI/Marker only — the Chat and control
    records that also carry 0/0 are not missing positions."""
    result = _tak_upload("tak_stream_sample.json")
    assert result["summary"]["no_fix_count"] == 1


def test_tak_summary_latency_stats_keep_the_negative_minimum():
    """Clock skew shows up as a negative min latency; clamping it to 0 would
    hide the exact signal this format was added to surface."""
    summary = _tak_upload("tak_stream_sample.json")["summary"]
    assert summary["min_latency_ms"] == -93
    assert summary["max_latency_ms"] == 166909


def test_tak_summary_negative_latency_count_serialized():
    result = _tak_upload("tak_stream_sample.json")
    assert result["summary"]["negative_latency_count"] == 10


def test_tak_server_info_serialized_from_the_handshake_record():
    result = _tak_upload("tak_stream_sample.json")
    assert result["tak_server_info"] == {
        "server_version": "5.6-RELEASE-57-HEAD",
        "api_version": "3",
    }


def test_tak_server_info_is_null_without_a_handshake_record():
    result = _tak_upload("tak_stream_clean_pli_only.json")
    assert result["tak_server_info"] is None


def test_tak_data_limitation_reaches_the_api_response():
    result = _tak_upload("tak_stream_sample.json")
    assert any(e.startswith("DATA LIMITATION —") for e in result["parse_errors"])


def test_tak_clean_stream_reports_no_operational_parse_errors_through_the_route():
    """Operational entries only — the unextracted-XML DATA LIMITATION fires for
    any stream carrying <status>/<takv>/<track>, which a clean one does."""
    result = _tak_upload("tak_stream_clean_pli_only.json")
    operational = [e for e in result["parse_errors"]
                   if not e.startswith("DATA LIMITATION —")]
    assert operational == []


TAK_FIXTURES = sorted(
    f.name for f in (Path(__file__).parent / "fixtures").glob("tak_*") if f.is_file()
)


def test_tak_fixture_discovery_covers_both_shapes():
    """The glob below deliberately matches tak_* rather than tak_stream_*.json:
    the NDJSON captures are named tak_ndjson_*.log, so the narrower pattern
    excluded them and the invariant CLAUDE.md describes as holding 'across every
    fixture' quietly stopped covering the newest shape. An empty or
    array-shape-only match here would collect a hollow guard."""
    assert any(name.startswith("tak_ndjson_") for name in TAK_FIXTURES)
    assert any(name.startswith("tak_stream_") for name in TAK_FIXTURES)


@pytest.mark.parametrize("fixture_name", TAK_FIXTURES)
def test_tak_category_counts_reconcile_against_total_events(fixture_name):
    """The five category counts must sum to total_events for every fixture. This
    is the guard the unrecognized bucket exists for — without it an unknown
    category counted in none of them and the KPI row silently stopped adding
    up, with no error anywhere to say so."""
    s = _tak_upload(fixture_name)["summary"]
    assert (s["pli_count"] + s["marker_count"] + s["chat_count"]
            + s["other_count"] + s["unrecognized_count"]) == s["total_events"]


def test_tak_unrecognized_count_serialized():
    s = _tak_upload("tak_stream_unknown_categories.json")["summary"]
    assert s["unrecognized_count"] == 2


def test_tak_missing_coordinate_serializes_as_null_not_zero():
    """A fabricated 0.0 would reach the map as a plottable equator position; the
    UI filters on has_gps_fix, but the exported CSV/JSON has no such guard."""
    result = _tak_upload("tak_stream_partial_coordinates.json")
    event = next(e for e in result["tak_events"] if e["callsign"] == "HALFLAT")
    assert event["lat"] is None and event["has_gps_fix"] is False


def test_tak_unextracted_xml_limitation_reaches_the_api_response():
    result = _tak_upload("tak_stream_clean_pli_only.json")
    assert any("Telemetry present in the raw CoT XML" in e
               for e in result["parse_errors"])


def test_tak_null_latency_survives_serialization_as_none():
    """A missing receivedAt must serialize to null, not 0 — a 0 would land in
    the latency chart as a perfect-delivery data point."""
    result = _tak_upload("tak_stream_edge_cases.json")
    event = next(e for e in result["tak_events"] if e["callsign"] == "NORECEIPT")
    assert event["latency_ms"] is None


def test_tak_no_fix_flag_survives_serialization():
    """TakTab.jsx plots on has_gps_fix alone; if the serializer dropped it the
    sentinel positions would be plotted at (0,0) off the coast of Africa."""
    result = _tak_upload("tak_stream_edge_cases.json")
    leon = next(e for e in result["tak_events"] if e["callsign"] == "LEON")
    assert leon["has_gps_fix"] is False


def test_tak_single_zero_coordinate_serializes_as_a_real_fix():
    result = _tak_upload("tak_stream_zero_coordinate_positions.json")
    tema = next(e for e in result["tak_events"] if e["callsign"] == "TEMA")
    assert (tema["has_gps_fix"], tema["lat"], tema["lon"]) == (True, 5.626081, 0.0)


# ── TAK NDJSON through the route ──────────────────────────────────────────────

def test_ndjson_capture_routes_to_the_tak_parser_by_content():
    """tak_ndjson_real_sample.log matches neither TAK filename hint, so this is
    the content path carrying an 804-event capture on its own."""
    result = _tak_upload("tak_ndjson_real_sample.log")
    assert result["log_format"] == "tak"
    assert len(result["tak_events"]) == 804


def test_ndjson_summary_stats_serialized():
    summary = _tak_upload("tak_ndjson_real_sample.log")["summary"]
    assert summary["unique_callsigns"] == 23
    assert summary["no_fix_count"] == 30
    assert summary["min_latency_ms"] == -2097
    assert summary["negative_latency_count"] == 793


def test_ndjson_partial_coordinates_serialize_as_null_not_zero():
    """Same guard as the array shape: the export has no has_gps_fix filter, so a
    fabricated 0.0 would leave the API as a plottable equator position."""
    result = _tak_upload("tak_ndjson_real_sample.log")
    partial = [e for e in result["tak_events"] if e["lat"] is None]
    assert len(partial) == 35
    assert all(e["lon"] is None and e["has_gps_fix"] is False for e in partial)


# ── ht-modem / ht-router serialization ────────────────────────────────────────
# Neither format has a UI consumer for this data yet — no TX-confirmation KPI
# card, nothing in App.jsx or ChartPanel.jsx reading an input_* field. That makes
# _result_to_dict() the terminus of both data paths rather than a waypoint, so a
# key dropped here would be caught at no layer, ever. These tests are the only
# thing standing under those 14 fields.

def _upload_fixture(fixture_name: str) -> dict:
    return _post(fixture_name, (FIXTURE_DIR / fixture_name).read_bytes())["results"][0]


def test_htmodem_upload_routes_to_the_htmodem_parser():
    result = _upload_fixture("htmodem_sample2.log")
    assert result["log_format"] == "htmodem"
    assert len(result["htmodem"]["tx_packets"]) == 2585


def test_htmodem_tx_packet_serialization_exposes_the_expected_field_set():
    """Pinning the exact key set catches a dropped field and an accidental
    payload bloat alike — the same reason the TAK event test above does it."""
    result = _upload_fixture("htmodem_sample2.log")
    assert set(result["htmodem"]["tx_packets"][0]) == {
        "timestamp", "packet_id", "priority", "local_flag", "chdesc",
        "mod_mode", "fec_mode", "data_length", "encoded_len", "bch_val",
        "symbol_count", "sample_count", "payload_extended_from",
        "payload_extended_to", "queued", "numinqueue",
        "transmitted", "retransmit_count", "transmissions",
    }


def test_htmodem_transmission_confirmation_fields_serialized():
    """The RF telemetry itself — rev/fwd power, S11, and the confirmation's own
    temp_val, which is a different sensor and scale from temp_samples_f and must
    not be folded into it."""
    result = _upload_fixture("htmodem_sample2.log")
    packet = next(p for p in result["htmodem"]["tx_packets"] if p["transmitted"])
    assert set(packet["transmissions"][0]) == {
        "rev_val", "fwd_val", "s11_db", "temp_val",
    }


def test_htmodem_second_confirmation_survives_serialization_as_a_list():
    """transmissions is a list precisely so a second confirmation isn't
    overwritten; serializing only the latest would discard a real observation.
    retransmit_count is an extra-confirmation count, not a confirmed retry —
    see test_htmodem.py for the positional-attribution ambiguity."""
    result = _upload_fixture("htmodem_sample2.log")
    packet = next(p for p in result["htmodem"]["tx_packets"]
                  if p["packet_id"] == 285)
    assert len(packet["transmissions"]) == 2
    assert packet["retransmit_count"] == 1


def test_htmodem_summary_reports_transmitted_and_retransmit_counts():
    summary = _upload_fixture("htmodem_sample2.log")["summary"]
    assert summary["transmitted_count"] == 2542
    assert summary["retransmit_packet_count"] == 42


def test_htmodem_orphaned_counts_both_reach_the_api():
    """orphaned_drop_count and orphaned_transmitted_count are the same kind of
    fact — an event the parser saw but could not attribute. Serializing one and
    not the other makes the unattributed confirmations unreachable from the UI
    or an export, which is the ParseResult chain stopping one step short."""
    htmodem = _upload_fixture("htmodem_sample2.log")["htmodem"]
    assert htmodem["orphaned_drop_count"] == 0
    assert htmodem["orphaned_transmitted_count"] == 1


def test_htmodem_multi_confirmation_limitation_reaches_the_api_response():
    """Prefixed, so the tab banner renders it. An un-prefixed entry reaches the
    file-list red ⚠ but is filtered out of every banner, which is a warning
    with no explanation."""
    result = _upload_fixture("htmodem_sample2.log")
    assert any(e.startswith("DATA LIMITATION — 42 TX packet(s)")
               for e in result["parse_errors"])


def test_htrouter_upload_routes_to_the_htrouter_parser():
    result = _upload_fixture("htrouter_sample3.log")
    assert result["log_format"] == "htrouter"
    assert len(result["htrouter"]["stat_snapshots"]) == 1077


def test_htrouter_snapshot_serialization_exposes_the_link_layer_fields():
    result = _upload_fixture("htrouter_sample3.log")
    snapshot = result["htrouter"]["stat_snapshots"][0]
    assert {
        "input_too_short_link_hdr": 152,
        "input_too_short_link_payload": 237,
        "input_too_short_link_crc": 2,
        "input_wrong_link_version": 579,
        "input_crc_present": 1831,
        "input_bad_crc": 112,
        "input_subframe_no_protocol": 3,
        "input_subframe_logical_recv_error": 11,
        "input_subframe_family_recv_error": 8,
    }.items() <= snapshot.items()


@pytest.mark.parametrize("fixture_name,fmt", [
    ("htmodem_sample2.log", "htmodem"),
    ("htrouter_sample3.log", "htrouter"),
    ("htrouter_sample.log", "htrouter"),
])
def test_next_gen_csv_export_types_all_download_through_the_endpoint(fixture_name, fmt):
    """Every name in _CSV_TYPES must actually download.

    The first version of this test asserted the serializer's *shape* instead —
    it read the table from the response dict, falling back to the nested
    per-format block when the top-level lookup missed. That fallback was
    precisely the lookup `export_csv` did not do, so the test reached the data
    by a path the endpoint couldn't and passed while all eight exports returned
    HTTP 400. Asserting through the real endpoint is the only version of this
    test worth having.

    Also covers the ragged-schema hazard: csv.DictWriter takes its fieldnames
    from row 0 and raises if a later row carries a key row 0 lacks, and these
    two formats omit whole field groups depending on what a session reported.
    """
    from api.routes.export import _CSV_TYPES

    client = _export_client()
    result = _upload_fixture(fixture_name)
    assert result["log_format"] == fmt
    session_id = client.post("/export/session", json=result).json()["session_id"]

    for data_type in sorted(_CSV_TYPES[fmt]):
        response = client.get(f"/export/{session_id}/csv", params={"data_type": data_type})
        # 404 is the documented answer for a table this session genuinely has
        # no rows for; anything else means the type is advertised but unusable.
        assert response.status_code in (200, 404), (
            f"{fmt}/{data_type} -> {response.status_code} {response.text[:120]}"
        )
        if response.status_code == 200:
            header = response.text.splitlines()[0]
            assert header, f"{fmt}/{data_type} returned an empty CSV"


def test_export_types_endpoint_only_advertises_downloadable_types():
    """/types is what a client builds its export menu from, so anything it
    lists must be fetchable — the two must not drift apart again."""
    client = _export_client()
    result = _upload_fixture("htrouter_sample3.log")
    session_id = client.post("/export/session", json=result).json()["session_id"]

    advertised = client.get(f"/export/{session_id}/types").json()["valid_types"]
    assert advertised, "htrouter advertises no export types"
    for data_type in advertised:
        response = client.get(f"/export/{session_id}/csv", params={"data_type": data_type})
        assert response.status_code in (200, 404), (
            f"advertised but not downloadable: {data_type} -> {response.status_code}"
        )


def test_htrouter_total_bad_crc_reaches_the_summary():
    """The Overview KPI row reads this from the summary rather than walking
    stat_snapshots itself, so the serializer is the link that makes the parser's
    cumulative-counter rule the single definition."""
    summary = _upload_fixture("htrouter_sample3.log")["summary"]
    assert summary["total_bad_crc"] == 130


def test_htrouter_total_bad_crc_is_null_when_never_reported():
    summary = _upload_fixture("htrouter_sample.log")["summary"]
    assert summary["total_bad_crc"] is None
    assert summary["total_modem_xmit_failed"] is None


def test_htrouter_absent_link_layer_fields_serialize_as_null_not_zero():
    """The absence convention has to survive JSON too: null reads as 'never
    reported', 0 reads as 'measured, none seen'. A session that never logged
    these counters must not arrive at the UI looking clean."""
    result = _upload_fixture("htrouter_sample.log")
    snapshot = result["htrouter"]["stat_snapshots"][0]
    assert snapshot["input_bad_crc"] is None
    assert snapshot["input_crc_present"] is None
    assert snapshot["input_wrong_link_version"] is None
