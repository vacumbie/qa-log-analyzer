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
        "received_at", "latency_ms",
    }


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


@pytest.mark.parametrize("fixture_name", [
    "tak_stream_sample.json",
    "tak_stream_edge_cases.json",
    "tak_stream_clean_pli_only.json",
    "tak_stream_unknown_categories.json",
])
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
