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
- **Fonts:** Rajdhani (body), Barlow Condensed (headings/display), Share Tech Mono (monospace/data, via `var(--mono)`). All three are loaded via a Google Fonts `<link>` in `index.html` and referenced by name in `index.css` and inline styles.

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
- **Sent vs Received** — app-reported cumulative totals; renders `chat_sent_recv` (diagnostic) and `atak_sent_vs_received` charts
- **Message Types Breakdown** — `atak_message_types` chart (ATAK only)
- **TX Outcomes (RSDK only)** — unicast ACK / NACK / Timeout; `tx_outcomes` chart
- **Partially Received (ATAK only)** — `atak_partial_received` chart

**GRIP Transfer Analysis (RSDK logs only — shown when any `grip_transfers` exist):**
- Explanatory note on the GRIP data source (structured `Outgoing/Incoming message fields` log lines; delivery time = sender-side "File transmission started" → "delivered"; repCounter caps at 3 before firmware cancels)
- **Transfer Outcomes** — `GripOutcomeBar`: delivered / cancelled / incomplete counts
- **Delivery Time Distribution** — `GripDeliveryChart`: `delivery_ms` per completed transfer
- **Transfers with retransmissions** — detail table (not a chart), shown only when any transfer has `max_rep_counter > 0`; lists start time, msg id, max rep counter (n/2), segment count, and delivery time/outcome per transfer

> **Backlog (not yet implemented):** per-device TX cross-log verification table, private (1to1) full-detail table, a broadcast-vs-private outgoing split chart, and a standalone retransmission-rate bar chart. These were in the reference design but are not in the current `TxRxTab`.

### 4. Sessions & Radio Stats (`sessions`)
- **App Version** — device card per log from the Device & Application Info block (or ATAK app launch record); shows format, app/build, platform, model, radio FW, serial
- **App Crash Detection** — explanatory note, shown only when a diagnostic log is loaded; diagnostic log format v1 has no explicit crash markers, ANR events, or exception traces — lists crash-proxy indicators (>30 min gaps, single app-info block, polling gaps)
- **Active Session Lengths** — `session_lengths` chart; session = contiguous activity block; gaps >30 min = session break

> **Backlog (not yet implemented):** Radio Lifetime Uptime bar chart (all-time cumulative firmware counter). The `radio_stat_snapshots` data is serialized but no chart renders it yet.

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

- **Hop Count Map** — rendered at the bottom of the Hop Count tab for ATAK logs that have `logging_user_location` data. Interactive Leaflet.js map (OpenStreetMap tiles, loaded from unpkg CDN). Each dot is the receiver's GPS position (`logging_user_location`) colored by hop count (green=1, yellow=2, orange=3, red=4+). Dashed RF link lines connect each receiver dot to the sender's `transmitted_location`; line color encodes RSSI quality (green ≥ −70 dBm · yellow −70 to −85 · orange −85 to −100 · red < −100). Lines capped at 80 per render for readability. One diamond marker (◆) per unique hop count (max 4) sits at the midpoint of its RF link line; clicking opens a popup showing distance (miles or feet via Haversine), RSSI + quality label, hop count, sender callsign, and timestamp. Controls: device selector, sender filter (All or specific callsign), RF links toggle. Map auto-fits bounds to visible points. Only renders when ATAK messages with `logging_user_location` are present.

  **RSSI thresholds** grounded in 2026-06-03 KOPEK field session data (range −19 to −118 dBm, median −86 dBm):
  | Band | Range | Color |
  |------|-------|-------|
  | Strong | ≥ −70 dBm | `#00e5a0` green |
  | Medium | −70 to −85 dBm | `#ffd166` yellow |
  | Weak | −85 to −100 dBm | `#ff6b35` orange |
  | Poor | < −100 dBm | `#ff4757` red |

### 8. RSSI (`rssi`)
- **RSSI Distribution by Hop Count** — `rssi_by_hop` chart grouped by hop count; diagnostic format: convert unsigned byte (value − 256); ATAK and RSDK GRIP: already signed dBm, no conversion needed
- **RSSI Distribution per Logging Device** — `rssi_avg_device` chart showing average RSSI per device; RSDK uses `grip_messages` incoming `rssi` field where available
- **GRIP RSSI Over Time** — shown only when RSDK GRIP RSSI data exists. Per-device summary cards (avg / min / max dBm, message count, and retransmit count when > 0) above the `grip_rssi_over_time` line chart. X-axis is normalized session progress (0–100%); each point is the bucketed average RSSI of incoming GRIP messages; ▲ markers flag buckets containing a retransmission (`rep_counter > 0`); dashed reference lines at −70 dBm (good) and −85 dBm (caution).

> ⚠️ **RSDK RSSI source.** `grip_messages` incoming `rssi` values are real dBm from `GRIP_Receiver` structured fields — genuine RF signal strength. No conversion needed (already signed). Previously RSSI was unavailable for RSDK logs.

### 9. Chat Activity (`chat`)
- **Chat / Map Message Split** — `pli_vs_chat` chart (PLI vs chat/map breakdown; same chart reused from Overview)
- **TX Outcomes** — `tx_outcomes` chart (RSDK logs only)

> **Backlog (not yet implemented):** dedicated "Chat Messages Received by Device" and "Top Chat Senders" charts from the reference design. The current `ChatTab` reuses the PLI-vs-chat split and TX-outcomes charts.

### 10. Health Score (`health`)
- **Per-Device Health Score** — one card per device showing a composite score out of 5 (not a radar chart). Score color: green ≥ 4 · yellow ≥ 3 · red below.

  **Pass/fail dimensions:**
  | Dimension | Pass condition | Rationale |
  |-----------|---------------|----------|
  | Thermal | Peak PA temp < 113°F | Hardware limit |
  | Battery | Min battery > 30% | Operational reserve |
  | BLE | No BLE fail events | Connectivity integrity. For ATAK logs, `ble_fail_count` comes from SDK Logging 2.0 `ERROR\|BLE` entries in `counts_by_tag`, falling back to the count of `deviceDisconnected` events when no SDK 2.0 records are present. |
  | RSSI | Avg RSSI > −95 dBm | From KOPEK field data (median −86, poor threshold −100) |
  | Queue | Peak storedMessages < 5 | Queue backup indicator — seen peaking at 30 on HOTLIPS |

  **Hop count is intentionally excluded** — hop count reflects network topology, not device health. A device at 3 hops in a healthy mesh is operating correctly.

  **Threshold status:** All thresholds are initial estimates pending field validation against observed failure cases. RSSI threshold (−95 dBm) is grounded in 2026-06-03 KOPEK field session data but has not been validated against device failures.

  **Scoped to device formats:** The Health Score is computed only for device logs — `atak`, `diagnostic`, and `rsdk` (the `HEALTH_FORMATS` allow-list in `App.jsx`). `relay_manager` logs are excluded: their summaries carry none of the five dimension inputs (`peak_temp_f`, `min_battery_pct`, `avg_rssi`, `ble_fail_count`, `max_stored_messages`), so a relay card would default-pass every dimension and show a misleading 5/5. When only `relay_manager` logs are loaded, the tab shows a "no device logs" note instead of empty score cards.

- **Radio Message Queue** — shown below score cards when any device has `max_stored_messages > 0`. Peak count per device, severity-colored (red ≥ 20, yellow ≥ 5, muted < 5). Explains the HOTLIPS PLI burst behavior (2026-06-03, peak=30, likely firmware buffer ceiling).
- Note updated from "placeholder" to "thresholds pending field validation".

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

### 12. ATAK (`atak`)
ATAK-only tab (`atakOnly`) — appears in the tab bar only when an ATAK plug-in log is loaded; marked with an `α` badge. Renders only ATAK-format results.

- **Data Limitations Banner** — shown at the top when any ATAK `parse_errors` entry begins with `DATA LIMITATION` (e.g. the sdkError volume baseline notice)
- **Message Delivery Status** — `atak_delivery_status` chart; includes `SUCCESS` (sender-side ACK), `FULLY_RECEIVED`, `SENT`, `DELIVERED`, `PARTIALLY_RECEIVED`
- **Message Types** — `atak_message_types` chart; PLI · Chat · Map Objects · File Transfers
- **Connection State Over Time** — `atak_connection_state` chart; CONNECTED vs CONNECTING health samples
- **Device Events Timeline** — `atak_events_timeline` chart; connect / disconnect (with location) / power / PLI / frequency / firmwareUpdate changes
- **Partially Received Messages** — `atak_partial_received` chart; shown only when `summary.partially_received > 0`. The Missing column shows `unknown` when `open_segments` is null (the -99 sentinel)
- **SDK Logging 2.0 — sdkError Events** — shown only when `summary.sdk_error_count > 0`; KPI cards for total event count and radio types (e.g. `PRO_X_2`), plus tables of events by tag and top `additionalInfo`. Aggregated, never rendered per-record
- **App Launches** — device cards; shown only when a log has more than one app launch (regular ATAK logs accumulate across launches)

> Negative delivery times (clock skew) are surfaced honestly via `summary.negative_delivery_time_count`. The sdkError volume baseline is unknown and surfaced as informational, not an error.

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

_Last updated: 2026-06-04_

---

### 13. Network Topology (`topology`) — ⚠️ ALPHA/BETA · NOT YET IMPLEMENTED

> **Not implemented.** There is no `topology` entry in the `TABS` array in `App.jsx` and no topology tab renders today. This section is a forward-looking design spec / backlog item, retained for when the feature is built.
>
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

_Last updated: 2026-06-04_

---

## To Do / Backlog

### Time Window Filtering — ✅ Implemented
Two-step upload flow: drop files → app scans timestamps client-side → dual-handle range slider with hour-level snapping. Start handle snaps down to hour, end snaps up (2:30–5:30 → 2:00–6:00). Adaptive tick marks: every 1hr if ≤24hr span, every 6hr for multi-day. Selected window displayed as header badge with ✕ to clear. Filtering recomputes summaries client-side.

### GRIP RSSI Line Graph Over Time — ✅ Implemented
Per-device GRIP RSSI line chart in the RSSI tab (`grip_rssi_over_time`), with summary cards and retransmit (▲) markers on a normalized 0–100% session-progress axis. See RSSI tab spec (section 8).

### Hop Count Map — ✅ Implemented
Interactive Leaflet.js map in the Hop Count tab showing receiver GPS position colored by hop count, with RSSI-colored RF link lines to sender positions, midpoint diamond markers with distance/signal popups, device + sender filters, and RF links toggle. Capped at 80 RF lines and 4 diamond markers per render. Only shown for ATAK logs with `logging_user_location` data. See Hop Count tab spec (section 7).

### ATAK Enhanced Log (SDK Logging 2.0) — ✅ Implemented
Full support for the enhanced ATAK log format. The `SdkLogSummaryCard` renders the aggregated `atak_sdk_error_summary` (counts by tag and by `additionalInfo`, distinct radio types, and a retained sample) — high-volume `sdkError` records are aggregated, never rendered per-record, with the volume-baseline `DATA LIMITATION` surfaced in the banner. Also covers the enhanced message/event fields: `loggingUserLocation` / `transmittedLocation`, `originatorUUID`, the `-99` open-segments sentinel shown as `unknown`, `firmwareUpdate` events, and `deviceDisconnected` location. See ATAK tab spec (section 12).

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

**Status:** ⏸ Deferred — not implemented. No persistence exists in `api/routes/export.py`, `App.jsx`, or `useLogData.js`.

### Health Score Threshold Validation
Validate the Health Score pass/fail thresholds against real field data, replacing
the current initial estimates (see Health Score spec, section 10).

**User story:** As a QA engineer, I want the Health Score dimensions to fail only
when a device is genuinely unhealthy, so the `/5` score is a signal I can trust
rather than a rough estimate.

**Scope — thresholds to validate against observed device behavior:**
- **BLE** (`> 0 = fail`): the dimension now derives `ble_fail_count` from the
  `ERROR|BLE` subset of ATAK `sdkError` records (falling back to `deviceDisconnected`
  event count when no SDK 2.0 records are present). A single transient BLE reconnect
  may not warrant a failure — the `> 0` cutoff needs a real-session baseline before it
  is trustworthy. The `sdkError` BLE-error volume baseline is unknown.
- **Thermal** (`< 113°F`), **Battery** (`> 30%`), **Queue** (`< 5 msgs`): also initial
  estimates, validated only against limited samples.
- **RSSI** (`> −95 dBm`): grounded in 2026-06-03 KOPEK field data but not yet validated
  against device failures.

**✅ Done (separate from the threshold work): relay_manager scoped out.** The Health
tab now computes scores only for device formats (`atak`, `diagnostic`, `rsdk`) via the
`HEALTH_FORMATS` allow-list in `App.jsx`, so `relay_manager` logs no longer render a
misleading 5/5. See the "Scoped to device formats" note under Health Score (section 10).
The remaining threshold-calibration work below is still blocked on field data.

**Completion criteria:**
- Each threshold backed by a documented baseline in `parsing-requirements.md`,
  replacing "initial estimate" wording.
- ✅ `relay_manager` logs no longer render a misleading 5/5 (scoped to device formats).
- The Health tab Note (`App.jsx`) updated from "thresholds pending field validation"
  once a threshold is validated.
- The `sdkError`-is-informational data limitation in CLAUDE.md / `parsing-requirements.md`
  updated to reflect any validated `ERROR|BLE` baseline.

**Dependencies:** Requires real ATAK (and diagnostic/rsdk) field logs with known
healthy vs. unhealthy device outcomes to calibrate against. Not actionable until such
samples are collected.

**Status:** ⏳ Pending — blocked on field data. The dimensions are wired and shipped
(BLE dimension completed in the `fix(health)` commits); only the threshold values
remain unvalidated, and this is disclosed honestly in the UI and all four docs.

### Time-Window Step — disabled state for unparseable timestamps
When the client-side scanner cannot parse timestamps from the uploaded logs, the
upload flow currently skips the time-window step entirely and jumps straight to the
dashboard. This is silent — the user never learns that time filtering is unavailable
or why.

**User story:** As a QA engineer uploading a log whose timestamps the tool can't read,
I want the time-window step to tell me filtering is unavailable for this log and why,
instead of silently disappearing, so I'm not left wondering whether the slider is
broken or whether my window was applied.

**Scope / behavior:**
- When `globalMin`/`globalMax` can't be derived (no parseable timestamps), still show
  the time-window step with the slider in a **disabled state** and a short explanation
  (e.g. "Time filtering unavailable — no parseable timestamps found in this log").
- Keep the **Analyse →** action available so the user can proceed without a window.
- Honest about gaps, consistent with the project philosophy — surface the limitation
  rather than hiding the step.

**Observed:** relay_manager logcat timestamps omit the year (`MM-DD HH:MM:SS.mmm`),
which the client-side scanner in `FileUpload.jsx` does not parse, so the range step is
skipped. Noticed during browser verification of the Health-tab scoping.

**Status:** ⏳ Pending — not started. Affects `ui/src/components/FileUpload.jsx`
(the `drop` → `range` step transition and `RangeSlider`).
