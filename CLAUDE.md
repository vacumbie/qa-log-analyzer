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
    └── ui-requirements.md        # Tab specs, KPI cards, backlog items
```

Look in `docs/` first when adding anything non-trivial. The specs there
are the intended source of truth — keep them in sync with the code.

---

## Supported log formats

Five formats, auto-detected by `_detect_format()` in `api/routes/parse.py`.
**Detection order matters** — fw_log runs first because its bracket pattern
`[digits-digits, MODULE, LEVEL]` is highly distinctive and cannot match any of
the other four. relay_manager must precede rsdk because both contain
`AndroidBleRadio` lines; relay_manager has additional markers that distinguish
it. `diagnostic` is always the catch-all fallback.

| Priority | Key | Parser | Source |
|----------|-----|--------|--------|
| 1 | `fw_log` | `parser/fw_log.py` | goTenna relay radio firmware (UART/USB debug) |
| 2 | `atak` | `parser/atak.py` | Android ATAK plug-in |
| 3 | `relay_manager` | `parser/relay_manager.py` | Android logcat, `com.gotenna.relaymanager` |
| 4 | `rsdk` | `parser/rsdk.py` | iOS/Android SDK logs |
| 5 | `diagnostic` | `parser/diagnostic.py` | goTenna Pro+ app export (fallback) |

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
Each active limitation has a `DATA LIMITATION` entry in `parse_errors` and
a visible banner in the relevant UI tab.

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
| `atak` | Callsign always empty in this format — identity is GID-only |
| `atak` | `sdkError` (SDK Logging 2.0) total volume baseline unknown — `sdk_error_count` is aggregated and informational, not a pass/fail signal. Exception: the `ERROR\|BLE` subset of `counts_by_tag` (falling back to `deviceDisconnected` event count) feeds the BLE Health Score dimension as `ble_fail_count`; its `> 0 = fail` threshold is an initial estimate pending field validation, like the other Health Score thresholds |
| `atak` | `numberOfOpenSegments = -99` is a sentinel (transfer cancelled before count known) — stored as null, never -99 |
| `atak` | Receiver-side `deliveryTimeInMillis = 0` on fileTransfer is a placeholder — only meaningful when `isSender=true` and status `SUCCESS` |
| `atak` | Device Health `serialNumber = "Unknown"` is expected during BLE reconnection, not a parser error |
| `fw_log` | Timestamps are relative ms from boot, not wall clock UTC — a session cannot be pinned to absolute time without a reference point from a correlated Relay Manager log |
| `fw_log` | Device serial number and firmware version live in the binary RHC response payload — not plaintext. Identity is shown as the origin hash only |
| `fw_log` | Battery stabilization errors are a known firmware quirk (the routine fires even when the battery is already stable), counted separately from real errors — not indicative of hardware failure, pending field validation |
| `fw_log` | `RSSI[]` detailed samples are DEBUG-level and skipped, so `rssi_samples`/`rssi_summary` are always empty; channel energy (`energy_samples`) is the RSSI proxy surfaced in the UI |

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
| P6: KNOT clock skew investigation | ⏳ Pending |
| P7: Poseidon log format | ⏳ Deferred |
| PLI tab ATAK support + gap inference | ✅ Done — all 14 devices shown |
| Battery chart real UTC timestamps + per-serial lines | ✅ Done |
| PLI Settings section (pliSettingUpdated) | ✅ Done |
| GID collision fix (CL_B + gt_Sassy_B_Net) | ✅ Done — nodeMap key = gid+filename |
| Time-window step disabled state for unparseable timestamps | ✅ Done — `range-unavailable` step in FileUpload.jsx replaces the silent skip |
| Min battery windowed reduce returns 0 for single-sample sets (ATAK branch) | ⏳ Pending — pre-existing `Math.min(…, null)` coercion bug |

---

## Agent-specific notes

- **Fetch current file state before editing.** Do not assume a file matches
  a previous session's output — the repo may have changed.
- **deviceDisconnected LIFO assumption:** Serial is omitted on disconnect events. Attribution uses LIFO (most recent connect = first to disconnect). Documented in `docs/parsing-requirements.md`. Pending dev team confirmation.
- **GID collision (CL_B + gt_Sassy_B_Net):** Share GID `90194071247761` and serial `PNE233200347`. PLI `nodeMap` uses `gid|source_filename` as key. Dev team notified.
- **Check `docs/` before adding anything non-trivial.** The specs there
  describe intended behavior. If the code disagrees with the docs, flag it.
- **One commit per logical change.** Format: `type(scope): description` —
  e.g. `feat(parser): add relay_manager` or `fix(ui): modal z-index via createPortal`.
- **Update docs alongside code.** Parser rule changed → update
  `parsing-requirements.md`. UI component changed → update `ui-requirements.md`.
- **Parser requirements P1–P7** are in `docs/parsing-requirements.md`. P1 (BLE tag) and P5 (battery critical) are done. P2–P4, P6 pending. P7 deferred. Protocol architecture (BROADCAST/PRIVATE/UNICAST normalization, GRIP, logId) also documented there.
- **Do not add npm packages without justification.** Check Chart.js 4.4,
  React 18, and plain CSS first.
