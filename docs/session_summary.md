# QA Log Analyzer — Session Summary
_Last updated: 2026-07-29_

---

## Project Identity

**Repo:** https://github.com/vacumbie/qa-log-analyzer  
**Owner:** Valerie Cumbie (`vacumbie`)  
**Description:** Local log parsing and visualization tool for goTenna mesh network diagnostic data.  
**Machine path (Windows):** `C:\Users\Valerie.Cumbie\Documents\qa-log-analyzer`  
**Machine path (Mac/Linux):** `~/Documents/qa-log-analyzer`

---

## Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Parser | Python 3.10+ | Pure stdlib + dataclasses |
| API | FastAPI + Uvicorn | `cd api && uvicorn main:app --reload --port 8000` |
| UI | React 18 + Vite | `cd ui && npm run dev` → http://localhost:5173 |
| Charts | Chart.js 4.4 + react-chartjs-2 | Line and Bar only; NO annotation plugin |
| Tests | Pytest | `pytest tests/` from repo root with venv active |
| Fonts | Barlow Condensed, Rajdhani, Share Tech Mono | Via Google Fonts `<link>` in `index.html` |
| CI | GitHub Actions | Pytest on every push/PR |

**Critical UI rules:**
- Do NOT add npm packages unless Chart.js 4.4, React 18, or plain CSS can't do it
- Leaflet.js (Hop Count Map) loaded from unpkg CDN — not installed via npm
- Playwright (if needed for browser testing): use `channel: 'msedge'` — bundled Chromium doesn't work on Valerie's machine

---

## Log Formats — 5 Supported

Detection order in `_detect_format()` — ORDER MATTERS:

| Priority | Key | Parser | Detection Marker |
|----------|-----|--------|-----------------|
| 1 | `fw_log` | `parser/fw_log.py` | `[digits-digits, MODULE, LEVEL]` bracket pattern |
| 2 | `atak` | `parser/atak.py` | `logId` / `connectionState` / `atakVersion` JSON keys |
| 3 | `relay_manager` | `parser/relay_manager.py` | `na.relaymanager(` or `com.gotenna.relaymanager` — MUST be before rsdk |
| 4 | `rsdk` | `parser/rsdk.py` | `IosBleRadio` or `AndroidBleRadio` or `GRIP_SENDER` |
| 5 | `diagnostic` | `parser/diagnostic.py` | Catch-all fallback |

---

## Architecture Decisions (Critical — Don't Change Without Reading CLAUDE.md)

1. **ParseResult is the ONLY contract.** Every parser returns `ParseResult` from `models.py`. API serializes via `_result_to_dict()` in `parse.py`. UI reads the dict. The chain is: `models.py` → parser → `_result_to_dict()` → UI. Skip any step = silent failure.

2. **Temperature:** Log files record Celsius. Convert to °F in `_result_to_dict()` ONLY. Never in a parser. Never in a UI component. Fields: `pa_temp_f`, `system_temp_f`.

3. **RSDK hop count:** Only from `GRIP_Receiver` incoming fields lines. Old `SendMessageResponse` hop count was an SDK sequence counter — still excluded.

4. **FileUpload uses createPortal:** The upload modal renders via `createPortal(..., document.body)` to escape the header's `backdropFilter: blur(12px)` stacking context. Do not move it back inside the header.

5. **Time series charts use normalized 0–100% x-axis** (`buildRelativeTimeSeries()` / `buildGripRssiSeries()`). Exception: Battery % Over Time uses real wall-clock UTC.

6. **CHART_MAP in ChartPanel.jsx:** All charts must be registered here. A key in `App.jsx` that's missing from `CHART_MAP` silently renders nothing.

7. **Chart registration order:** `fw_log` detection first (bracket pattern distinctive). `relay_manager` before `rsdk` (both have AndroidBleRadio lines).

8. **GID collision fix:** CL_B + gt_Sassy_B_Net share GID `90194071247761` and serial `PNE233200347`. PLI `nodeMap` uses `gid|source_filename` as key.

9. **Health Score:** Scoped to `atak`, `diagnostic`, `rsdk` only via `HEALTH_FORMATS` in `App.jsx`. `relay_manager` excluded (no dimension data → misleading 5/5).

---

## Design Tokens (Use These — Don't Drift)

```js
const C = {
  accent: '#00d4ff',   // cyan — primary highlight
  green:  '#00e5a0',
  yellow: '#ffd166',
  red:    '#ff4757',
  muted:  '#4a6080',
  dim:    '#2a3a52',
}
const PALETTE = ['#00d4ff','#ff6b35','#ffd166','#c77dff','#00e5a0','#ff4757','#4a90e2','#ff6b9d']
```
Backgrounds: `#060d16` page · `#080e18` panel · `#0f1923` card  
Fonts: `'Barlow Condensed'` (display) · `'Rajdhani'` (body) · `'Share Tech Mono'` via `var(--mono)`

---

## 14 Tabs (Current State)

| # | Tab Key | Name | Gate | Status |
|---|---------|------|------|--------|
| 1 | `overview` | Overview | Always | ✅ |
| 2 | `pli` | PLI Frequency | diagnostic or atak loaded | ✅ |
| 3 | `txrx` | TX/RX Analysis | Always | ✅ |
| 4 | `sessions` | Sessions & Radio Stats | Always | ✅ |
| 5 | `thermal` | Thermal | Always | ✅ |
| 6 | `battery` | Battery | Always | ✅ |
| 7 | `hops` | Hop Count | Always | ✅ |
| 8 | `rssi` | RSSI | Always | ✅ |
| 9 | `chat` | Chat Activity | Always | ✅ |
| 10 | `health` | Health Score | Always (device formats only) | ✅ |
| 11 | `relay-health` | Relay Health | Always visible; dimmed + empty state when no relay_manager log loaded | ✅ |
| 12 | `atak` | ATAK (α badge) | atak loaded | ✅ |
| 13 | `fw-log` | FW Log | Always visible; dimmed + empty state when no fw_log loaded | ✅ |
| 14 | `topology` | Network Topology | NOT IMPLEMENTED | ⚠️ Design spec only |

---

## Known Data Limitations (Surface Honestly — Never Paper Over)

| Format | Limitation |
|--------|-----------|
| `relay_manager` | BLE payloads captured but NOT decoded — SNR, battery%, temp°F, uptime, FW version are raw hex bytes |
| `relay_manager` | Single relay node per observed session — multi-node unknown |
| `relay_manager` | Prod logs not analyzed — stage/prod behavioral differences unknown |
| `rsdk` | GRIP hop count and RSSI only when `GRIP_Receiver` incoming fields lines are present |
| `diagnostic` | Firmware 3.1.11 omits callsign and GID from Received Message blocks |
| `atak` | `originatorCallsign`/`receiverCallsign`/UUIDs always empty — identity for those is GID-only. `senderCallsign` IS populated in ATAK plugin v3.0+ (was always empty before) and is now the `device.callsign` fallback when filename parsing doesn't yield one |
| `atak` | ATAK v3.0 filenames drop the `ATAK_` segment (`diagnostic_<CALLSIGN>_<GID>_...`) — both conventions now accepted by the filename regex |
| `atak` | Some early ATAK v3.0 builds emit **zero device-health (`connectionState`) records** for a session — no battery/thermal/firmware/radio-health data at all. Flagged via `DATA LIMITATION —` in `parse_errors`, fires only when it actually happens. RSSI also observed as always `0` in early v3.0 captures. See `docs/atak_v3_early_integration_notes.md` |
| `atak` | `sdkError` (SDK Logging 2.0) volume baseline unknown — count is informational, not pass/fail |
| `atak` | `numberOfOpenSegments = -99` is a sentinel → stored as null |
| `atak` | Receiver-side `deliveryTimeInMillis = 0` on fileTransfer is a placeholder |
| `atak` | `serialNumber = "Unknown"` during BLE reconnection is expected, not an error |
| `fw_log` | Timestamps are relative ms from boot — not wall clock |
| `fw_log` | Serial number and FW version in binary RHC payload — not plaintext |
| `fw_log` | Battery stabilization errors are a known FW quirk — counted separately |
| `fw_log` | `RSSI[]` samples are DEBUG-level and skipped — channel energy is the RSSI proxy |
| `atak` | `deviceDisconnected` omits serial — attribution uses LIFO assumption (pending dev team confirmation) |
| `atak`/`diagnostic` | Host-clock skew not auto-detected/corrected — a wrong phone clock offsets all `timestampInMillis` uniformly (makes `deliveryTimeInMillis` a large constant, even negative); timestamps stored verbatim, interpret manually. Confirmed: KNOT ≈ −2h. See P6 |

---

## Backlog Status

| Item | Status |
|------|--------|
| Time Window Filtering | ✅ Done |
| GRIP RSSI Line Graph Over Time | ✅ Done |
| ATAK Enhanced Log (SDK Logging 2.0) | ✅ Done |
| FW Log — relay firmware parser & tab | ✅ Done |
| PLI tab overhaul + battery chart real UTC timestamps | ✅ Done (PR #6) |
| P5: Battery critical threshold < 10% | ✅ Done |
| P1: MESMER BLE tag profile (BLE\|DEBUG vs ERROR\|BLE) | ✅ Done (PR #4) |
| Hop Count Map (Leaflet, ATAK only) | ✅ Done |
| GID collision fix (CL_B + gt_Sassy_B_Net) | ✅ Done |
| PLI Settings section (pliSettingUpdated) | ✅ Done |
| Battery chart real UTC timestamps + per-serial lines | ✅ Done |
| PLI tab ATAK support + gap inference | ✅ Done |
| DATA LIMITATION prefix normalization (em-dash) across all 5 parsers | ✅ Done (PR #19) |
| diagnostic 3.1.11 `parse_errors` emission (callsign + GID omitted) | ✅ Done (PR #19) |
| rsdk GRIP-availability `parse_errors` emission | ✅ Done (PR #19) |
| Quality-gate agent deduplication (single-owner responsibilities) | ✅ Done (PR #20) |
| General DATA LIMITATION banner for diagnostic/rsdk/atak tabs | ⏳ Pending — jenny (PR #19 gate) found CLAUDE.md:299 promises a UI banner per limitation, but diagnostic 3.1.11 & atak sdkError entries reach `parse_errors` + the file-list ⚠ glyph only (rsdk shown via HopsTab note); CLAUDE.md qualified, banner deferred |
| API route double-translates CRLF → diagnostic CRLF uploads parse to 0 blocks | ✅ Fixed (PR #21, merged) — karen found during PR #19 gate; temp file now opened with `newline=""`, plus `tests/test_parse_route.py` API-path regression test |
| FW Log — RHC payload decoding (hash→serial, FW version) | ⛔ Blocked — waiting on mapping tables from QA |
| Session Persistence | ⏸ Deferred |
| Relay Manager prod log support | ⛔ Blocked — waiting on prod samples |
| BLE payload decoding (relay health attributes) | ⛔ Blocked — waiting on protocol spec |
| Relay Manager JSON log format (SDK Logging 2.0) | ⏳ Pending — format in design |
| Health Score threshold validation | ⏳ Pending — blocked on field data |
| P2: Protocol separation (BROADCAST/PRIVATE) in TX/RX | ⏳ Pending |
| P3: Cross-device delivery matrix using logId | ⏳ Pending |
| P4: Relay copy/retransmission flag | ⏳ Pending |
| P6: KNOT clock skew investigation | ✅ Done (tool-side, 2026-06-30) — constant ≈ −2h host-clock skew (uniform across all 50 senders, hop-independent, no buffer lag), documented as a `DATA LIMITATION` in `parsing-requirements.md`; no parser/UI work possible. **Two QA questions remain open as external, non-blocking follow-ups** (which clock was correct; tz/NTP-vs-manually-wrong root cause — see `parsing-requirements.md` P6). GID `90296226464906` KNOT-vs-HOTLIPS **attribution resolved** — same physical radio (`PNE234200704`) used by both operators on different test days, not a mislabel |
| P7: Poseidon log format | ⏳ Deferred |
| Network Topology tab (Section 14) | ⏳ Pending (design spec exists) |
| Time-window disabled state for unparseable timestamps | ✅ Done — `range-unavailable` step in FileUpload.jsx replaces the silent skip |
| Min battery windowed reduce returns 0 for single-sample sets (ATAK) | ✅ Done — IIFE pattern: `(batPcts => batPcts.length ? Math.min(...batPcts) : null)(filtered)` |
| `extractTimeRange` doesn't detect ATAK epoch-ms timestamps (`timestampInMillis`) — ATAK logs lose the time-window slider | ✅ Done — scanner now unions wall-clock `TS_RE` with a key-anchored 13-digit `EPOCH_MS_RE`; ATAK regains the slider; client-side only |
| Battery Chart — Multi-Radio False Recovery DataNote | ⏳ Pending dev team confirmation |
| ATAK v3.0 filename convention support (`ATAK_` segment optional) + `device.callsign` fallback via `senderCallsign` | ✅ Done (2026-07-29) — `_FILENAME_RE` accepts both conventions; new `sender_callsign` field on `AtakMessage`; callsign falls back to it when filename doesn't match |
| ATAK v3.0 missing-health-telemetry `DATA LIMITATION` | ✅ Done (2026-07-29) — `parser/atak.py` flags it in `parse_errors` when a log has zero `connectionState` records |
| ATAK v3.0 test fixtures + coverage | ✅ Done (2026-07-29) — 2 new synthetic fixtures, 8 new tests in `test_atak.py`; suite at 183 passed, 2 skipped |

---

## Claude Code Agents (in `.claude/agents/`)

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| `jenny` | Spec compliance auditor | Feature claimed complete — verify against docs |
| `karen` | Reality manager / no-nonsense status check | Something feels off, verify what actually works |
| `parser-agent` | Full parser chain specialist | Adding/modifying any parser or ParseResult field |
| `log-analyst` | Raw log analysis before parser is written | New log file arrives — understand it first |
| `docs-agent` | Keeps all 4 docs in sync with code | After any significant code change |
| `peer-reviewer` | Pre-merge code review | Before merging a branch |
| `vera` | Unit test specialist — writes tests, audits coverage gaps, ensures fixtures are realistic | After parser work (adding/modifying a parser), when coverage feels thin, or as a routine pre-merge check |
| `task-completion-validator` | End-to-end completion check | After claiming a feature is done |
| `code-quality-pragmatist` | Simplicity check | After implementing — check for over-engineering |
| `claude-md-compliance-checker` | Verifies against CLAUDE.md rules | After any significant change |

---

## Standing Rules (Always Apply)

- **Temperature:** Always °F in UI. Convert in `_result_to_dict()` only.
- **Data limitations:** Flag honestly in `parse_errors` with `DATA LIMITATION —` prefix. Never silently drop fields or return zeros.
- **Log format detection:** Never assume — auto-detect via `_detect_format()`.
- **No npm packages** without justification (Chart.js 4.4, React 18, plain CSS first).
- **Commit format:** `type(scope): description` — e.g. `feat(parser): add relay_manager`
- **Tests are first-class code.** Fixtures in `tests/fixtures/`, not inlined as strings.
- **Readability over cleverness.** A clear `for` loop beats a clever comprehension.
- **Comments explain WHY, not what.** The code explains what; comments explain parser quirks, CSS workarounds, format inconsistencies.
- **Fetch current file state before editing.** Never assume files match a previous session's output.

---

## How to Start Dev Environment

```bash
# Terminal 1 — API (Windows PowerShell)
cd C:\Users\Valerie.Cumbie\Documents\qa-log-analyzer
.\venv\Scripts\activate
cd api
uvicorn main:app --reload --port 8000

# Terminal 2 — UI (both platforms)
cd <repo-root>/ui
npm run dev
# → http://localhost:5173

# Run tests
pytest tests/           # full suite
pytest tests/ -x        # stop on first failure
pytest tests/test_atak.py -v  # single file verbose
```

---

## Most Recent Work (Last Few PRs)

**2026-07-29 — ATAK plugin v3.0 early-integration support (filename, callsign fallback, missing-health DATA LIMITATION):**
- Two real field logs introduced (`diagnostic_BARK_65043_2026-07-28_15_09_17_944.log`,
  `diagnostic_EUD-009_54498_2026-07-29_04_02_14_14.log`) — first logs seen from the new
  ATAK plugin v3.0 build (app version `3.0.0 (dae7d160) - [5.6.0]`, ATAK `5.6.0.21`,
  Samsung SM-S931U1). Both parsed clean as `atak` format (format detection unaffected —
  content sniffing on `logId`/`atakVersion` still matches), but surfaced two real gaps:
- **Filename convention changed:** v3.0 drops the `ATAK_` segment
  (`diagnostic_<CALLSIGN>_<GID>_<DATE>_<TIME>.log` vs the old
  `diagnostic_ATAK_<CALLSIGN>_<GID>_...`). `_FILENAME_RE` in `parser/atak.py` now accepts
  both. Added a `senderCallsign` fallback for `device.callsign` (new `sender_callsign` field
  on `AtakMessage`, mirroring the existing GID fallback pattern) for cases where neither
  filename convention matches at all.
- **Missing device-health telemetry:** both new logs contained **zero `connectionState`
  records** — no battery/thermal/firmware/radio-health data for the whole session. Confirmed
  expected — brand new FW/radio combo, early integration. Added a `DATA LIMITATION —` entry
  in `parse_errors` when this happens, rather than silently rendering empty Thermal/Battery
  tabs. Also noted (not yet acted on): RSSI is always `0` in these logs, and PLI interval
  shows inconsistent values within one session.
- **New doc:** `docs/atak_v3_early_integration_notes.md` — running baseline of what's
  actually available in v3.0 logs as the plugin/FW matures (present/absent/inconsistent
  data categories, source log table to extend as more samples come in).
- **Docs synced to reflect the fix** (were stating things now factually wrong):
  `CLAUDE.md` (Known Data Limitations table), `docs/parsing-requirements.md` (Filename
  Convention sections ×2, "Callsign/UUID fields always empty" claims ×3, Known Limitations),
  `docs/log-field-definitions.md` (`senderCallsign` field row, Device Health record note).
- **Tests:** 2 new synthetic fixtures (`diagnostic_KESTREL_11223_2026-07-28_09_00_00_000.log`
  for the new filename convention, `atak_v3_no_health_sample.json` for the callsign fallback
  + missing-health-limitation path) and 8 new tests in `test_atak.py`, including a regression
  guard that the new DATA LIMITATION does NOT fire when health samples are present. Full
  suite: **183 passed, 2 skipped** (the 2 skips are the pre-existing real-field-data tests
  gated on `NAMED_FIXTURE`, unrelated to this work).
- Delivered as a zip (parser/atak.py, parser/models.py, tests/test_atak.py, 2 fixtures,
  docs/atak_v3_early_integration_notes.md) for manual drop-in rather than a PR from this
  session — not yet run through jenny/karen/vera in Claude Code.

**2026-06-30 — docs(p6): close P6 KNOT clock skew tool-side:**
- The P6 investigation (2026-06-15) had already concluded: constant ≈ −2h **host-clock skew** on KNOT,
  uniform across all 50 senders, hop-independent, no buffer lag — genuine clock skew, not delivery lag.
  A single log cannot detect or correct the offset, so there is **no parser/UI work to do**.
- Documented the conclusion as a **`DATA LIMITATION`** in `parsing-requirements.md` (`## Known Limitations`):
  host-clock skew is not auto-detected/corrected; timestamps are stored verbatim and must be interpreted
  manually; distinguished from normal *sporadic* per-message negative `deliveryTimeInMillis`.
- Marked **P6 ✅ Done (tool-side)** in `CLAUDE.md` (backlog row + P1–P7 summary) and this file (backlog row
  + Known Data Limitations table). The **two QA questions** (which clock was correct; tz/NTP-vs-manually-wrong
  root cause) are reframed from "blockers" to **external, non-blocking follow-ups** — they are QA field
  actions, not codebase work. GID attribution remains resolved (2026-06-16, shared radio `PNE234200704`).
- Docs-only change; no code, tests, parsers, or `_result_to_dict` touched.

**2026-06-16 — Afternoon session wrap (parser-honesty PRs #19–#21, GID identity #27, P6 + buffer-saturation analysis):**
- **PR #19 — `parse_errors` honesty pass (157 tests passing):** canonical `DATA LIMITATION — ` (em-dash)
  prefix normalized across all 5 parsers; diagnostic 3.1.11 callsign+GID-omission emission (data-driven,
  fires only when a Received Message block omits both, reports "{n} of {total}"); rsdk GRIP-availability
  emission (no `GRIP_Receiver` incoming fields → hop/RSSI unavailability surfaced honestly).
- **vera first run (quality gate):** found **3 real coverage gaps**; all fixed by `parser-agent` before merge.
- **PR #20 — agent suite deduplication (✅ merged):** single-owner responsibilities; revised karen,
  task-completion-validator, jenny; code-quality-pragmatist drafted. No further agent-dedup PR pending.
- **PR #21 — CRLF route bug (✅ merged):** API route double-translated CRLF, so diagnostic CRLF uploads
  parsed to 0 blocks; temp file now opened with `newline=""`, plus `tests/test_parse_route.py` API-path
  regression test. Surfaced by karen during the PR #19 gate.
- **P6 KNOT clock skew — investigated:** constant ≈ −2h host-clock skew (uniform across all 50 senders,
  hop-independent, no buffer lag; not delivery lag). **Two QA questions documented as blockers** (see
  `parsing-requirements.md` P6). **GID attribution resolved** — shared physical radio. *(Closed tool-side
  2026-06-30 — see entry below.)*
- **PR #27 — GID-as-radio-identity clarification (✅ merged):** GID reflects the radio paired at
  log-export time, **not** a permanent operator identity; **callsign + serial number together are the
  reliable identity pair.** New "GID, Callsign, and Serial Number — Identity Model" section in
  `parsing-requirements.md`.
- **HOTLIPS + MESMER `storedMessages` buffer saturation:** analysis confirmed **systemic** — a
  **30-message hard ceiling**; the buffer fills while the device is CONNECTED, then PLI **bursts on drain**.
  (Detail in the 2026-06-12 web-session entry below.)
- **Troubleshooting docs — created in a web session, NOT yet committed to this repo:**
  `HotLips_Troubleshooting.md` and `MESMER_Troubleshooting.md` (see the 2026-06-12 entry below) are
  **not present in `docs/`** as of this entry — pending commit, not shipped artifacts.

**2026-06-16 — docs: clarify GID-as-radio-identity (PR #27, docs only):**
- Documented the architectural clarification that **GID reflects the radio paired at log-export time,
  not a permanent operator identity**: callsign = operator/app instance, serial = physical radio
  hardware. A GID under two callsigns = same physical radio used by both operators at different times,
  not a mislabel or collision. GID alone is not a reliable unique operator id — callsign + serial is.
- `parsing-requirements.md`: new section "GID, Callsign, and Serial Number — Identity Model"; P6 KNOT
  GID-attribution question marked **resolved** (same radio `PNE234200704` used by HOTLIPS and KNOT on
  different test days). The existing CL_B + gt_Sassy_B_Net `gid|source_filename` nodeMap fix confirmed
  still correct under this model.
- `CLAUDE.md`: new agent note on GID-as-radio-identity; P6 backlog row + P1–P7 summary updated;
  CL_B/gt_Sassy_B_Net collision note annotated.
- `session_summary.md` (this file): P6 backlog row + the two GID-conflict entries below updated from
  "pending/unresolved" to resolved.
- Verified by `docs-agent`: PR changes accurate, anchor links resolve, cross-docs consistent. No code
  change.
- Follow-up (PR #28): bumped the stale `_Last updated:_` footer in `parsing-requirements.md`
  (2026-06-12 → 2026-06-16). All three doc dates now consistent at 2026-06-16.

**2026-06-15 — P6 KNOT clock-skew investigation (log-analyst, docs only):**
- Analyzed `docs/diagnostic_KNOT_90296226464906_2026-06-04 16_42_33.829.log` (~12 MB, 18,959 lines).
  Despite the `diagnostic_` filename it is **ATAK format** (`atakVersion` present → `parser/atak.py`);
  the `diagnostic_` prefix is not a format indicator.
- **Finding: genuine host-clock skew, not delivery lag.** KNOT's own clock is monotonic/clean, but
  `deliveryTimeInMillis` (receive − send) is a **constant ≈ −7232 s (−2h 0m 32s)**, uniform across
  **all 50 senders** and **flat across hop counts**, non-drifting over 8.5 h. `storedMessages` never
  exceeds 3 → no buffering to cause lag. KNOT's Android host clock was ~2 h behind the mesh (smells
  like a timezone/NTP misconfig). KNOT's log alone can't say which side held correct time — needs a
  correlated peer log.
- **GID conflict surfaced (RESOLVED 2026-06-16):** GID `90296226464906` = KNOT here (serial
  `PNE234200704`), but the 2026-06-12 web-session entry below attributed it to HOTLIPS. The earlier
  buffer-saturation finding was pinned to "HOTLIPS GID 90296226464906" — that GID is KNOT, which shows
  no saturation. **Resolution:** not a mislabel or collision — GID reflects the radio paired at export
  time, not operator identity, so the same physical radio (`PNE234200704`) legitimately appears under
  both callsigns on different test days. Reliable identity = callsign + serial, not GID alone. See
  `parsing-requirements.md` → "GID, Callsign, and Serial Number — Identity Model".
- Verified the format + offset directly before recording (first received line carries
  `deliveryTimeInMillis: -7232006`; median delta −7232.0 s across 5,724 received messages).
- Docs updated: `parsing-requirements.md` P6 section + ATAK known-limitation note, CLAUDE.md backlog +
  P1–P7 summary, this summary. No code change — `atak.py` already captures negative deltas honestly.

**2026-06-12 — feat: ATAK epoch-ms time-window slider (`extractTimeRange`):**
- ATAK logs store time as epoch ms (`timestampInMillis` etc.), not a wall-clock string,
  so regular ATAK logs found no range and routed to `range-unavailable`, losing the slider.
- `ui/src/components/FileUpload.jsx`: `extractTimeRange` now returns epoch ms
  (`{ minMs, maxMs }`) and **unions** wall-clock `TS_RE` matches with a key-anchored
  13-digit `EPOCH_MS_RE` (`timestampInMillis`/`launchTimeInMillis`/`messageTimestampInMillis`).
  Duration keys (`deliveryTimeInMillis` 0/negative, `event.updateTimeInMillis`) are
  excluded by key-anchoring + the exactly-13-digit guard. Caller in `onDrop` uses
  `minMs`/`maxMs` directly (dropped the `normaliseTs` round-trip).
- **Purely client-side** — confirmed by log-analyst + parser-agent: the slider window is a
  browser-only filter in `App.jsx`, never sent to `/parse`; `atak.py` already parses these
  timestamps. No models/parser/`_result_to_dict`/API change.
- Verified in Node against fixtures: regular ATAK (`atak_sample.json`) now 15:20:00→15:20:30;
  enhanced unions epoch-ms + sdkError ISO; diagnostic unchanged; `fw_log` still range-unavailable.
- Tests: extended `tests/test_timewindow_trigger.py` (premise-pinned `EPOCH_MS_RE`, duration-key
  exclusion, 13-digit guard, ATAK fixtures now detectable). Docs updated (ui-requirements ✅,
  CLAUDE.md + this backlog flipped to Done).

**2026-06-12 — Log analysis (web session): HOTLIPS + MESMER storedMessages buffer saturation:**
- ⚠️ **GID label conflict (found 2026-06-15, RESOLVED 2026-06-16, see P6 entry above):** this entry
  attributes GID `90296226464906` to HOTLIPS, but the KNOT diagnostic log's own identity fields say
  that GID is **KNOT** (serial `PNE234200704`), with HOTLIPS appearing there as a separate originator
  (GID `90389599969003`). The buffer-saturation finding below was attributed to "HOTLIPS GID
  90296226464906" — but that GID is KNOT, and KNOT shows **no** buffer saturation (max 3).
  **Resolution:** the same physical radio (`PNE234200704`) was used by both operators on different
  test days — GID reflects the radio paired at export time, not a permanent operator identity, so this
  is neither a mislabel nor a collision. The reliable identity pair is callsign + serial, not GID
  alone. See `parsing-requirements.md` → "GID, Callsign, and Serial Number — Identity Model".
- Analyzed HOTLIPS (GID `90296226464906`) and MESMER (GID `90397332557396`) diagnostic
  logs from the **2026-06-04 test event**.
- Confirmed a `storedMessages` **buffer saturation** pattern on **both** devices: a
  **30-message hard ceiling** — the buffer fills while the device is CONNECTED, then PLI
  **bursts on drain**.
- **MESMER Episode 6**: buffer stuck at the ceiling for **2+ minutes while connected** — the
  strongest observed instance, candidate for a bug report.
- Both devices show an **anomalous second serial** at session start.
- Finding is **systemic, not device-specific**.
- Troubleshooting docs created (web session): `HotLips_Troubleshooting.md`, `MESMER_Troubleshooting.md`.
- **NACK 204/205 interpretation flagged as a DATA LIMITATION** — meaning of these codes is
  unconfirmed, pending a firmware error-code reference from the dev team.

**2026-06-12 — PRs #19, #21, #20 merged to main:**
- Merged in order #19 → #21 → #20 (merge commits `5cf4eb8`, `f5bfb32`, `e968068`); all three
  feature branches deleted. Full suite on merged `main`: **159 passed, 2 skipped**.
- On `main` now: canonical `DATA LIMITATION — ` (U+2014) prefix + conditional diagnostic-3.1.11
  and rsdk-GRIP emissions (#19), the CRLF parse-route fix + first API-path test (#21), and the
  quality-gate agent deduplication (#20).

**2026-06-12 — PR #20: quality-gate agent deduplication:**
- Refactored the 5 quality-gate agent definitions (`.claude/agents/`) so each overlapping
  responsibility has a single owner and the others defer: vera owns `parse_errors` DATA
  LIMITATION auditing + test-coverage depth; claude-md-compliance-checker owns the
  ParseResult chain; karen is the post-validation live-browser check only (no longer
  re-runs pytest or re-traces the chain); jenny owns spec alignment. jenny / TCV /
  code-quality-pragmatist dropped the checks they were duplicating.
- Branch `refactor-agent-deduplication`, kept **separate** from PR #19 (these were the
  5 long-pending uncommitted agent edits). Reviewer note in the PR: the `vera.md` edit
  also *removes* the JS-premise-via-pytest guidance (`test_timewindow_trigger.py` pattern)
  rather than relocating it — flagged for confirmation.

**2026-06-12 — PR #19 quality gate complete + a follow-up bug found:**
- All gate steps passed: claude-md-compliance-checker ✅, vera ✅ (after closing 2 coverage
  gaps — partial-count diagnostic + outgoing-only-GRIP rsdk), task-completion-validator ✅,
  karen ✅ (banner prefix strips cleanly at both UI sites, no leak), peer-reviewer ✅ (2 Low
  nits fixed: relay test tightened to em-dash assertion, inline-content rationale documented),
  jenny ✅ on parser scope — but found CLAUDE.md:299 ("a visible banner in the relevant UI tab"
  per limitation) overstates reality: only fw_log/relay_manager render a parse_errors banner;
  diagnostic 3.1.11 & atak sdkError reach `parse_errors` + the ⚠ glyph only (rsdk is shown via
  the HopsTab note). Pre-existing overstatement, not a #19 regression. Resolved by qualifying
  CLAUDE.md and backlogging a general diagnostic/rsdk/atak banner (see Backlog Status).
- **karen surfaced a separate, pre-existing bug** (NOT introduced by PR #19): `api/routes/parse.py`
  writes the uploaded text to a temp file in text mode, which on Windows double-translates
  CRLF (`\r\n` → `\r\r\n`); `Path.read_text()` universal-newline reading then turns that into
  `\n\n`, prematurely splitting diagnostic blocks → **0 received messages** for any CRLF
  diagnostic upload through the API. The unit test misses it because it calls the parser
  directly, bypassing the route. Decision: merge #19 on its (clean) scope, fix CRLF in a
  separate `fix(api)` PR with an **API-path** regression test. See Backlog Status.

**2026-06-12 — parse_errors DATA LIMITATION gaps (3 fixes + test set):**
- **Prefix normalization:** `atak.py` and `fw_log.py` (3 entries) now use the canonical
  `DATA LIMITATION — ` (em-dash U+2014) prefix, matching CLAUDE.md, the compliance
  checker, `docs-agent`, and `relay_manager.py`. All five parsers verified to emit
  the exact same literal. **UI coupling:** `App.jsx` line 1638 (general/ATAK
  limitations banner) stripped the old colon form `'DATA LIMITATION: '` — updated to
  the em-dash form so the prefix is still stripped from the banner display. (The
  relay banner at line 1881 already used em-dash.)
- **diagnostic.py:** emits a DATA LIMITATION when a Received Message block omits the
  originator callsign **and** GID (the known firmware-3.1.11 omission). Data-driven —
  fires only when it actually manifests, so logs that include the fields stay clean.
- **rsdk.py:** emits a DATA LIMITATION when no `GRIP_Receiver` incoming message-fields
  lines are present (hop count / RSSI unavailable for the session).
- **Tests:** new `tests/test_detect_format.py` (11 cases: per-format detection,
  filename signals, fw-log-first and relay-before-rsdk ordering, fallback). New
  fixture `diagnostic_3111_no_identity_sample.txt`. `test_rsdk.py` / `test_diagnostic.py`
  gained positive+negative limitation tests; `test_no_parse_errors` repointed where
  the new conditional limitation now legitimately fires. `test_atak.py` / `test_fw_log.py`
  tightened to assert the em-dash prefix. After the vera coverage audit, added two
  more cases + fixtures: rsdk **outgoing-only** GRIP (`rsdk_grip_outgoing_only.txt` —
  grip_messages populated but all outgoing, limitation must still fire) and diagnostic
  **partial** omission (`diagnostic_3111_partial_identity_sample.txt` — pins the
  "1 of 2 affected" count). **Full suite: 157 passed, 2 skipped.**
- Note: `parser-agent` and `vera` are read-only audit agents (no Edit/Write), so the
  edits + tests were implemented directly to their standard rather than by the agents.

**2026-06-10 — PRs #15–#17: agent governance docs in CLAUDE.md:**
- **PR #16** (`4065d3c`) — added a "Quality gate sequence" section listing the mandatory per-feature agent order plus the optional code-quality-pragmatist pass.
- **PR #17** (`a474f57`) — consolidated the whole agents area into one authoritative **Quality Gate Sequence** block: mandatory step table (with "What It Checks" / "Invoke With" columns), optional pass, an agent division-of-labor table, the available-agents roster, and the unique project-rule notes (LIFO, GID collision, P1–P7, etc.) preserved as a subsection. Removed the duplicate Available-agents table (PR #14) and the simpler quality-gate list (PR #16) — exactly one of each now remains.
- **PR #15** (`bcb40f3`) — session-summary housekeeping (recorded the #10–#14 verification chain).
- Note: 5 `.claude/agents/*.md` files have uncommitted working-tree edits (appeared outside the PR work) — deferred for a later commit.

**2026-06-10 — PRs #10–#14: verification follow-ups (jenny/karen/vera) on the two time-window fixes:**
- **PR #11** (`6d776e9`) — karen's end-to-end check found the `range-unavailable` step never fires for relay_manager (its `System.out` lines carry a year-bearing ISO timestamp the scanner parses). Corrected the trigger to **fw_log** (relative-ms, no wall clock) in `ui-requirements.md`, `session_summary.md`, and the user-facing banner copy in `FileUpload.jsx` (made format-neutral). jenny had passed it at the spec level; karen caught the false premise.
- **PR #12** (`0b2e6aa`) — added `tests/test_timewindow_trigger.py` (6 cases) pinning the trigger premise against real fixtures, since `extractTimeRange` had zero coverage (lean stack, no JS runner — tested via pytest premise). Also added `.claude/agents/vera.md` to version control (was untracked).
- **PR #13** (`0b8bf01`) — backlogged (High) that `extractTimeRange` doesn't detect ATAK epoch-ms timestamps (`timestampInMillis`), so ATAK logs also route to `range-unavailable` and lose the slider. Surfaced while writing the PR #12 tests.
- **PR #14** (`36892b2`) — documented the **vera** agent (unit test specialist) in both agent rosters; added a new "Available agents" table to `CLAUDE.md` (it had none before).
- **PR #10** (`7e95773`) — session-summary housekeeping (recorded PR #9 + corrected PR #8 entry).
- Net on the two fixes: **min-battery reduce (Fix 2) verified WORKS end-to-end**; **time-window disabled state (Fix 1) works but its trigger was mis-documented** — now corrected, tested, and the ATAK gap backlogged.

**2026-06-10 — PR #7: time-window disabled state — validation, ternary cleanup, docs reconcile:**
- Feature itself shipped in `7cc7bf8`: when `FileUpload.jsx` can't derive `globalMin`/`globalMax` (no parseable timestamps), the flow routes to a new `range-unavailable` step instead of silently skipping the time-window step — warning banner, disabled slider placeholder, **← Back**, and a working **Analyse →** that proceeds with the full log (`timeWindow = null`). Real trigger is **fw_log** (relative-ms timestamps, no wall-clock date); relay_manager was the originally-assumed trigger but its `System.out` lines carry a year-bearing ISO timestamp, so it routes to the working slider instead (corrected after karen end-to-end verification)
- task-completion-validator flagged the code as done but four doc locations still said "Pending — not started"; PR #7 closes that gap
- `fix(ui)` (`9c100d5`): collapsed a redundant modal-header ternary (both branches returned `'Select Time Window'`)
- `docs(session)` (`2f74692`): marked the item ✅ Done in `ui-requirements.md`, `session_summary.md`, and `CLAUDE.md` line 377 (line-377 hunk staged surgically so unrelated working-tree CLAUDE.md edits stayed out)
- `fix(ui)` (`d026110`): UI Lint failed CI (`--max-warnings 0`) on a `react-hooks/exhaustive-deps` warning — `7cc7bf8` moved the no-timestamps branch off `onFiles()`/`onClose()`, leaving `onDrop` with stale `[onFiles, onClose]` deps. Emptied the dep array (body only calls stable setters); verified lint clean locally
- Branch: `feat-time-window-disabled-step` → **PR #7 merged** (`31bc8a3`), branch deleted

**2026-06-10 — PR #9: mark min-battery windowed-reduce backlog item Done in CLAUDE.md:**
- CLAUDE.md backlog row still showed the single-sample ATAK min-battery coercion bug as ⏳ Pending though it was fixed in `040d40b`; synced it to ✅ Done with the IIFE pattern to match `session_summary.md` line 161
- Branch `fix-claudemd-min-battery-backlog` → **PR #9 merged** (`61bd561`), branch deleted

**2026-06-10 — PR #8: document the session-summary workflow in CLAUDE.md:**
- Added `session_summary.md` to the project-shape doc map, a new "Update the session summary" task under Common Tasks, and an agent-note reminder to update it after every task
- Branch `docs-session-summary-workflow` (`9a9005f`) → **PR #8 merged** (`8caf8f3`), branch deleted

**2026-06-10 — feat(ui): always show Relay Health and FW Log tabs:**
- Relay Health and FW Log tabs are now always visible in the tab bar
- When no relevant log is loaded: tab label is dimmed (opacity 45%, darker color, default cursor) and tab body shows a centered empty-state message
- Empty state messages: "No Relay Manager Logs Uploaded" / "No Firmware Logs Uploaded" with file type guidance
- New `EmptyTabState` component added to `App.jsx`
- Commit: `feat(ui): always show Relay Health and FW Log tabs, dim when no relevant log loaded`

**2026-06-10 — fix(ui): min battery single-sample reduce bug:**
- Fixed `Math.min(…, null)` coercion in `App.jsx` line 2247 (ATAK windowed recompute block)
- Old: `.reduce((a,b)=>Math.min(a,b), null)` — `Math.min(null, 80)` coerces null to 0, returns 0
- New: IIFE `(batPcts => batPcts.length ? Math.min(...batPcts) : null)(filtered)` — same pattern as non-ATAK branch on line 2266
- Commit: `fix(ui): min battery windowed reduce returns real value for single-sample ATAK sets`

**PR #6 — PLI/Battery overhaul** (previously most recent merged work):
- PLI tab overhauled — originator cards, gap inference for ATAK, interval color thresholds
- Battery chart moved to real wall-clock UTC x-axis with per-serial lines
- P5 battery critical threshold (< 10%) implemented
- Known bug documented: `Math.min(…, null)` in windowed min battery reduce for single-sample ATAK sets

**PR #4 — P1 MESMER BLE tag fix:**
- `ble_fail_count` now counts any `counts_by_tag` key containing `BLE` regardless of severity (fixes MESMER firmware 3.1.11 DEBUG-tagged BLE errors being missed)

**PR #3/FW Log work:**
- `parser/fw_log.py` implemented and merged
- FW Log tab (tab 13) implemented
- All 4 docs updated

---

## What to Work On Next

Based on the backlog, the most actionable items (not blocked):

0. **Run today's ATAK v3.0 changes through jenny/karen/vera** in Claude Code — done in the
   web chat interface this session, not yet through the usual quality-gate sequence

1. **P2: Protocol separation (BROADCAST/PRIVATE)** in TX/RX analysis — `messageProtocol` is already parsed, just needs UI lanes

2. **P3: Cross-device delivery matrix** — `logId` is already parsed across ATAK logs

3. **P4: Relay copy/retransmission flag** — flag file transfers with matching segment count but different logId

---

## How to Use This File

At the start of every new Claude session, paste the contents of this file (or upload it).  
At natural breakpoints, say: **"Update the session summary with what we just did"** and I'll revise the relevant sections.

Save this file in the repo at `docs/SESSION_SUMMARY.md` (gitignored or committed — your call).
