# UI Requirements

> **Source of truth for all dashboard and UI requirements.**
> Update this file as requirements change or grow.
> Reference implementation: `tw_field_data__4_.html` (provided Apr 2026)

---

## Table of Contents
- [Tech Stack](#tech-stack)
- [Design System](#design-system)
- [Layout Structure](#layout-structure)
- [KPI Header Row](#kpi-header-row)
- [Tabs](#tabs)
- [Known Limitations & Open Questions](#known-limitations--open-questions)

---

## Tech Stack

- **Framework:** React / Vite
- **API:** FastAPI
- **Charting:** Chart.js 4.4.1
- **Fonts:** Rajdhani (body), Barlow Condensed (headings), Share Tech Mono (monospace/data)

---

## Design System

Dark tactical aesthetic. All colors defined as CSS variables:

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `#05080f` | Page background |
| `--bg2` | `#080c18` | Secondary background |
| `--panel` | `#0d1428` | Card/panel background |
| `--border` | `#162035` | Default border |
| `--border2` | `#1e2f4a` | Emphasized border |
| `--text` | `#b8cfe8` | Body text |
| `--muted` | `#4a6080` | Secondary/label text |
| `--accent` | `#00d4ff` | Primary accent (cyan) |
| `--accent2` | `#ff6b35` | Secondary accent (orange) |
| `--green` | `#00e5a0` | Positive/good |
| `--yellow` | `#ffd166` | Caution threshold |
| `--red` | `#ff4757` | Alert/critical |
| `--purple` | `#c77dff` | Supplementary data |

---

## Layout Structure

```
┌─────────────────────────────────────────────────┐
│  HEADER (frosted glass, 8px padding)            │
│    goTenna Log Parser · Log selector ·          │
│    Time window badge · + Add Log Files · Clear  │
├─────────────────────────────────────────────────┤
│  TAB BAR                                        │
├─────────────────────────────────────────────────┤
│  TAB PANEL (active tab content)                 │
│    [Overview only] KPI row                      │
│    section-header                               │
│    chart-wrap / table / data grid               │
│    ...                                          │
└─────────────────────────────────────────────────┘
```

**Header:** Frosted glass (`rgba(5,8,15,0.92)` + `backdrop-filter: blur(12px)`), `8px` vertical padding. Title is "goTenna Log Parser" in Barlow Condensed with "Log Parser" in `--accent`. Separated from content by `var(--border2)` bottom border.

**KPI row:** Rendered inside the Overview tab only — not pinned globally. Scrolls with tab content.

**Time window badge:** When a filter is active, a compact badge appears in the header between the log selector and the upload button showing `WINDOW start → end UTC` with an ✕ to clear.

---

## KPI Header Row

Displayed on the **Overview tab only** (not globally pinned). One `KpiCard` per metric. Cards support an optional `tooltip` prop — on hover shows a dropdown with per-device detail.

| KPI | Color | Value | Sub-label | Tooltip |
|-----|-------|-------|-----------|---------|
| Devices Logged | `--accent` | Count | "hover for details" | callsign · FORMAT · firmware per log |
| Network Nodes | `--green` | Count | "Unique GIDs / peers observed" | — |
| Peak Temp | threshold | °F | Device that hit peak | — |
| Avg Hop Count | `--accent2` | hops | "diagnostic + ATAK · RSDK via GRIP" | — |
| App Version | green/red | version (build) | "N devices" or "⚠ version mismatch" | callsign · vX.X.X (build) · PLATFORM per log |
| Radio Firmware | green/red | version(s) | "all match" or "⚠ version mismatch" | — |
| PLI Changers | `--purple` | n/total | "N nodes changed rate" | — |
| Avg PLI Rate | threshold | e.g. "5m" | median across N nodes or "⚠ N high-freq nodes ≤30s" | — |
| Chat Messages | `--accent` | Count | "received across all devices" | — |

**Peak Temp color:** red ≥ 131°F · yellow ≥ 113°F · green below 113°F.

**App Version / Radio Firmware color:** red = mismatch · green = all match.

**Avg PLI Rate:** Median dominant interval across all observed nodes (diagnostic only). Color follows PLI thresholds: red ≤ 30s · yellow ≤ 180s · green > 180s. High-freq warning shown if any node's dominant interval is ≤ 30s.

> **Temperature rule:** Always display in °F. Source data is Celsius — convert before display.

---

## Tabs

### 1. Overview (`overview`)
- **KPI Row** — rendered at top of this tab only (see KPI Header Row section)
- **Session Timeline** — active windows per device; horizontal bar per log showing start → end with gap count
- **Messages Received by Device** — PLI vs chat breakdown bar chart
- **Network Participants** — grid of all unique originators; shows callsign, GID, PLI rate

### 2. PLI Frequency (`pli`)
- **Originator PLI — All Network Nodes** — one card per originator node; shows dominant PLI rate (by message count), interval label, STABLE / ⚠ CHANGES badge, and an ALSO OBSERVED section listing every other interval seen with its message count

**PLI interval color thresholds (applied to dominant interval and all ALSO OBSERVED chips):**

| Interval | Color | Label |
|----------|-------|-------|
| ≤ 5 seconds | Red | VERY HIGH |
| 6–15 seconds | Red | CRITICAL |
| 16–30 seconds | Red | HIGH |
| 31–180 seconds | Yellow | ELEVATED |
| > 180 seconds | Green | STANDARD |

> ⚠️ **5s and 15s intervals are critical data points.** These indicate deliberate high-frequency testing or misconfiguration and must always be clearly visible in red.
>
> ⚠️ **`N/A` is not an interval.** It indicates the originator's radio was disconnected at time of receipt. Exclude from dominant interval calculation and from ALSO OBSERVED chips.
>
> ⚠️ **Dominant interval is determined by message count**, not first-seen. A node that sent 110 messages at 5s and 9 at 300s shows 5s as dominant.
>
> ⚠️ **CHANGES badge fires when more than one real (non-N/A) interval was observed** for a node, even if the non-dominant interval count is very small. Nodes with a single stable interval show **no badge** — STABLE is intentionally not shown since interval changes are normal on a live network.

**Below the cards:** Stacked horizontal bar chart — "Estimated Time per PLI Interval". Each row is one node; each colored segment is an interval. Duration computed from consecutive message gaps capped at 3× the interval. N/A gaps bridged when same interval appears on both sides.

### 3. TX / RX Analysis (`txrx`)
- **Chat Message TX/RX — What the Logs Can Tell Us** — explanatory section on data limitations
- **Sent vs Received Counters** — app-reported cumulative totals (broadcast + private); bar chart; note: Unknown device had no Message Count Details blocks
- **Received Messages by Type** — broadcast vs private (1to1) breakdown; bar chart
- **Per-Device TX Delivery — Cross-Log Verification** — messages sent, confirmed in ≥1 other log, unverifiable gap; table per device
- **Private (1to1) Messages — Full Detail** — every private message to/from a logging device; table with hop count

**GRIP Transfer Analysis (RSDK logs only — shown when grip_transfer_count > 0):**
- **Delivery Time Distribution** — histogram of `delivery_ms` per completed transfer; x-axis in ms; color-coded by outcome (delivered = green, cancelled = red, incomplete = amber). Sub-label shows average delivery time.
- **Transfer Outcomes** — stacked bar per device: delivered / cancelled / incomplete counts
- **Retransmission Rate** — bar chart of `grip_retransmit_count` (segments requiring >1 attempt) vs clean segments per device. Note: `max_rep_counter = 2` means firmware was one failure from cancelling that transfer.
- **Broadcast vs Private Split** — bar chart of outgoing broadcast (`msg_type=2`) vs private (`msg_type=0`) message counts per device

### 4. Sessions & Radio Stats (`sessions`)
- **App Version** — from Device & Application Info block; table per device
- **App Crash Detection** — explanatory section; note: diagnostic log format v1 has no explicit crash markers, ANR events, or exception traces
- **Crash / Interruption Evidence** — result summary (0 confirmed crashes); gaps between exercise days are expected, not crashes
- **Active Session Lengths** — bar chart; session = contiguous activity block; gaps >30 min = session break
- **Radio Lifetime Uptime** — all-time cumulative firmware counter (not session duration); bar chart; captured at each stat snapshot

### 5. Thermal (`thermal`)
- **PA Temperature Over Time** — line chart per device; °F; thresholds: yellow = 113°F caution, red = 131°F peak. X-axis uses **normalized session progress (0–100%)** per device so sessions of different lengths all render fully across the chart width.
- **Peak Temperature by Device** — bar chart; highlight max per device

### 6. Battery (`battery`)
- **Battery Level Over Time** — line chart per device; %; red threshold line at 30%. X-axis uses **normalized session progress (0–100%)** — same approach as Thermal.
- **Minimum Battery Recorded** — bar chart; lowest % reached per device

### 7. Hop Count (`hops`)
- **Hop Count Distribution per Device** — bar/histogram per logging device; diagnostic and ATAK use `received_messages.hop_count`; RSDK uses `grip_messages` where `direction = "incoming"` and `hops` is not null — these are genuine RF hop counts from `GRIP_Receiver` structured fields lines
- **Hop Count Distribution — All Messages Combined** — network-wide histogram across all formats
- **Data source badge** per device: `DIAGNOSTIC` · `ATAK` · `GRIP (RSDK)` so the user knows which data source populated each chart

> ⚠️ **RSDK hop count source changed.** Previously excluded entirely as unreliable (SDK sequence counter). Now included when sourced from `GRIP_Receiver` incoming message fields — these are genuine RF mesh hop counts. The old `SendMessageResponse` hop count is still excluded.

### 8. RSSI (`rssi`)
- **RSSI Distribution by Hop Count** — box/bar chart grouped by hop count; diagnostic format: convert unsigned byte (value − 256); ATAK and RSDK GRIP: already signed dBm, no conversion needed
- **RSSI Distribution per Logging Device** — bar chart per device showing average RSSI; RSDK uses `grip_messages` incoming `rssi` field where available
- **Data source badge** per device: `DIAGNOSTIC` · `ATAK` · `GRIP (RSDK)`

> ⚠️ **RSDK RSSI source.** `grip_messages` incoming `rssi` values are real dBm from `GRIP_Receiver` structured fields — genuine RF signal strength. No conversion needed (already signed). Previously RSSI was unavailable for RSDK logs.

### 9. Chat Activity (`chat`)
- **Chat Messages Received by Device** — bar chart of non-PLI (text type) messages per logging device
- **Top Chat Senders** — bar chart of senders visible to logged devices

### 10. Health Score (`health`)
- **Per-Device Health Score** — composite radar chart per device; 4 dimensions (to be defined); higher = better
- Render one radar chart card per device

---

### 11. Relay Health (`relay-health`)
Displays data from goTenna Relay Manager logs (networkPolling and scheduledHealthRequest sub-types). Logs are auto-detected and routed here from the main upload — no separate upload required.

- **Session Info** — relay device serial, BLE MAC address, app PID, detected sub-type, environment (stage / unknown), log time span
- **Health Request Timeline** — timestamps of all confirmed `relayHealthRequestCall` events; computed average poll interval
- **Firmware Notification Breakdown** — bar chart of notification type counts with labels (BLE poll heartbeat, health response ready, device alert, battery change)
- **Event Log** — chronological list of named relay manager events (`health_response_ready`, `device_alert`, `battery_state_changed`, `empty_sender_uuid`) with timestamps
- **Data Limitations Banner** — always visible; surfaces the BLE payload decoding gap and any other active limitations from `parse_errors`

**Sub-type badge:** `networkPolling` or `scheduledHealthRequest` shown on the session card.

**Environment badge:** `STAGE` (cyan) or `UNKNOWN` (amber). Prod badge to be defined when prod logs are analyzed.

> ⚠️ Relay health attribute values (SNR, battery %, temperature °F, uptime, firmware version) are not yet available — they are encoded in BLE payload bytes not yet decoded. Surface this limitation prominently rather than silently omitting the fields.

---

## Known Limitations & Open Questions

- **Temperature** must always be converted from Celsius (source) to Fahrenheit (display) — never show raw °C values
- **RSSI** is stored as unsigned byte in diagnostic logs; real dBm = value − 256; display as dBm
- **Hop count in RSDK logs** — `GRIP_Receiver` incoming `hops` field is genuine RF routing data and should be included in hop count analysis. Legacy `SendMessageResponse` hop count (SDK sequence counter) is still excluded. Display a `GRIP (RSDK)` source badge to distinguish from diagnostic/ATAK data.
- **Unknown device** had no Message Count Details blocks — some KPIs will be unavailable for this device
- **App crash detection** is not possible from diagnostic log format v1 — no crash markers present; surface this limitation honestly in the Sessions tab
- **Health Score dimensions** not yet fully defined — placeholder radar chart in reference implementation
- **Relay Health tab — BLE payload decoding pending:** Relay health attribute values (SNR, battery %, temperature °F, uptime, firmware version) cannot be displayed until BLE protocol decoding is implemented. The tab must surface this limitation via a Data Limitations Banner rather than showing empty fields silently.
- **Relay Health tab — prod environment:** Prod log behavior and environment badge are undefined until prod samples are analyzed.
- **Topology tab** — Alpha/Beta feature; see Tab 12. Accuracy is inherently limited by what the logs can surface — the hardest data point in the dashboard to get right; must be clearly labeled as experimental in the UI
- **Multi-log upload** — supported; drag-and-drop or file picker; multiple files processed simultaneously
- **Duplicate log detection** — files with matching `radio_serial + session_start + session_end` are deduplicated automatically; only first occurrence used. Handles named files (`RSO_HagenM.txt`) loaded alongside auto-exported equivalents (`diagnostic_2026*.txt`).
- **Time window filtering** — client-side; filters all time-series arrays (`received_messages`, `system_samples`, `ble_fail_events`, `tx_events`, `atak_messages`, `atak_health_samples`). Computable summary fields recomputed from filtered arrays; static fields retain parse-time values.
- **Chart time axis** — line charts use per-device normalized session-progress axis (0–100%) rather than shared absolute time axis, ensuring sessions of very different lengths all render fully.

---

_Last updated: 2026-05-26_

---

### 12. Network Topology (`topology`) — ⚠️ ALPHA/BETA

> This is the most difficult data point in the dashboard to get accurate. Topology is inferred entirely from what the parsed logs can surface — it is not ground truth. The UI must clearly label this tab as experimental/Alpha.

**Purpose:** Visualize the mesh network as a node graph — which devices were communicating, through how many hops, and how messages flowed between them.

**Data sources (inferred from parsed logs):**
- `senderGid` / `originatorGid` / `receiverGid` from received messages → node relationships
- `hopCount` → edge weight / routing depth (diagnostic logs only — not reliable from RSDK)
- `rssi` → signal strength between nodes (diagnostic logs only)
- `originatorCallsign` / `receiverCallsign` → node labels
- `timestamp` → temporal filtering (show topology at a point in time or over full session)
- Multiple log files → cross-device perspective improves accuracy

**What the topology can show:**
- Nodes: every unique GID observed as originator or receiver
- Edges: message paths between nodes, weighted by hop count
- Direct links (hop count = 1) are the most reliable
- Multi-hop paths (hop count > 1) are inferred — intermediate relay nodes are not directly visible in the logs

**Known accuracy limitations (must be surfaced in UI):**
- Intermediate relay nodes are invisible — a 3-hop message passed through 2 unknown relays that do not appear as named nodes
- Topology is reconstructed from the receiver's perspective only — nodes that never sent a message visible to a logging device will not appear
- RSDK log hop counts are not genuine RF routing data and must not be used for topology edges
- The more log files uploaded simultaneously, the more complete the picture — single-log topology is highly incomplete
- Node positions are layout-only (force-directed or similar) — they do not represent physical geography

**UI requirements:**
- Clearly label the tab with an ⚠️ Alpha/Beta badge
- Show a data confidence indicator (e.g. "X of Y nodes have confirmed direct links")
- Allow filtering by hop count (show only direct links, or include multi-hop)
- Allow filtering by time window
- Tooltip on each node: callsign, GID, messages sent/received, avg RSSI
- Tooltip on each edge: hop count, message count, avg RSSI
- Honest disclaimer visible on the tab: "Topology is inferred from log data. Intermediate relay nodes are not visible. Multi-hop paths are approximate."

---

_Last updated: 2026-05-26_

---

## To Do / Backlog

### Time Window Filtering — ✅ Implemented
Two-step upload flow: drop files → app scans timestamps client-side → dual-handle range slider with hour-level snapping. Start handle snaps down to hour, end snaps up (2:30–5:30 → 2:00–6:00). Adaptive tick marks: every 1hr if ≤24hr span, every 6hr for multi-day. Selected window displayed as header badge with ✕ to clear. Filtering recomputes summaries client-side.

### Session Persistence
Allow a user to save a parsed session so it can be retrieved later and compared alongside other test data.

**User story:** As a QA engineer, I want to save a parsed log session by name (e.g. "TW Field Exercise Apr 27") so I can reload it in a future session without re-uploading the original log files, and compare it against other saved sessions.

**Scope:**
- Save the full parsed result (the JSON returned by `POST /parse/`) with a user-defined name and timestamp
- List saved sessions on the landing page or in a sidebar panel
- Load a saved session back into the dashboard exactly as if the logs were just uploaded
- Allow multiple saved sessions to be loaded simultaneously for cross-exercise comparison
- Delete saved sessions

**Implementation notes:**
- Backend: extend `api/routes/export.py` session store with persistence (file-based JSON or SQLite — no database server needed for a local tool)
- Frontend: session list UI on the landing page, save button in the header when results are loaded
- Consider naming convention: exercise name + date + device count (e.g. "TW Exercise · Apr 27 · 4 devices")
- Saved sessions should include the original source filenames for traceability

**Dependencies:** Requires API session store to persist beyond in-memory (currently lost on server restart)

**Priority:** ✅ Implemented
