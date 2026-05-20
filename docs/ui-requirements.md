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
│  HEADER (title, sub, badge, KPI row)            │
├─────────────────────────────────────────────────┤
│  TAB BAR (10 tabs)                              │
├─────────────────────────────────────────────────┤
│  TAB PANEL (active tab content)                 │
│    section-header                               │
│    chart-wrap / table / data grid               │
│    section-header                               │
│    chart-wrap / table / data grid               │
│    ...                                          │
└─────────────────────────────────────────────────┘
```

---

## KPI Header Row

Displayed at all times above the tab bar. One KPI card per metric.

| KPI | Color | Value | Sub-label |
|-----|-------|-------|-----------|
| Devices Logged | `--accent` | Count | Device names + date ranges |
| Network Nodes | `--green` | Count | Unique originators seen |
| Peak Temp | `--yellow` | °F | Device that hit peak |
| Avg Hop Count | `--accent2` | hops | Range across all logs |
| App Version | `--green` | version + build | All devices / firmware note |
| PLI Changers | `--purple` | n/total | Nodes that changed rate |
| Radio Firmware | `--red` | version(s) | Flag mismatched versions |
| Chat Messages | `--accent` | Count | Across all devices |

> **Temperature rule:** Always display in °F. Source data is Celsius — convert before display.

---

## Tabs

### 1. Overview (`overview`)
- **Session Timeline** — active windows per device; horizontal bar chart showing date/time ranges
- **Messages Received by Device** — PLI vs chat breakdown; stacked bar chart from final Message Count Details block
- **Network Participants** — table of all unique originators; columns: callsign, PLI rate, firmware (if known), ⚠ flag if PLI changed

### 2. PLI Frequency (`pli`)
- **Receiver PLI Interval** — own PLI rate per logging device; bar chart
- **Originator PLI — All Network Nodes** — dominant PLI rate per originator; table with ⚠ for nodes that changed rate; flag 5s intervals as anomalous (stress test / misconfiguration)
- **PLI Change Events** — nodes observed switching PLI rate; bar chart of transition counts per node

### 3. TX / RX Analysis (`txrx`)
- **Chat Message TX/RX — What the Logs Can Tell Us** — explanatory section on data limitations
- **Sent vs Received Counters** — app-reported cumulative totals (broadcast + private); bar chart; note: Unknown device had no Message Count Details blocks
- **Received Messages by Type** — broadcast vs private (1to1) breakdown; bar chart
- **Per-Device TX Delivery — Cross-Log Verification** — messages sent, confirmed in ≥1 other log, unverifiable gap; table per device
- **Private (1to1) Messages — Full Detail** — every private message to/from a logging device; table with hop count

### 4. Sessions & Radio Stats (`sessions`)
- **App Version** — from Device & Application Info block; table per device
- **App Crash Detection** — explanatory section; note: diagnostic log format v1 has no explicit crash markers, ANR events, or exception traces
- **Crash / Interruption Evidence** — result summary (0 confirmed crashes); gaps between exercise days are expected, not crashes
- **Active Session Lengths** — bar chart; session = contiguous activity block; gaps >30 min = session break
- **Radio Lifetime Uptime** — all-time cumulative firmware counter (not session duration); bar chart; captured at each stat snapshot

### 5. Thermal (`thermal`)
- **PA Temperature Over Time** — line chart per device; °F; thresholds: yellow = 113°F caution, red = 131°F peak
- **Peak Temperature by Device** — bar chart; highlight max per device

### 6. Battery (`battery`)
- **Battery Level Over Time** — line chart per device; %; red threshold line at 30%
- **Minimum Battery Recorded** — bar chart; lowest % reached per device

### 7. Hop Count (`hops`)
- **Hop Count Distribution per Device** — bar/histogram per logging device; note: diagnostic logs contain genuine RF hop data (unlike RSDK logs where hop count is unreliable)
- **Hop Count Distribution — All Messages Combined** — network-wide histogram; max observed = 6

### 8. RSSI (`rssi`)
- **RSSI Distribution by Hop Count** — box/bar chart grouped by hop count; display as real dBm (value − 256); note: stored as unsigned byte (137–237)
- **RSSI Distribution per Logging Device** — bar chart per device showing average RSSI

### 9. Chat Activity (`chat`)
- **Chat Messages Received by Device** — bar chart of non-PLI (text type) messages per logging device
- **Top Chat Senders** — bar chart of senders visible to logged devices

### 10. Health Score (`health`)
- **Per-Device Health Score** — composite radar chart per device; 4 dimensions (to be defined); higher = better
- Render one radar chart card per device

---

## Known Limitations & Open Questions

- **Temperature** must always be converted from Celsius (source) to Fahrenheit (display) — never show raw °C values
- **RSSI** is stored as unsigned byte in diagnostic logs; real dBm = value − 256; display as dBm
- **Hop count in RSDK logs** is not genuine RF routing data — flag this in any RSDK-sourced hop count display
- **Unknown device** had no Message Count Details blocks — some KPIs will be unavailable for this device
- **App crash detection** is not possible from diagnostic log format v1 — no crash markers present; surface this limitation honestly in the Sessions tab
- **Health Score dimensions** not yet fully defined — placeholder radar chart in reference implementation
- **Topology tab** — Alpha/Beta feature; see Tab 11. Accuracy is inherently limited by what the logs can surface — the hardest data point in the dashboard to get right; must be clearly labeled as experimental in the UI
- **Multi-log upload** — reference HTML is a static export; dynamic React UI will need file upload supporting multiple logs simultaneously

---

_Last updated: 2026-05-20_

---

### 11. Network Topology (`topology`) — ⚠️ ALPHA/BETA

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

_Last updated: 2026-05-20_
