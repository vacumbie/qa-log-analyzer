# CLAUDE.md — goTenna QA Log Analyzer

## What this project is

A local analysis tool for parsing and visualizing goTenna mesh network log
files. QA engineers or other internal goTenna team members upload one or
more log files; the tool parses them, extracts structured data, and renders
it across a multi-tab analysis dashboard.

**Not a production web service for now.** Currently it runs locally on
Windows or Mac, has no authentication, no database, and no multi-user
concerns. Every design decision should optimize for the QA engineer or
other team members who need to load a log and get an answer quickly —
not for scale, elegance, or generality.

## Who maintains this

SDETs own and maintain this codebase, with assistance from developers as
needed. Most people opening a file here are adding a parser rule, fixing
a chart, or wiring up a new log format — not redesigning the architecture.
Write for *that* reader.

## Coding philosophy

- **Readability over cleverness** — Write Python and JSX that a mid-level
  developer can read and modify without reaching for documentation. If a
  clear `for` loop beats a clever list comprehension, use the loop. If a
  straightforward `if/elif` chain beats a dispatch dict, use the chain.

- **Explicit over implicit** — No auto-loading, no magic registration, no
  hidden side effects on import. If a parser runs, it should be obvious
  from reading `parse.py` where and why. If a chart renders, it should be
  obvious from `CHART_MAP` in `ChartPanel.jsx`.

- **Honest about gaps** — This tool parses real QA data with real
  limitations. Missing fields, undecoded payloads, and format ambiguities
  are surfaced in `parse_errors` and shown in the UI — never silently
  dropped or replaced with zeros. Data limitations are features, not bugs.

- **Reuse without over-abstraction** — When the same logic appears twice,
  extract it to a shared helper. But if extracting it forces callers to
  pass a wide options bag or learn a mini-DSL, leave the duplication. A
  short obvious copy beats a clever abstraction nobody can follow.

- **Comments explain *why*, not *what*** — The code should make *what*
  obvious. Comments are for non-obvious things: a parser quirk for a
  specific firmware version, a CSS workaround, a regex that handles a
  known log format inconsistency. Don't comment what a well-named function
  already says.

- **Tests are first-class code** — `tests/` follows the same rules as
  `parser/`. Fixtures live in `tests/fixtures/`, not inlined as strings.
  A test should read like a description of the scenario, not a wall of
  setup. The fixtures are the source of truth for expected parser behavior.

## When in doubt

Ask: *would the next QA engineer who opens this file understand it without
asking anyone?* If not, simplify.

---

## Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Parser | Python 3.10+ | Pure stdlib + dataclasses; no ML or heavy dependencies |
| API | FastAPI + Uvicorn | `cd api && uvicorn main:app --reload --port 8000` |
| UI | React 18 + Vite | `cd ui && npm run dev` → `http://localhost:5173` |
| Charts | Chart.js 4.4 + react-chartjs-2 | Line and Bar only; annotation plugin not installed |
| Maps | Leaflet 1.9.4 | **CDN only — not an npm dependency.** Loaded via `useLeaflet()` in `ui/src/hooks/useLeaflet.js`, shared by the Hop Count Map and the TAK position map |
| Tests | Pytest | `pytest tests/` from repo root with venv active |
| Fonts | Barlow Condensed, Rajdhani, Share Tech Mono | Loaded via Google Fonts `<link>` in `index.html` |

**Windows:** `.\venv\Scripts\activate` at repo root before any Python work.
**Mac/Linux:** `source venv/bin/activate` at repo root before any Python work.
**Do not add npm packages** unless Chart.js 4.4, React 18, or plain CSS
genuinely cannot do the job. The stack is intentionally lean.

---

## Project shape (quick map)

```
qa-log-analyzer/
├── parser/
│   ├── models.py           # Single source of truth for all dataclasses
│   ├── diagnostic.py       # goTenna Pro+ block-format logs
│   ├── rsdk.py             # iOS/Android SDK line-per-event logs
│   ├── atak.py             # Android ATAK plug-in logs
│   ├── tak.py              # TAK server CoT event stream (server-side)
│   └── relay_manager.py    # Android logcat from com.gotenna.relaymanager
├── api/
│   ├── main.py             # FastAPI app entry point + CORS config
│   └── routes/
│       ├── parse.py        # POST /parse — detect format, run parser, serialize
│       └── export.py       # GET  /export/{id} — download CSV or JSON
├── ui/src/
│   ├── App.jsx             # Tabs, KPI row, time window filter, all tab components
│   ├── components/
│   │   ├── ChartPanel.jsx  # All Chart.js chart components + CHART_MAP registry
│   │   ├── FileUpload.jsx  # Upload modal — uses createPortal (see architecture)
│   │   ├── TakTab.jsx      # TAK Server tab — Leaflet map (chart via CHART_MAP)
│   │   ├── DeviceSummary.jsx
│   │   └── DataPointSelector.jsx
│   └── hooks/
│       └── useLogData.js
├── tests/
│   ├── fixtures/           # Sample log snippets — one per format
│   └── test_*.py
└── docs/
    ├── parsing-requirements.md   # Parser rules, field sources, known limitations
    ├── log-field-definitions.md  # Every log field: raw → parsed → model field
    ├── ui-requirements.md        # Tab specs, KPI cards, backlog items
    └── session_summary.md        # Running session log — context bridge between sessions
```

Look in `docs/` first when adding anything non-trivial. The specs there
are the intended source of truth — keep them in sync with the code.

---

## Supported log formats

Six formats, auto-detected by `_detect_format()` in `api/routes/parse.py`.
**Detection order matters** — fw_log runs first because its bracket pattern
`[digits-digits, MODULE, LEVEL]` is highly distinctive and cannot match any of
the others. `tak` must precede `atak`: both are JSON, but their field sets are
disjoint (`receivedAt`/`nodeType`/`category` vs
`logId`/`connectionState`/`atakVersion`). That disjointness covers the *content*
check only — the `tak` **filename** hints are substring tests, and `tak_server`
matches the legacy ATAK convention whenever the callsign starts with `SERVER`
(`diagnostic_ATAK_SERVER_…` → misrouted, every record dropped as missing `time`,
reported as an empty stream). The hints are guarded by `_is_atak_content()`,
shared with the ATAK branch; the guard is a negative test, not a positive
`is_tak_log()` requirement, so a genuine empty export (`[]`) still routes to
`tak`. relay_manager must precede rsdk
because both contain `AndroidBleRadio` lines; relay_manager has additional
markers that distinguish it. `diagnostic` is always the catch-all fallback.

| Priority | Key | Parser | Source |
|----------|-----|--------|--------|
| 1 | `fw_log` | `parser/fw_log.py` | goTenna relay radio firmware (UART/USB debug) |
| 2 | `tak` | `parser/tak.py` | TAK server CoT event stream (JSON export) |
| 3 | `atak` | `parser/atak.py` | Android ATAK plug-in |
| 4 | `relay_manager` | `parser/relay_manager.py` | Android logcat, `com.gotenna.relaymanager` |
| 5 | `rsdk` | `parser/rsdk.py` | iOS/Android SDK logs |
| 6 | `diagnostic` | `parser/diagnostic.py` | goTenna Pro+ app export (fallback) |

`tak` is the only **server-side** source — the server's view of many clients,
not a device describing itself. It carries no radio identity (no serial, GID or
firmware version) and no RF data (no RSSI or hop count), so it is excluded from
the Health Score and contributes nothing to the device KPI row.

Every parser returns a `ParseResult` from `parser/models.py`. The API and
UI only depend on that shape — never import parser internals into routes or
UI components.

---

## Architecture decisions worth knowing

### ParseResult is the only contract between parser and API
Every parser returns `ParseResult`. `_result_to_dict()` in `parse.py`
handles all serialization. The order is always: add to `models.py` →
populate in the parser → serialize in `_result_to_dict()` → use in the UI.
Skipping any step produces silent failures.

### Chart registration in ChartPanel.jsx
All charts are self-contained components in `ChartPanel.jsx`. To add one:
write a component accepting `{ results }`, register it in `CHART_MAP` at
the bottom of the file, then reference it from the relevant tab in
`App.jsx` via `<ChartPanel results={results} selectedPoints={['key']} />`.
A key in `App.jsx` that doesn't exist in `CHART_MAP` silently renders
nothing — keep them in sync.

### FileUpload uses createPortal
The upload modal renders via `createPortal(…, document.body)` to escape
the header element's CSS stacking context. The header uses
`backdropFilter: blur(12px)`, which creates a new stacking context that
traps `position: fixed` children regardless of z-index. Do not move the
modal rendering back inside the header.

### Time series charts use a normalized 0–100% x-axis
`buildRelativeTimeSeries()` and `buildGripRssiSeries()` in `ChartPanel.jsx`
map each device's session to 0–100% independently. This prevents
sparse-data problems when sessions of different lengths are loaded together
— a 10-minute log and a 7-hour log both render fully across the chart
width. Do not switch to absolute timestamps without thinking through this.

### Temperature is always Fahrenheit in the UI
Log files record temperatures in Celsius. `_result_to_dict()` converts to
°F (fields: `pa_temp_f`, `system_temp_f`). The conversion happens once, in
the API layer. Never convert in a parser or in a UI component.

### RSDK hop count — only from GRIP_Receiver
The old `SendMessageResponse` hop count was an SDK sequence counter, not
RF data, and is excluded. Genuine hop counts come only from `GRIP_Receiver`
incoming message fields lines — `grip_messages` where
`direction === "incoming"` and `hops != null`.

### Relay Manager — stage confirmed, prod unknown
Stage logs are identified by `na.relaymanager(<pid>)` in io_stats lines.
Prod logs have not been analyzed. Do not assume prod behavior matches stage,
and do not remove the "unknown" environment path.

### Health Score — device-format-scoped, BLE from ERROR|BLE
The Health tab scores only device-format logs via the `HEALTH_FORMATS`
allow-list (`atak`, `diagnostic`, `rsdk`) in `App.jsx`. `relay_manager` is
excluded because its summary carries none of the five dimension inputs — an
unscoped relay card would default-pass everything and show a misleading 5/5.
When only relay logs are loaded, the tab shows a "no device logs" note.
The BLE dimension's `ble_fail_count` is derived in `_result_to_dict()`: for
ATAK it sums the `ERROR|BLE` subset of `counts_by_tag`, falling back to the
`deviceDisconnected` count **only when no SDK 2.0 summary exists** (a summary
with zero `ERROR|BLE` is a real `0`); diagnostic/rsdk use `len(ble_fail_events)`.
A dimension with no data for a format is **N/A** — excluded from the score
denominator, never a free pass (`pass: null` in `App.jsx`). RSSI is the main
case: `avg_rssi` comes from ATAK received-message RSSI and rsdk GRIP incoming
RSSI, but is `None` for diagnostic, so diagnostic cards score `/4`.
All Health Score thresholds are unvalidated initial estimates — see the
threshold-validation backlog in `docs/ui-requirements.md`.

### A scoped count must state its scope
If a KPI counts a subset, its label says which subset. The TAK `No GPS Fix` card
counts PLI/Marker events only — the categories expected to carry a position —
so its sub-label reads `PLI/Marker only`, **not** "excluded from map", which
also includes Chat and server-control events that never had a position to lose.
Where a chart excludes rows for more than one reason, name the reasons
separately so the arithmetic reconciles on screen (`86 of 91 plotted ·
excluded: 1 PLI/Marker with no GPS fix, 4 Chat/server-control`). A scoped count
also renders at zero — `0` doesn't mean everything is included.

Corollary: **don't re-derive a parser definition in the UI.** `has_gps_fix` is
already `not (lat == 0 and lon == 0)`; a UI-side `lat !== 0 && lon !== 0` would
reject a genuine position on the equator or prime meridian and make the two
counts disagree again.

### An empty map must say it's empty
A Leaflet container that never gets `fitBounds`/`setView` loads no tiles and
paints as a blank near-white box on the dark dashboard. Keep the container
mounted — unmounting leaves the creation effect (deps `[]`) with no ref when
data returns — but hide it with `display: none` and render a message in its
place, as `TakPositionMap` does. Same rule the latency chart already followed.

---

## Common tasks

### Add a new log format
1. Create `parser/<format>.py` returning `ParseResult`
2. Add new dataclasses to `parser/models.py` — under a `# <Format> only` comment
3. Add detection to `_detect_format()` in `api/routes/parse.py` — before
   the diagnostic fallback; after relay_manager if it shares AndroidBleRadio
4. Add a routing branch in the `if fmt ==` block in `POST /parse`
5. Add serialization in `_result_to_dict()` — format block + summary block
6. Add a tab in `App.jsx` — `TABS` entry with `*Only` flag, `visibleTabs`
   filter update, `case` in `TabContent`
7. Add tests with a fixture in `tests/fixtures/`
8. Update all docs in `docs/`
9. Add a `_CSV_TYPES` entry in `api/routes/export.py` listing the flat
   per-row tables to expose — or, if the format's data is nested
   summary/health structure, document it as JSON-only in that file (as
   `relay_manager` and `fw_log` are)

### Add a new chart
1. Write a component in `ChartPanel.jsx` — follow `TempOverTime` or
   `GripRssiOverTime` as a reference depending on whether it's a simple
   time series or needs custom data preparation
2. Register in `CHART_MAP`
3. Reference from the tab via `<ChartPanel selectedPoints={['key']} />`

### Add a new ParseResult field
`models.py` → parser → `_result_to_dict()` in `parse.py` → UI. In that order.

### Update the session summary
After completing any task — adding a parser, fixing a bug, implementing a tab,
updating docs — update `docs/session_summary.md`:

1. Read the current `docs/session_summary.md`
2. Under **Most Recent Work**, replace or append with what was just built/decided
3. Update any **Backlog** items whose status changed (✅ Done, Blocked, etc.)
4. Add any new **Known Data Limitations** that were surfaced
5. Update **What to Work On Next** if priorities shifted
6. Commit alongside the code: `docs(session): update session summary`

This file is the primary context bridge between sessions. Keep it accurate —
a stale summary is worse than no summary.

### Run tests
```bash
pytest tests/          # full suite
pytest tests/test_rsdk.py -v   # single file, verbose
pytest tests/ -x       # stop on first failure
```

### Start the dev environment
```bash
# Terminal 1 — API

# Windows (PowerShell)
cd C:\Users\Valerie.Cumbie\Documents\qa-log-analyzer
.\venv\Scripts\activate
cd api
uvicorn main:app --reload --port 8000

# Mac/Linux
cd ~/Documents/qa-log-analyzer
source venv/bin/activate
cd api
uvicorn main:app --reload --port 8000

# Terminal 2 — UI (both platforms)
cd <repo-root>/ui
npm run dev
```

### Verifying UI changes in a browser (this machine)

When driving the running UI with Playwright (e.g. to verify a tab renders),
launch **system Edge**, not bundled Chromium:

```js
const browser = await chromium.launch({ channel: 'msedge' })
```

On this machine `npx playwright install chromium` reports success (exit 0,
100% download) but does not populate `…\ms-playwright\chromium-<rev>\chrome-win\`,
so `chromium.launch()` fails with "Executable doesn't exist". Edge ships with
Windows 11 and `channel: 'msedge'` drives it directly with no download. Keep
Playwright itself out of `ui/` — install it in a temp dir so it doesn't touch
the lean stack (see "Do not add npm packages").

---

## Known data limitations

Surface these honestly — never paper over them with zeros or missing fields.
Most active limitations have a `DATA LIMITATION` entry in `parse_errors` — but not
all of them, and the exceptions are deliberate. A `parse_errors` entry means *data
is missing or undecodable*. Two kinds of row below are **not** that, and correctly
have no entry: **interpretive caveats**, where the data is parsed in full and the
caution is about how to read it (the frequency/mode raw-command rows — nothing is
lost, and an entry would fire on every enhanced log and dilute the real ones), and
**transparently handled format quirks**, where the parser absorbs the oddity without
loss (the `--- RSDK LOGS ---` divider). For those, the honesty burden sits in the UI
copy and the model docstrings instead. How a real entry reaches the UI varies by
format today: `fw_log`, `relay_manager` and `tak` render
the full text in a dedicated banner (`FwLogTab` and `RelayHealthTab` in
`App.jsx`, `LimitationBanner` in `TakTab.jsx`); the `rsdk` GRIP hop/RSSI gap is surfaced as a `HopsTab` note; the
`diagnostic` 3.1.11 and `atak` `sdkError` entries currently reach `parse_errors`
(and the file-list ⚠ glyph) but have no dedicated tab banner. A general
diagnostic/rsdk/atak limitations banner is backlogged — see the Backlog section below.

The parser is still learning. `log-field-definitions.md` is a living
document — it grows as new log samples are introduced to the project and
as previously unknown fields or behaviors are observed. When a new log
file reveals something the parser doesn't handle yet, the right response
is to document it in `log-field-definitions.md` and `parsing-requirements.md`
first, then update the parser. Unknown fields are an expected part of this
project's lifecycle, not a sign something is broken.

| Format | Limitation |
|--------|-----------|
| `relay_manager` | BLE payloads captured but not decoded — relay health attributes (SNR, battery %, temp °F, uptime, firmware version) are raw hex bytes pending BLE protocol implementation |
| `relay_manager` | Single relay node per observed session — multi-node behavior unknown |
| `relay_manager` | Prod logs not analyzed — stage/prod behavioral differences unknown |
| `rsdk` | GRIP hop count and RSSI only available when `GRIP_Receiver` incoming fields lines are present |
| `diagnostic` | Firmware 3.1.11 omits callsign and GID from Received Message blocks |
| `atak` | `originatorCallsign`/`originatorUUID`/`receiverCallsign` always empty in observed samples — identity for those is GID-only. `senderCallsign` IS populated starting with ATAK plugin v3.0 (was always empty in earlier plugin versions/samples) — see `docs/atak_v3_early_integration_notes.md` |
| `atak` | ATAK plugin v3.0 filenames drop the `ATAK_` segment (`diagnostic_<CALLSIGN>_<GID>_<DATE>_<TIME>.log`); the filename regex accepts both conventions, and `device.callsign` falls back to `senderCallsign` on the device's own sent message when the filename doesn't match either |
| `atak` | Some early ATAK v3.0 builds emit zero `connectionState` (device-health) records for a session — no battery %, thermal, firmware version, or radio-health data available. Flagged via `DATA LIMITATION —` in `parse_errors`, fires only when a log actually has zero health records |
| `atak` | `sdkError` (SDK Logging 2.0) total volume baseline unknown — `sdk_error_count` is aggregated and informational, not a pass/fail signal. Exception: the `ERROR\|BLE` subset of `counts_by_tag` (falling back to `deviceDisconnected` event count) feeds the BLE Health Score dimension as `ble_fail_count`; its `> 0 = fail` threshold is an initial estimate pending field validation, like the other Health Score thresholds |
| `atak` | Frequency SET attempts and NetworkMode/TetherMode polls (`atak_frequency_set_attempts`, `atak_radio_mode_queries`) are the raw radio-command layer, not confirmed state — a `FAILED` or `QUEUED` attempt/poll should never be treated as a confirmed change. Confirmed frequency changes come from the `frequencyUpdated` event; confirmed radio mode comes from the Device Health record's own `mode` field. Status vocabulary is an open set (`QUEUED`/`COMPLETED`/`FAILED`/`CANCELLED`/`TIMEOUT` observed so far) — don't assume it's exhaustive, and never render it through a hardcoded allow-list. A `COMPLETED` SET is **not** confirmation either: it is a command-layer ack, so the UI deliberately does not promote it into the confirmed-frequency timeline (decided 2026-08-04 — see `docs/parsing-requirements.md` → "Radio Command Layer vs Confirmed State"). Consequence: enhanced logs, which emit no `frequencyUpdated`, honestly show "confirmed frequency unknown" plus attempt counts |
| `atak` | Some field logs append a second, unwrapped section after the main JSON array closes (a `--- RSDK LOGS ---` divider followed by more bare `sdkError` records, same shape as the rest). Handled transparently — the divider line and the mid-file array-close artifact are skipped, not logged as parse errors — but worth knowing the file isn't strictly valid JSON as a whole |
| `atak` | `numberOfOpenSegments = -99` is a sentinel (transfer cancelled before count known) — stored as null, never -99 |
| `atak` | Receiver-side `deliveryTimeInMillis = 0` on fileTransfer is a placeholder — only meaningful when `isSender=true` and status `SUCCESS` |
| `atak` | Device Health `serialNumber = "Unknown"` is expected during BLE reconnection, not a parser error |
| `fw_log` | Timestamps are relative ms from boot, not wall clock UTC — a session cannot be pinned to absolute time without a reference point from a correlated Relay Manager log |
| `fw_log` | Device serial number and firmware version live in the binary RHC response payload — not plaintext. Identity is shown as the origin hash only |
| `fw_log` | Battery stabilization errors are a known firmware quirk (the routine fires even when the battery is already stable), counted separately from real errors — not indicative of hardware failure, pending field validation |
| `fw_log` | `RSSI[]` detailed samples are DEBUG-level and skipped, so `rssi_samples`/`rssi_summary` are always empty; channel energy (`energy_samples`) is the RSSI proxy surfaced in the UI |
| `tak` | **Server-side viewpoint — no radio identity or RF data.** No serial, GID, firmware version, battery, thermal, RSSI or hop count; identity is callsign + CoT `uid`. Excluded from the Health Score for the same reason as `relay_manager`, and contributes nothing to the device KPI row |
| `tak` | `lat`/`lon` of exactly `(0,0)` is the CoT no-GPS-fix sentinel (paired with a `999999.0`-family `hae`/`ce`/`le`), not a real position — flagged `has_gps_fix=False`, never plotted. The parser owns this definition; see "A scoped count must state its scope" for why the UI must not re-derive it |
| `tak` | Negative `latency_ms` (`receivedAt` before `time`) is real data, not an error — the source device's clock is ahead of the server. Preserved, never clamped, and shown red in the latency chart with that caption. 10 of 91 events in the first sample (min `−93 ms`). Server-side counterpart to P6, tracked as **P8** in `docs/parsing-requirements.md` |
| `tak` | GeoChat (`b-t-f`) message bodies are not extracted — only the envelope (sender callsign, timestamps); the `<remarks>` text stays in `raw_cot`. Also unextracted from the raw XML: `<status battery>`, `<takv>` device/OS strings, `<track>` speed/course. These are **two separate `DATA LIMITATION —` entries**: the Chat one fires only when Chat records are present, the telemetry one only for the elements a given stream actually carries (with per-element counts). Both note that `raw_cot` itself is not serialized, so none of it is reachable from the UI or an export |
| `tak` | Two different "no GPS fix" counts exist: `summary.no_fix_count` is PLI/Marker-scoped (1 in the sample) while the `parse_errors` sentence counts all categories ("5 event(s)"). Both are correct for what they measure, but the error wording reads as 5 devices losing GPS when 1 did — the UI resolved this conflation, **the parser text has not**. Open fix |
| `tak` | `parentCallsign` always null in observed samples, and `platform` is often absent (18 of 91, including all Chat records) even when `nodeType` is known — stored as `None`, never guessed |
| `tak` | Single-stream validation — one real sample plus three hand-built fixtures (edge cases, clean PLI-only, zero-coordinate positions). Multi-server, multi-day and larger streams unobserved. The `lat == 0`/`lon == 0` sentinel rule **is** covered: `tak_stream_zero_coordinate_positions.json` exercises a real prime-meridian position, a real equator position, and the `(0,0)` sentinel — but no *observed* sample has ever contained one, so the fixture is hand-built, not field-confirmed |

---

## UI design tokens

```js
const C = {
  accent: '#00d4ff',  // cyan — primary highlight
  green:  '#00e5a0',
  yellow: '#ffd166',
  red:    '#ff4757',
  muted:  '#4a6080',
  dim:    '#2a3a52',
}
const PALETTE = ['#00d4ff','#ff6b35','#ffd166','#c77dff','#00e5a0','#ff4757','#4a90e2','#ff6b9d']
```

Backgrounds: `#060d16` page · `#080e18` panel · `#0f1923` card.
Borders: `#1e293b` standard · `#1e3a4a` accent.
Mono font: `'Share Tech Mono'` via `var(--mono)`.
Display font: `'Barlow Condensed'`.

---

## Backlog

The canonical backlog lives in `docs/ui-requirements.md`. Summary:

| Item | Status |
|------|--------|
| Time Window Filtering | ✅ Done |
| GRIP RSSI Line Graph Over Time | ✅ Done |
| ATAK Enhanced Log (SDK Logging 2.0) | ✅ Done |
| FW Log — relay firmware parser & tab | ✅ Done |
| FW Log — RHC payload decoding (hash→serial, firmware version) | Blocked — waiting on mapping tables from QA |
| Session Persistence | Deferred |
| Relay Manager prod log support | Blocked — waiting on prod samples |
| BLE payload decoding (relay health attributes) | Blocked — waiting on protocol spec |
| Relay Manager JSON log format (SDK Logging 2.0) | Pending — format in design |
| Health Score threshold validation (BLE, thermal, battery, queue, RSSI) | Pending — blocked on field data; dimensions wired, thresholds are initial estimates |
| P1: MESMER BLE tag profile (DEBUG vs ERROR) | ✅ Done — any tag containing BLE counts regardless of severity |
| P2: Protocol separation (BROADCAST/PRIVATE) in TX/RX, file transfer, congestion | ⏳ Pending |
| P3: Cross-device delivery matrix using logId | ⏳ Pending |
| P4: Relay copy/retransmission flag | ⏳ Pending |
| P5: Battery critical threshold < 10% | ✅ Done — 🔴 ⚠ CRITICAL in Health Score |
| P6: KNOT clock skew investigation | ⏳ Investigated 2026-06-15 — confirmed constant ≈ −2h host-clock skew (uniform across all 50 senders, hop-independent, no buffer lag); not delivery lag. **Two open QA questions blocking closure** (which clock was correct; tz/NTP-vs-manually-wrong root cause). GID `90296226464906` KNOT-vs-HOTLIPS conflict **resolved** (2026-06-16) — same physical radio used by both operators on different test days, not a mislabel. See `docs/parsing-requirements.md` P6 |
| P7: Poseidon log format | ⏳ Deferred |
| PLI tab ATAK support + gap inference | ✅ Done — all 14 devices shown |
| Battery chart real UTC timestamps + per-serial lines | ✅ Done |
| PLI Settings section (pliSettingUpdated) | ✅ Done |
| GID collision fix (CL_B + gt_Sassy_B_Net) | ✅ Done — nodeMap key = gid+filename |
| Time-window step disabled state for unparseable timestamps | ✅ Done — `range-unavailable` step in FileUpload.jsx replaces the silent skip |
| Min battery windowed reduce returns 0 for single-sample sets (ATAK branch) | ✅ Done — IIFE pattern: `(batPcts => batPcts.length ? Math.min(...batPcts) : null)(filtered)` |
| `extractTimeRange` doesn't detect ATAK epoch-ms timestamps (`timestampInMillis`) — ATAK logs route to `range-unavailable`, lose the slider | ✅ Done — `extractTimeRange` returns epoch ms and unions wall-clock `TS_RE` with a key-anchored 13-digit `EPOCH_MS_RE` (`timestampInMillis`/`launchTimeInMillis`/`messageTimestampInMillis`); duration keys excluded; client-side only |
| DATA LIMITATION prefix normalization (em-dash) across all parsers | ✅ Done (PR #19) — canonical `DATA LIMITATION — ` (U+2014) in atak/fw_log/diagnostic/rsdk/relay_manager; `App.jsx` FW Log banner strip site updated to match (relay banner was already em-dash). `tak.py` was added later (PR #35) and conforms — all six parsers verified U+2014 |
| General DATA LIMITATION banner for diagnostic/rsdk/atak tabs | ⏳ Pending — diagnostic 3.1.11 & atak sdkError `parse_errors` entries reach the API + file-list ⚠ glyph but have no dedicated tab banner (rsdk is shown via the HopsTab note); CLAUDE.md "Known data limitations" qualified accordingly |
| diagnostic 3.1.11 `parse_errors` emission (originator callsign + GID omitted) | ✅ Done (PR #19) — data-driven, fires only when a Received Message block omits both; reports "{n} of {total}" affected |
| rsdk GRIP-availability `parse_errors` emission (no `GRIP_Receiver` incoming fields) | ✅ Done (PR #19) — hop count / RSSI unavailability surfaced honestly when no incoming GRIP fields lines are present |
| Rename "Relay Firmware" / "Relay radio firmware" to "Firmware" throughout codebase and docs | ⏳ Pending — cosmetic/naming only; do not change variable names, function names, or key strings (fw_log stays fw_log) |
| ATAK radio-command layer (Frequency SET attempts, NetworkMode/TetherMode queries, `relayModeUpdated`) + Modes tab | ✅ Built 2026-08-04 — uncommitted; see `docs/session_summary.md` |
| New ATAK command/query arrays not covered by the time-window filter | ✅ Done (2026-08-04) — `atak_frequency_set_attempts`, `atak_radio_mode_queries`, `atak_events` added to `filteredResults` |
| `current` frequency badge misattributed to the last *new* config instead of the chronologically last change | ✅ Done (2026-08-04) — `lastKey` now derived from `confirmedChanges`, not `segments` insertion order |
| ATAK `action` GET/SET conflation | ✅ Done (2026-08-04) — both actions are still stored (dropping GETs would lose real observations); the UI splits on `action` so SET attempts, GET queries, mode polls, and mode change cmds are counted and labelled separately. Verified against the real MESMER log: 28 Frequency cmds = 16 SET + 12 GET; 2,028 mode records = 2,016 polls + 12 change cmds |
| Rename `AtakFrequencySetAttempt`/`AtakRadioModeQuery` (they hold both actions) | ⏳ Deferred — ~69 references incl. the two serialized keys, tests, and docs; pure churn for no behavior change. Docstrings state what the fields actually hold |
| `_CSV_TYPES` entry or JSON-only note for the two new ATAK tables | ⏳ Pending — decision not yet recorded in `api/routes/export.py` |
| TAK server CoT stream — parser + TAK Server tab | ✅ Built 2026-08-24 (PR #35, open) — `karen` passed; the other 5 gate agents have not run |
| TAK — Leaflet loaded from npm (`TakTab.jsx`) vs unpkg CDN (Hop Count Map) | ✅ Done — resolved as **CDN only**. `leaflet` removed from `package.json`/`package-lock.json`; both maps now use the shared `useLeaflet()` hook, so the library is fetched once per page instead of bundled *and* fetched |
| TAK — `parse_errors` no-fix wording counts all categories while `summary.no_fix_count` is PLI/Marker-scoped | ⏳ Pending — same conflation the UI already fixed |
| TAK — `summary.min_latency_ms` serialized and time-windowed but never rendered | ✅ Done — rendered as a Min Latency KPI. `TakTab` now *reads* `avg`/`max`/`min_latency_ms` and `unique_callsigns` from the summary instead of recomputing them, which also removed an API-vs-UI rounding disagreement (1 dp vs integer) |
| TAK — no format-specific KPI row on Overview | ✅ Done — `TakKpiRow` in `App.jsx`, mirroring `RelayKpiRow`. A TAK-only session no longer falls through to the device row and its `APP VERSION: 0 versions` |
| TAK — `_CSV_TYPES` entry or JSON-only note for `tak_events` | ✅ Done — `"tak": {"tak_events"}` in `api/routes/export.py`; it's a flat per-row table, so an entry rather than a JSON-only note. The two ATAK command tables are still undecided |
| TAK — `TakLatencyChart` defined outside `ChartPanel.jsx`/`CHART_MAP` | ✅ Done — moved to `ChartPanel.jsx` as `tak_latency`; `TakTab` renders it via `<ChartPanel selectedPoints={['tak_latency']} />`. `ChartPanel.jsx` is again the only file importing `react-chartjs-2` |
| TAK — `<status battery>`/`<takv>`/`<track>` documented as surfaced via `DATA LIMITATION` but no entry existed | ✅ Done — `parse_tak_log` now emits a second entry naming only the elements a given stream actually carries, with per-element counts |
| P8: TAK server receipt latency / clock skew | ⏳ Open — defined 2026-08-24 in `docs/parsing-requirements.md` so the `parser/tak.py` and `models.py` references resolve |
| `extractTimeRange` matches `stale=` inside embedded CoT XML — 18-min session reads as a 25-hour slider range | ⏳ Pending — pre-existing scanner behavior, newly reachable via TAK; slider can't narrow within the data |
| TAK map legend lists unplotted callsigns; `PALETTE` collides past 10 callsigns | ⏳ Pending — cosmetic; `colorByCallsign` iterates all events rather than plotted ones |

---

## Quality Gate Sequence

Every feature or fix must pass through the following agents before merge.
Run them in order — each agent assumes the previous one has already passed.

### Mandatory (every feature)

| Step | Agent | What It Checks | Invoke With |
|------|-------|---------------|-------------|
| 1 | `vera` | Test coverage depth, fixture realism, sentinel value handling, `DATA LIMITATION` entries in `parse_errors` | `run vera to audit coverage for <feature>` |
| 2 | `task-completion-validator` | End-to-end completion checklist — ParseResult chain, pytest clean, docs updated | `run task-completion-validator to verify <feature>` |
| 3 | `jenny` | Spec compliance — does the implementation match `docs/` and `CLAUDE.md`? | `run jenny to verify <feature> against the docs` |
| 4 | `karen` | Live browser verification — real log, real data, no dashes or NoData | `run karen to verify <feature> in the UI` |
| 5 | `peer-reviewer` | Pre-merge code review — diff reviewed, helpers read, no invented findings | `run peer-reviewer` |
| 6 | `claude-md-compliance-checker` | CLAUDE.md rules — ParseResult chain, detection order, temperature conversion, commit format | `run claude-md-compliance-checker` |

### Optional (invoke when complexity is suspected)

| Agent | When to Use | Invoke With |
|-------|------------|-------------|
| `code-quality-pragmatist` | After implementing — if the solution feels over-engineered, abstractions feel wide, or a helper grew an options bag | `run code-quality-pragmatist to review <feature or file>` |

`code-quality-pragmatist` is **not a routine checkbox**. It enforces the
"readability over cleverness" and "reuse without over-abstraction" rules
already in this file. Run it when something feels wrong, not after every
small fix. The other agents will recommend it if they spot complexity during
their own checks.

### Agent division of labor (avoid duplicate effort)

These responsibilities are owned by one agent — others defer rather than
re-check:

| Responsibility | Owner | Others defer to |
|---------------|-------|-----------------|
| `parse_errors` DATA LIMITATION coverage | `vera` | task-completion-validator, jenny |
| ParseResult chain enforcement | `claude-md-compliance-checker` | code-quality-pragmatist |
| Live browser verification | `karen` | task-completion-validator |
| Spec alignment | `jenny` | karen |
| Test coverage depth | `vera` | task-completion-validator |

### Available agents (in `.claude/agents/`)

| Agent | Purpose | Mandatory / Optional |
|-------|---------|---------------------|
| `vera` | Unit test specialist — writes tests, audits coverage, ensures fixtures are realistic; owns DATA LIMITATION auditing | Mandatory |
| `task-completion-validator` | End-to-end completion checklist | Mandatory |
| `jenny` | Spec compliance auditor — implementation vs docs | Mandatory |
| `karen` | Live browser verification only — assumes validator already ran | Mandatory |
| `peer-reviewer` | Pre-merge code review | Mandatory |
| `claude-md-compliance-checker` | CLAUDE.md rules enforcement; owns ParseResult chain check | Mandatory |
| `code-quality-pragmatist` | Simplicity and readability check | Optional |
| `parser-agent` | Full parser chain specialist | Use when adding/modifying any parser |
| `log-analyst` | Raw log analysis before parser is written | Use when new log format arrives |
| `docs-agent` | Keeps all 4 docs in sync with code | Use after any significant change |

### Agent-specific notes

- **Fetch current file state before editing.** Do not assume a file matches
  a previous session's output — the repo may have changed.
- **Update `docs/session_summary.md` after every task.** This is the context
  bridge between sessions — for both Claude Code agents and claude.ai chat.
  Read it at the start of any non-trivial task; update it when the task is done.
  Commit it alongside the code change: `docs(session): update session summary`.
  See "Update the session summary" under Common Tasks for the update checklist.
- **deviceDisconnected LIFO assumption:** Serial is omitted on disconnect events. Attribution uses LIFO (most recent connect = first to disconnect). Documented in `docs/parsing-requirements.md`. Pending dev team confirmation.
- **GID is radio identity, not operator identity:** The GID in a diagnostic/ATAK log reflects the radio paired at the time of export — not a permanent operator identity. The **callsign** identifies the operator/app instance; the **serial number** identifies the physical radio hardware. A GID appearing under two different callsigns means the same physical radio was used by both operators at different times — not a mislabel or collision. GID alone is not a reliable unique identifier; callsign + serial together are the reliable identity pair. See `docs/parsing-requirements.md` → "GID, Callsign, and Serial Number — Identity Model".
- **GID collision (CL_B + gt_Sassy_B_Net):** Share GID `90194071247761` and serial `PNE233200347`. PLI `nodeMap` uses `gid|source_filename` as key — this remains correct under the identity model above. Dev team notified.
- **Check `docs/` before adding anything non-trivial.** The specs there
  describe intended behavior. If the code disagrees with the docs, flag it.
- **One commit per logical change.** Format: `type(scope): description` —
  e.g. `feat(parser): add relay_manager` or `fix(ui): modal z-index via createPortal`.
- **Update docs alongside code.** Parser rule changed → update
  `parsing-requirements.md`. UI component changed → update `ui-requirements.md`.
- **Parser requirements P1–P8** are in `docs/parsing-requirements.md`. P1 (BLE tag) and P5 (battery critical) are done. P2–P4 pending. P8 (TAK server receipt latency / clock skew — the server-side counterpart to P6) was defined 2026-08-24 to resolve references already present in `parser/tak.py` and `models.py`. P6 investigated 2026-06-15 (KNOT constant ≈ −2h host-clock skew; two open QA questions blocking closure — which clock was correct + tz/NTP-vs-manually-wrong root cause; GID label conflict resolved 2026-06-16 as same-radio reuse, see identity-model note above). P7 deferred. Protocol architecture (BROADCAST/PRIVATE/UNICAST normalization, GRIP, logId) also documented there.
- **Do not add npm packages without justification.** Check Chart.js 4.4,
  React 18, and plain CSS first.
