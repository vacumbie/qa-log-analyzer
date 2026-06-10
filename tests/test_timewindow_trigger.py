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

NOTE: TS_RE is duplicated from FileUpload.jsx on purpose. If the JS regex
changes, this copy should change with it — a drift here is a signal, not a bug.
"""

import re
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"

# Canonical copy of TS_RE from ui/src/components/FileUpload.jsx
TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")


def _has_wallclock_timestamp(fixture_name):
    """True if the client-side scanner would find a parseable time range."""
    text = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8")
    return TS_RE.search(text) is not None


# ── Fixture availability ──────────────────────────────────────────────────────

def test_fixtures_exist():
    assert (FIXTURE_DIR / "fw_log_sample.log").exists()
    assert (FIXTURE_DIR / "relay_manager_sample.txt").exists()


# ── The disabled-step trigger ─────────────────────────────────────────────────

def test_fw_log_has_no_wallclock_timestamp_so_disabled_step_fires():
    # fw_log timestamps are relative ms from boot ([100000000-000, ...]) with no
    # wall-clock date, so the scanner finds nothing and routes to range-unavailable.
    assert _has_wallclock_timestamp("fw_log_sample.log") is False


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
