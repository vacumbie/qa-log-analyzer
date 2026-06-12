"""
tests/test_timewindow_trigger.py

Pins the premise behind the upload flow's time-window step routing.

`extractTimeRange()` in `ui/src/components/FileUpload.jsx` scans the head+tail
of each uploaded file for wall-clock timestamps using:

    TS_RE = /\\d{4}-\\d{2}-\\d{2}[T ]\\d{2}:\\d{2}:\\d{2}/g   (requires a 4-digit year)

If it finds a match, the upload flow shows the working time-window slider; if it
finds none, it routes to the disabled `range-unavailable` step. That routing
decision is therefore entirely a property of the *log text*, not of the parser.

There is no JS test runner in this repo (the stack is intentionally lean — see
CLAUDE.md), so we cannot unit-test the JS function directly. Instead we assert
the same premise against the real fixtures with the canonical regex replicated
below. This is exactly the test that would have caught the original false
premise ("relay_manager omits the year → disabled step"): relay_manager logs
actually carry a year-bearing ISO timestamp, so they route to the slider, and
fw_log — relative ms from boot, no wall clock — is the real disabled-step trigger.

ATAK logs carry no wall-clock string — they store epoch milliseconds under
`timestampInMillis` / `launchTimeInMillis` / `messageTimestampInMillis`. The
scanner now also matches those (EPOCH_MS_RE) and unions the two sources, so
regular ATAK logs regain the slider instead of routing to range-unavailable.

NOTE: TS_RE and EPOCH_MS_RE are duplicated from FileUpload.jsx on purpose. If
either JS regex changes, this copy should change with it — a drift here is a
signal, not a bug.
"""

import re
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"

# Canonical copies of the scanner regexes from ui/src/components/FileUpload.jsx
TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")
EPOCH_MS_RE = re.compile(
    r'"(?:timestampInMillis|launchTimeInMillis|messageTimestampInMillis)"\s*:\s*(\d{13})\b'
)


def _has_wallclock_timestamp(fixture_name):
    """True if the wall-clock scanner alone would find a timestamp."""
    text = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8")
    return TS_RE.search(text) is not None


def _has_detectable_range(fixture_name):
    """True if the scanner (wall-clock OR epoch-ms) would find a time range —
    i.e. the upload flow shows the slider rather than the range-unavailable step."""
    text = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8")
    return TS_RE.search(text) is not None or EPOCH_MS_RE.search(text) is not None


# ── Fixture availability ──────────────────────────────────────────────────────

def test_fixtures_exist():
    assert (FIXTURE_DIR / "fw_log_sample.log").exists()
    assert (FIXTURE_DIR / "relay_manager_sample.txt").exists()


# ── The disabled-step trigger ─────────────────────────────────────────────────

def test_fw_log_has_no_detectable_range_so_disabled_step_fires():
    # fw_log timestamps are relative ms from boot ([100000000-000, ...]) with no
    # wall-clock date AND no epoch-ms JSON keys, so neither scanner matches and the
    # flow routes to range-unavailable. fw_log is now the sole disabled-step trigger
    # among the fixtures (ATAK regained the slider via EPOCH_MS_RE).
    assert _has_wallclock_timestamp("fw_log_sample.log") is False
    assert _has_detectable_range("fw_log_sample.log") is False


def test_relay_manager_has_wallclock_timestamp_so_slider_is_shown():
    # relay_manager System.out lines carry an internal ISO timestamp with year
    # (e.g. 2026-06-03T14:46:41.944712Z), so the scanner parses a range and shows
    # the working slider. Guards against re-introducing the old false premise.
    assert _has_wallclock_timestamp("relay_manager_sample.txt") is True


# ── Regex behavior — the year requirement ─────────────────────────────────────

def test_year_bearing_iso_timestamp_matches():
    assert TS_RE.search("Command relayHealthRequestCall 2026-06-03T14:46:41.944712Z")


def test_logcat_prefix_without_year_does_not_match():
    # The MM-DD HH:MM:SS.mmm logcat prefix alone (no year) must NOT match —
    # this is what was originally, wrongly, assumed to trigger the disabled step.
    assert TS_RE.search("06-03 14:46:40.100  16170  16170 I na.relaymanager") is None


def test_relative_ms_from_boot_does_not_match():
    assert TS_RE.search("[100000002-001, TRX, INFO] RF Configuration") is None


# ── ATAK epoch-ms detection (the new path) ────────────────────────────────────
# Regular ATAK logs carry no wall-clock string, only epoch-ms JSON fields, so
# before EPOCH_MS_RE they routed to range-unavailable and lost the slider.

def test_atak_regular_log_is_invisible_to_wallclock_scanner():
    # The bug: a regular ATAK log has no YYYY-MM-DD string at all.
    assert _has_wallclock_timestamp("atak_sample.json") is False


def test_atak_regular_log_now_detected_via_epoch_ms():
    # The fix: epoch-ms keys give it a detectable range → slider restored.
    assert _has_detectable_range("atak_sample.json") is True


def test_atak_multiserial_log_detected_via_epoch_ms():
    assert _has_detectable_range("atak_multiserial_sample.json") is True


def test_atak_enhanced_log_detected():
    # Enhanced logs carry both sdkError ISO timestamps and epoch-ms records;
    # either source is enough, and the scanner unions them.
    assert _has_detectable_range("atak_enhanced_sample.json") is True


# ── EPOCH_MS_RE behavior — which keys it captures ─────────────────────────────

def test_epoch_ms_matches_session_timestamp_keys():
    for key in ("timestampInMillis", "launchTimeInMillis", "messageTimestampInMillis"):
        m = EPOCH_MS_RE.search(f'"{key}": 1780500001000')
        assert m and m.group(1) == "1780500001000", key


def test_epoch_ms_excludes_duration_keys():
    # deliveryTimeInMillis is a duration (0, negative, or small) and updateTimeInMillis
    # is a firmware-update field — neither is a session timestamp, so capturing them
    # would corrupt the min/max range. Key anchoring must exclude them.
    assert EPOCH_MS_RE.search('"deliveryTimeInMillis": 0') is None
    assert EPOCH_MS_RE.search('"deliveryTimeInMillis": -200') is None
    assert EPOCH_MS_RE.search('"deliveryTimeInMillis": 1780500001000') is None
    assert EPOCH_MS_RE.search('"updateTimeInMillis": 1780500003000') is None


def test_epoch_ms_requires_exactly_13_digits():
    # A short duration-like value under a timestamp key must not be read as epoch ms.
    assert EPOCH_MS_RE.search('"timestampInMillis": 2006') is None
    assert EPOCH_MS_RE.search('"timestampInMillis": 1780500001000') is not None
