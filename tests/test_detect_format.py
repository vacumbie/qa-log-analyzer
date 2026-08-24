"""tests/test_detect_format.py

Covers _detect_format() in api/routes/parse.py — the heuristic that picks a
parser from filename + content. Detection ORDER is the thing most likely to
break silently when a new format is added, so the ordering rules documented in
CLAUDE.md ("fw_log first", "relay_manager before rsdk") get dedicated tests.

Convention note: CLAUDE.md says fixtures live in tests/fixtures/, not inline.
The filename-signal and ordering tests below intentionally pass content inline
instead. Filename tests use a bare "{}" because detection is driven by the name,
not the body; ordering tests need synthetic content that mixes markers from two
formats at once — no real log does that, so a fixture file would be misleading.
The per-format detection tests above use the real fixtures.
"""

from pathlib import Path

import pytest

from api.routes.parse import _detect_format

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _content(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


# ── Each real fixture detects as its own format ───────────────────────────────

def test_detects_fw_log_from_fixture():
    assert _detect_format("fw_log_sample.log", _content("fw_log_sample.log")) == "fw_log"


def test_detects_atak_from_fixture():
    # atak_sample.json filename has no diagnostic_atak_ prefix, so this exercises
    # the content path (connectionState / atakVersion / logId markers).
    assert _detect_format("atak_sample.json", _content("atak_sample.json")) == "atak"


def test_detects_relay_manager_from_fixture():
    assert _detect_format(
        "relay_manager_sample.txt", _content("relay_manager_sample.txt")
    ) == "relay_manager"


def test_detects_rsdk_from_fixture():
    assert _detect_format("rsdk_sample_ios.txt", _content("rsdk_sample_ios.txt")) == "rsdk"


def test_detects_diagnostic_from_fixture():
    assert _detect_format(
        "diagnostic_sample.txt", _content("diagnostic_sample.txt")
    ) == "diagnostic"


def test_detects_tak_from_fixture():
    # tak_stream_sample.json has no filename hint here, so this exercises the
    # content path (receivedAt / nodeType / category markers).
    assert _detect_format(
        "tak_stream_sample.json", _content("tak_stream_sample.json")
    ) == "tak"


# ── Filename signals ──────────────────────────────────────────────────────────

def test_atak_detected_by_filename_prefix():
    # The diagnostic_ATAK_ filename convention wins even when content is bare.
    assert _detect_format("diagnostic_ATAK_HOTEL_90215634664458_2026-03-04.log", "{}") == "atak"


def test_atak_filename_match_is_case_insensitive():
    assert _detect_format("DIAGNOSTIC_ATAK_HOTEL_90215634664458_2026-03-04.LOG", "{}") == "atak"


def test_tak_detected_by_filename_convention():
    # Bare "[]" is a valid-but-empty JSON array, so content detection alone
    # would fail here — the filename convention is what carries it.
    assert _detect_format("tak-stream-2026-07-30T19-42-44.json", "[]") == "tak"


# ── Ordering rules (the part that breaks silently) ────────────────────────────

def test_fw_log_wins_over_later_markers():
    """fw_log runs first; its bracket pattern is distinctive and must win even
    when a stray marker from a later format also appears in the content."""
    content = (
        "[100000001-001, TRX, INFO] Energy on chn=0\n"
        "[100000002-001, TRX, INFO] RF Configuration for goTenna Pro\n"
        "[100000003-001, RELAY, INFO] Rx: TTL=255\n"
        '{"logId": 5, "connectionState": "CONNECTED"}\n'
    )
    assert _detect_format("mystery.log", content) == "fw_log"


def test_relay_manager_precedes_rsdk_when_both_match():
    """relay_manager and rsdk both contain AndroidBleRadio lines; the
    na.relaymanager( PID marker must route the log to relay_manager, not rsdk."""
    content = (
        "06-03 14:46:40.100  16170  16170 I na.relaymanager(16170): io_stats\n"
        "06-03 14:46:41.200  16170  16205 D AndroidBleRadio: scan started\n"
    )
    assert _detect_format("capture.txt", content) == "relay_manager"


def test_android_ble_alone_is_rsdk():
    """Without any relay_manager marker, an AndroidBleRadio line is an rsdk log."""
    content = "2026-03-03T15:16:13.515351Z DEBUG Device - PNE1 AndroidBleRadio: connected\n"
    assert _detect_format("capture.txt", content) == "rsdk"


# TAK is checked before ATAK, but only because both are JSON — the two content
# heuristics look at disjoint key sets, so the ordering is defensive rather than
# load-bearing. What IS load-bearing is that disjointness: TAK's signature keys
# (receivedAt/nodeType/category) must not appear in any real ATAK log, or every
# ATAK upload would silently route to the TAK parser and lose its whole dataset.
# These tests pin that, so widening _SIGNATURE_KEYS in parser/tak.py fails loudly.

ATAK_JSON_FIXTURES = sorted(f.name for f in FIXTURE_DIR.glob("atak_*.json"))


def test_atak_fixture_discovery_is_not_empty():
    """The parametrized guard below is only worth anything if the glob matched —
    an empty list would silently collect zero tests."""
    assert len(ATAK_JSON_FIXTURES) >= 5


@pytest.mark.parametrize("fixture_name", ATAK_JSON_FIXTURES)
def test_tak_content_check_does_not_capture_atak_logs(fixture_name):
    assert _detect_format(fixture_name, _content(fixture_name)) == "atak"


def test_tak_filename_check_does_not_capture_atak_filenames():
    """The TAK filename hints run before the ATAK ones — 'diagnostic_ATAK_...'
    contains the substring 'atak' but none of 'tak-stream'/'tak_server'."""
    assert _detect_format(
        "diagnostic_ATAK_HOTEL_90215634664458_2026-03-04.log", "[]"
    ) == "atak"


# The TAK filename hints are substring tests, so the legacy ATAK convention
# collides whenever the callsign starts with SERVER: diagnostic_ATAK_SERVER_...
# lowercases to a name containing "tak_server". The file is valid JSON, so the
# TAK parser doesn't error — it skips all 10 records for a missing 'time' field
# and reports an empty stream, losing the whole log silently. The content guard
# is what stops it; these pin the guard.

SERVER_CALLSIGN_FILENAMES = [
    "diagnostic_ATAK_SERVER_90215634664458_2026-03-04.log",
    "diagnostic_ATAK_SERVER1_90215634664458_2026-03-04.log",
    "diagnostic_TAK_SERVER_90215634664458_2026-03-04.log",  # v3.0 drops ATAK_
]


@pytest.mark.parametrize("filename", SERVER_CALLSIGN_FILENAMES)
def test_atak_content_wins_over_a_colliding_tak_filename(filename):
    assert _detect_format(filename, _content("atak_sample.json")) == "atak"


@pytest.mark.parametrize("fixture_name", ATAK_JSON_FIXTURES)
def test_server_callsign_collision_holds_for_every_atak_fixture(fixture_name):
    """Same collision, swept across every real ATAK fixture — the guard must not
    depend on which markers a particular log happens to carry."""
    assert _detect_format(
        "diagnostic_ATAK_SERVER_90215634664458_2026-03-04.log", _content(fixture_name)
    ) == "atak"


def test_empty_tak_export_still_detected_by_filename():
    """The guard refuses the filename hint only when the content is positively
    ATAK — an empty TAK export carries no signal either way and must still
    route to tak, not fall through to the diagnostic catch-all."""
    assert _detect_format("tak-stream-2026-07-30T19-42-44.json", "[]") == "tak"


# ── Fallback ──────────────────────────────────────────────────────────────────

def test_unrecognized_content_falls_back_to_diagnostic():
    assert _detect_format("mystery.txt", "nothing recognizable here\n") == "diagnostic"
