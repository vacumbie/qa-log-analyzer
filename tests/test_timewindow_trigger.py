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
from datetime import datetime, timezone
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


def _iso_to_ms(ts):
    """Mirror normaliseTs() in FileUpload.jsx: treat the wall-clock string as UTC."""
    return int(
        datetime.fromisoformat(ts.replace(" ", "T"))
        .replace(tzinfo=timezone.utc)
        .timestamp()
        * 1000
    )


def _extract_time_range(fixture_name):
    """Python mirror of extractTimeRange(): union of wall-clock and epoch-ms hits,
    returned as (minMs, maxMs) or None. Used to pin the union *value*, not just the
    boolean that a range exists."""
    text = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8")
    vals = [_iso_to_ms(m) for m in TS_RE.findall(text)]
    vals += [int(g) for g in EPOCH_MS_RE.findall(text)]
    if not vals:
        return None
    return min(vals), max(vals)


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


# ── Each matched key is exercised individually (not just collectively) ────────
# test_epoch_ms_matches_session_timestamp_keys loops all three, but loops can
# mask a single-arm regression. Pin each arm with its own named scenario.

def test_epoch_ms_matches_timestamp_in_millis():
    m = EPOCH_MS_RE.search('"timestampInMillis": 1780500001000')
    assert m and m.group(1) == "1780500001000"


def test_epoch_ms_matches_launch_time_in_millis():
    m = EPOCH_MS_RE.search('"launchTimeInMillis": 1780500000000')
    assert m and m.group(1) == "1780500000000"


def test_epoch_ms_matches_message_timestamp_in_millis():
    m = EPOCH_MS_RE.search('"messageTimestampInMillis": 1780500010000')
    assert m and m.group(1) == "1780500010000"


# ── Anchoring risk: messageTimestampInMillis CONTAINS timestampInMillis ───────
# The alternation includes both `timestampInMillis` and `messageTimestampInMillis`.
# The leading `"` is what prevents the shorter arm from matching the substring
# inside the longer key — without it, `messageTimestampInMillis` would yield a
# spurious match starting mid-word. Pin that the match spans the whole key.

def test_message_timestamp_key_matches_as_whole_key_not_inner_substring():
    line = '"messageTimestampInMillis": 1780500010000'
    m = EPOCH_MS_RE.search(line)
    assert m is not None
    # The match must begin at the opening quote of the full key, not at the
    # 'timestampInMillis' substring 7 chars in.
    assert m.group(0) == line


def test_unquoted_timestamp_substring_does_not_match():
    # Only quoted JSON keys are timestamps. A bare substring (e.g. inside prose
    # or a different identifier) must never be read as a session timestamp.
    assert EPOCH_MS_RE.search("XmessageTimestampInMillis: 1780500010000") is None


# ── Digit-count boundary: exactly 13, the  guard ───────────────────────────

def test_epoch_ms_rejects_twelve_digit_value():
    assert EPOCH_MS_RE.search('"timestampInMillis": 178050000100') is None


def test_epoch_ms_rejects_fourteen_digit_value():
    # \d{13} fails when a 14th digit follows (no word boundary mid-number), so a
    # 14-digit value is rejected rather than silently truncated to its first 13.
    assert EPOCH_MS_RE.search('"timestampInMillis": 17805000010000') is None


def test_epoch_ms_rejects_negative_value_under_valid_key():
    # A negative value can never be a wall-clock epoch ms; the leading '-' is not
    # consumed and \d{13} cannot anchor, so it is excluded.
    assert EPOCH_MS_RE.search('"timestampInMillis": -1780500001000') is None


def test_epoch_ms_tolerates_whitespace_around_colon():
    # JSON pretty-printers vary the spacing; the scanner must not depend on it.
    assert EPOCH_MS_RE.search('"timestampInMillis"  :   1780500001000') is not None


# ── Union behavior — the enhanced log uses BOTH sources, and ISO widens it ────
# atak_enhanced_sample.json carries epoch-ms records AND sdkError ISO timestamps
# that fall OUTSIDE the epoch-ms span. test_atak_enhanced_log_detected only proves
# a range exists (epoch-ms alone is enough). This pins that the union actually
# widens the range — if extractTimeRange dropped the wall-clock branch, the slider
# would silently under-cover the session and this test would catch it.

def test_enhanced_log_union_widens_range_beyond_epoch_ms_alone():
    text = (FIXTURE_DIR / "atak_enhanced_sample.json").read_text(encoding="utf-8")
    epoch_max = max(int(g) for g in EPOCH_MS_RE.findall(text))
    union_min, union_max = _extract_time_range("atak_enhanced_sample.json")
    iso_max = max(_iso_to_ms(m) for m in TS_RE.findall(text))
    # The fixture is constructed so sdkError ISO timestamps run later than the last
    # epoch-ms record; the union must reflect the later ISO bound.
    assert iso_max > epoch_max, (
        "fixture precondition: atak_enhanced_sample.json must have an sdkError ISO "
        "timestamp later than its last epoch-ms record for this union test to be meaningful"
    )
    assert union_max == iso_max


def test_regular_atak_log_range_comes_only_from_epoch_ms():
    # No wall-clock string in a regular ATAK log, so the union equals the epoch-ms
    # min/max — confirms the epoch-ms branch alone produces a usable range.
    text = (FIXTURE_DIR / "atak_sample.json").read_text(encoding="utf-8")
    epochs = [int(g) for g in EPOCH_MS_RE.findall(text)]
    assert _extract_time_range("atak_sample.json") == (min(epochs), max(epochs))
