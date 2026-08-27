import { useState } from 'react'
import { Bar, Line } from 'react-chartjs-2'
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement,
  LineElement, PointElement, Title, Tooltip, Legend,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend)

const PALETTE = ['#00d4ff','#ff6b35','#ffd166','#c77dff','#00e5a0','#ff4757','#4a90e2','#ff6b9d']
const GRID    = '#162035'
const TICK    = { color: '#4a6080', font: { family: "'Share Tech Mono', monospace", size: 9 } }
const TT_CFG  = {
  backgroundColor: '#0d1428ee', titleColor: '#00d4ff',
  bodyColor: '#b8cfe8', borderColor: '#1e2f4a', borderWidth: 1,
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function shortLabel(r) {
  // Parsers with no identity field to read write the literal string 'unknown'
  // (next-gen radio logs carry no callsign at all). That means "absent", not a
  // device named "unknown" — fall through to the filename so two logs charted
  // together don't get identical series labels.
  const callsign = r.device?.callsign
  if (callsign && callsign !== 'unknown') return callsign
  const name = r.source_filename || ''
  // ATAK: diagnostic_ATAK_CALLSIGN_GID_...
  const atakMatch = name.match(/diagnostic_ATAK_([^_]+)_/)
  if (atakMatch) return atakMatch[1]
  // Diagnostic named: diagnostic_CALLSIGN_... (uppercase letters only)
  const namedMatch = name.match(/diagnostic_([A-Z][A-Z_]+)_/)
  if (namedMatch) return namedMatch[1]
  // Fallback to radio serial if available — more useful than truncated filename
  if (r.device?.radio_serial) return r.device.radio_serial.slice(-6)
  return name.replace(/\.[^.]+$/, '').slice(0, 20)
}

function downsample(arr, max = 50) {
  if (arr.length <= max) return arr
  const step = arr.length / max
  return Array.from({ length: max }, (_, i) => arr[Math.floor(i * step)])
}

/**
 * Build per-device normalized time series for line charts.
 *
 * Each device's samples are mapped to a 0–100% session-progress axis
 * independently, so a 3-day log and a 70-minute log both show their
 * full shape across the chart width. This avoids the sparse-data problem
 * that occurs when sessions of very different lengths share an absolute
 * time axis.
 *
 * X labels show % of each device's own session (0%, 10%, … 100%).
 */
function buildRelativeTimeSeries(results, key = 'system_samples', maxPoints = 15) {
  const toMs = ts => {
    if (!ts) return NaN
    const s = ts.includes('T') ? ts : ts.replace(' ', 'T')
    const ms = new Date(s.endsWith('Z') ? s : s + 'Z').getTime()
    return isNaN(ms) ? new Date(ts).getTime() : ms
  }

  const hasAny = results.some(r => (r[key] || []).some(s => s.timestamp))
  if (!hasAny) return { labels: [], getDataset: () => [] }

  // Shared normalized labels: 0% → 100% in maxPoints steps
  const labels = Array.from({ length: maxPoints }, (_, i) =>
    `${Math.round((i / (maxPoints - 1)) * 100)}%`
  )

  // Per-device: normalize each device's own session to 0-100%
  const getDataset = (r, valueKey) => {
    const samples = (r[key] || [])
      .filter(s => s.timestamp && s[valueKey] != null)
      .map(s => ({ ms: toMs(s.timestamp), val: s[valueKey] }))
      .filter(s => !isNaN(s.ms))
      .sort((a, b) => a.ms - b.ms)

    if (!samples.length) return labels.map(() => null)

    const devMin  = samples[0].ms
    const devSpan = Math.max(1, samples[samples.length - 1].ms - devMin)

    return labels.map((_, i) => {
      const targetPct = i / (maxPoints - 1)
      const targetMs  = devMin + targetPct * devSpan
      let closest = null, minDist = Infinity
      for (const s of samples) {
        const dist = Math.abs(s.ms - targetMs)
        if (dist < minDist) { minDist = dist; closest = s }
      }
      // Allow up to 2 bucket-widths gap before treating as null
      const bucketSpan = devSpan / (maxPoints - 1)
      return (closest && minDist <= bucketSpan * 2) ? closest.val : null
    })
  }

  return { labels, getDataset }
}

function makeScales(yMin, yMax, yLabel = '') {
  return {
    x: { grid: { color: GRID }, ticks: { ...TICK, maxTicksLimit: 10, maxRotation: 45 } },
    y: {
      min: yMin, max: yMax, grid: { color: GRID }, ticks: TICK,
      ...(yLabel ? { title: { display: true, text: yLabel, color: '#2a3a52', font: { size: 9 } } } : {}),
    },
  }
}

const LINE_OPTS = (extra = {}) => ({
  responsive: true, maintainAspectRatio: false,
  plugins: { tooltip: TT_CFG, legend: { labels: { color: '#4a6080', boxWidth: 10 } } },
  ...extra,
})

const BAR_OPTS = (extra = {}) => ({
  responsive: true, maintainAspectRatio: false,
  plugins: { tooltip: TT_CFG, legend: { labels: { color: '#4a6080' } } },
  ...extra,
})

function ChartCard({ title, subtitle, height = 260, children }) {
  return (
    <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: '16px 18px', marginBottom: 10 }}>
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 14, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: '#c8ddf4' }}>{title}</div>
        {subtitle && <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#2a3a52', marginTop: 2 }}>{subtitle}</div>}
      </div>
      <div style={{ height }}>{children}</div>
    </div>
  )
}

function DataNote({ text }) {
  return <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#ffd16680', marginTop: 6 }}>⚠ {text}</div>
}

function NoData({ message = 'No data available for this log format' }) {
  return <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--muted)', padding: '20px 0', textAlign: 'center' }}>{message}</div>
}

// ── Shared charts ─────────────────────────────────────────────────────────────

function TempOverTime({ results }) {
  const { labels, getDataset } = buildRelativeTimeSeries(results, 'system_samples', 15)
  const datasets = results.map((r, i) => ({
    label: shortLabel(r),
    data: getDataset(r, 'pa_temp_f'),
    borderColor: PALETTE[i % PALETTE.length], backgroundColor: 'transparent',
    borderWidth: 2, pointRadius: 3, pointBackgroundColor: PALETTE[i % PALETTE.length],
    tension: 0.4, spanGaps: true,
  }))
  return (
    <ChartCard title="PA Temperature Over Time (°F)" subtitle="Power amp temp recorded periodically · yellow = 113°F caution · red = 131°F peak" height={300}>
      <Line data={{ labels, datasets }} options={{ ...LINE_OPTS(), scales: makeScales(80, 145, '°F') }} />
    </ChartCard>
  )
}

function TempPeak({ results }) {
  const labels = results.map(r => shortLabel(r))
  const data   = results.map(r => r.summary?.peak_temp_f || 0)
  return (
    <ChartCard title="Peak PA Temperature per Device (°F)" height={200}>
      <Bar
        data={{ labels, datasets: [{ label: 'Peak °F', data, backgroundColor: data.map(v => v >= 131 ? '#ff4757cc' : v >= 113 ? '#ff8c00cc' : '#00e5a0cc'), borderRadius: 4 }] }}
        options={{ ...BAR_OPTS({ plugins: { tooltip: TT_CFG, legend: { display: false } } }), scales: makeScales(80, 145, '°F') }}
      />
    </ChartCard>
  )
}

function BatteryOverTime({ results }) {
  const [hiddenLabels, setHiddenLabels] = useState(new Set())
  const [pickerOpen, setPickerOpen] = useState(false)

  // X axis = real wall-clock time (HH:MM UTC), Y axis = battery %
  // Each device's actual sample timestamps are used directly rather than
  // normalizing to 0-100% session, so the chart shows real time of day.
  // Multi-device sessions with different start times are shown on a shared
  // absolute time axis — gaps appear where a device has no data.

  const toMs = ts => {
    if (!ts) return NaN
    const s = ts.includes('T') ? ts : ts.replace(' ', 'T')
    const ms = new Date(s.endsWith('Z') ? s : s + 'Z').getTime()
    return isNaN(ms) ? new Date(ts).getTime() : ms
  }

  const fmtTime = ms => {
    if (!ms || isNaN(ms)) return ''
    const d = new Date(ms)
    return d.toISOString().slice(11, 16) + ' UTC'
  }

  // Collect all sample points across all results with real timestamps
  const allPoints = []
  results.forEach(r => {
    const src = r.log_format === 'atak' ? (r.atak_health_samples || []) : (r.system_samples || [])
    src.forEach(s => {
      if (s.timestamp && s.battery_pct != null && s.battery_pct >= 0) {
        const ms = toMs(s.timestamp)
        if (!isNaN(ms)) allPoints.push(ms)
      }
    })
  })

  if (!allPoints.length) {
    return (
      <ChartCard title="Battery % Over Time" subtitle="X axis = real time (UTC) · Y axis = battery %" height={300}>
        <NoData />
      </ChartCard>
    )
  }

  // Build shared time axis across all devices — 20 evenly spaced ticks
  const globalMin = Math.min(...allPoints)
  const globalMax = Math.max(...allPoints)
  const span = Math.max(1, globalMax - globalMin)
  const NUM_TICKS = 40  // ~13.6 min buckets at 543 min session; reveals radio disconnect gaps
  const labels = Array.from({ length: NUM_TICKS }, (_, i) =>
    fmtTime(globalMin + (i / (NUM_TICKS - 1)) * span)
  )

  const outliers = []
  // One dataset per unique serial number within each result (Option B label: callsign · serial)
  // This shows radio swaps and BLE reconnections as separate lines rather than
  // a false recovery curve on a single line.
  const datasets = []
  let paletteIdx = 0
  results.forEach(r => {
    const callsign = r.device?.callsign || shortLabel(r)
    const isAtak = r.log_format === 'atak'
    const src = isAtak ? (r.atak_health_samples || []) : (r.system_samples || [])

    // Group samples by serial number
    const bySerial = {}
    src.forEach(s => {
      if (!s.timestamp || s.battery_pct == null) return
      const serial = s.serial_number || 'Unknown'
      if (!bySerial[serial]) bySerial[serial] = []
      bySerial[serial].push({ ms: toMs(s.timestamp), val: s.battery_pct })
    })

    const serials = Object.keys(bySerial)
    if (!serials.length) return

    const bucketSpan = span / (NUM_TICKS - 1)
    serials.sort().forEach(serial => {
      const samples = bySerial[serial].filter(s => !isNaN(s.ms)).sort((a, b) => a.ms - b.ms)
      const color = PALETTE[paletteIdx % PALETTE.length]
      // Only ATAK distinguishes radios by serial. diagnostic/rsdk have no serial
      // field at all, so their single 'Unknown' bucket is the device's real
      // battery line — render it connected, not as reconnecting-scatter.
      const reconnecting = isAtak && serial === 'Unknown'
      const labelText = isAtak && (serials.length > 1 || results.length > 1)
        ? `${callsign} · ${serial === 'Unknown' ? 'Unknown (reconnecting)' : serial}`
        : callsign

      const data = labels.map((_, idx) => {
        const targetMs = globalMin + (idx / (NUM_TICKS - 1)) * span
        let closest = null, minDist = Infinity
        for (const s of samples) {
          const dist = Math.abs(s.ms - targetMs)
          if (dist < minDist) { minDist = dist; closest = s }
        }
        if (!closest || minDist > bucketSpan * 1) return NaN  // NaN = visible gap in Chart.js 4
        const v = Math.min(100, Math.max(0, closest.val))
        if (closest.val < 0 || closest.val > 100) outliers.push(`${labelText}: ${closest.val}% at ${labels[idx]}`)
        return v
      })

      // Reconnecting (ATAK Unknown serial): same hue as device but dimmer
      const lineColor = reconnecting ? color + '70' : color  // 44% opacity
      datasets.push(reconnecting ? {
        // ATAK reconnecting radio: dots only — no line, no connections.
        // showLine:false on the default line dataset gives points-only without
        // needing a separate ScatterController registered (keeps the stack lean).
        label: labelText,
        data,
        borderColor: lineColor,
        backgroundColor: lineColor,
        pointRadius: 4,
        pointStyle: 'triangle',
        showLine: false,
      } : {
        label: labelText,
        data,
        borderColor: lineColor,
        backgroundColor: 'transparent',
        borderWidth: 2,
        pointRadius: 3,
        pointBackgroundColor: lineColor,
        tension: 0,
        spanGaps: false,
      })
      paletteIdx++
    })
  })

  const opts = {
    ...LINE_OPTS(),
    plugins: { tooltip: TT_CFG, legend: { display: false } },
    scales: {
      x: {
        grid: { color: GRID },
        ticks: { ...TICK, maxTicksLimit: 10, maxRotation: 45 },
        title: { display: true, text: 'Time (UTC)', color: '#2a3a52', font: { size: 9 } },
      },
      y: {
        min: 0, max: 100,
        grid: { color: GRID },
        ticks: TICK,
        title: { display: true, text: 'Battery %', color: '#2a3a52', font: { size: 9 } },
      },
    },
  }

  // ── Radio swap detection — DataNote only, no chart markers ────────────
  const swapEvents = []
  results.forEach(r => {
    const callsign = r.device?.callsign || shortLabel(r)
    const src2 = r.log_format === 'atak' ? (r.atak_health_samples || []) : (r.system_samples || [])
    const bySerial2 = {}
    src2.forEach(s => {
      if (!s.timestamp || s.battery_pct == null) return
      const serial = s.serial_number || 'Unknown'
      const ms = toMs(s.timestamp)
      if (!bySerial2[serial] || ms < bySerial2[serial]) bySerial2[serial] = ms
    })
    const serials2 = Object.keys(bySerial2).filter(s => s !== 'Unknown')
    if (serials2.length <= 1) return
    const primaryMs = Math.min(...serials2.map(s => bySerial2[s]))
    serials2.forEach(serial => {
      if (bySerial2[serial] === primaryMs) return
      swapEvents.push({ ms: bySerial2[serial], serial, callsign })
    })
  })
  swapEvents.sort((a, b) => a.ms - b.ms)
  const swapNote = swapEvents.length > 0
    ? `Radio swap${swapEvents.length > 1 ? 's' : ''} detected: `
      + swapEvents.map(ev => `${fmtTime(ev.ms)} → ${ev.serial}`).join(' · ')
      + '. Each line = one radio serial. '
      + 'Multiple serials appearing at the same time point reflect bucket sampling (~14 min window) — '
      + 'radio swaps within that window overlap on the chart. '
      + 'Note: deviceDisconnected events do not include serial numbers — '
      + 'disconnect attribution uses LIFO assumption (most recent connection disconnects first). '
      + 'Simultaneous multi-radio connection cannot be ruled out from log data alone.'
    : null
  const hasMultiSerial = results.some(r => {
    const src3 = r.log_format === 'atak' ? (r.atak_health_samples || []) : (r.system_samples || [])
    return new Set(src3.map(s => s.serial_number).filter(Boolean)).size > 1
  })

  const allLabels = datasets.map(d => d.label)
  const visibleDatasets = datasets.filter(d => !hiddenLabels.has(d.label))
  const shownCount = allLabels.length - hiddenLabels.size

  const toggleLabel = (label) => {
    setHiddenLabels(prev => {
      const next = new Set(prev)
      if (next.has(label)) next.delete(label)
      else next.add(label)
      return next
    })
  }

  return (
    <ChartCard title="Battery % Over Time" subtitle="X axis = real time (UTC) · Y axis = battery % · one line per radio serial · ▲ = Unknown/reconnecting BLE poll" height={320}>
      <div style={{ position: 'relative', marginBottom: 10, display: 'inline-block' }}>
        <button
          onClick={() => setPickerOpen(o => !o)}
          style={{
            fontFamily: 'var(--mono)', fontSize: 9, color: '#94a3b8',
            background: 'var(--panel)', border: '1px solid var(--border2)', borderRadius: 5,
            padding: '6px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          Radios ({shownCount}/{allLabels.length} shown) <span style={{ fontSize: 8 }}>{pickerOpen ? '▲' : '▼'}</span>
        </button>
        {pickerOpen && (
          <>
            <div onClick={() => setPickerOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 9998 }} />
            <div style={{
              position: 'absolute', top: '100%', left: 0, marginTop: 4,
              background: 'var(--panel)', border: '1px solid var(--border2)', borderRadius: 6,
              zIndex: 9999, minWidth: 320, maxWidth: 480, maxHeight: '50vh', overflowY: 'auto',
              boxShadow: '0 8px 32px #000a', padding: 8,
            }}>
              <div style={{ display: 'flex', gap: 6, marginBottom: 6, paddingBottom: 6, borderBottom: '1px solid var(--border)' }}>
                <button
                  onClick={() => setHiddenLabels(new Set())}
                  style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#00d4ff', background: 'transparent', border: '1px solid #00d4ff40', borderRadius: 4, padding: '4px 8px', cursor: 'pointer' }}
                >Select All</button>
                <button
                  onClick={() => setHiddenLabels(new Set(allLabels))}
                  style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#4a6080', background: 'transparent', border: '1px solid var(--border2)', borderRadius: 4, padding: '4px 8px', cursor: 'pointer' }}
                >Clear Selection</button>
              </div>
              {datasets.map(d => (
                <label key={d.label} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '4px 4px', cursor: 'pointer', fontFamily: 'var(--mono)', fontSize: 9 }}>
                  <input
                    type="checkbox"
                    checked={!hiddenLabels.has(d.label)}
                    onChange={() => toggleLabel(d.label)}
                    style={{ accentColor: d.borderColor, cursor: 'pointer' }}
                  />
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: d.borderColor, flexShrink: 0 }} />
                  <span style={{ color: hiddenLabels.has(d.label) ? '#334155' : '#c8ddf4' }}>{d.label}</span>
                </label>
              ))}
            </div>
          </>
        )}
      </div>
      <Line data={{ labels, datasets: visibleDatasets }} options={opts} />
      {swapNote && <DataNote text={swapNote} />}
      {hasMultiSerial && !swapNote && (
        <DataNote text="Multiple radio serials detected. Each line represents one radio — lines do not indicate simultaneous connections." />
      )}
      {outliers.length > 0 && <DataNote text={`Out-of-range readings clamped to 0–100%: ${outliers.join(', ')}`} />}
    </ChartCard>
  )
}

function BatteryMin({ results }) {
  const labels = results.map(r => shortLabel(r))
  // Use windowed summary value; fall back to original summary if windowing
  // produced null (e.g. time window doesn't cover health sample period)
  const data   = results.map(r =>
    r.summary?.min_battery_pct          // windowed value
    ?? r.summary?.min_battery_unfiltered // full-session fallback (ATAK)
    ?? null
  )
  return (
    <ChartCard title="Minimum Battery Recorded per Device" height={200}>
      <Bar
        data={{ labels, datasets: [{ label: 'Min %', data, backgroundColor: data.map(v => v == null ? '#2a3a52' : v < 30 ? '#ff4757cc' : v < 50 ? '#ff8c00cc' : '#00e5a0cc'), borderRadius: 4 }] }}
        options={{ ...BAR_OPTS({ plugins: { tooltip: TT_CFG, legend: { display: false } } }), scales: makeScales(0, 100, '%') }}
      />
    </ChartCard>
  )
}

function SessionLengths({ results }) {
  // Use hours for readability — multi-day logs produce huge minute values
  const sessions = results.map(r => {
    const start = r.session_start, end = r.session_end
    const hrs = (start && end) ? +((new Date(end) - new Date(start)) / 3600000).toFixed(1) : 0
    return { label: shortLabel(r), hours: hrs }
  })
  return (
    <ChartCard title="Session Span per Device" subtitle="Total hours from first to last record" height={200}>
      <Bar
        data={{ labels: sessions.map(s => s.label), datasets: [{ label: 'Hours', data: sessions.map(s => s.hours), backgroundColor: sessions.map((_, i) => PALETTE[i % PALETTE.length] + 'cc'), borderRadius: 4 }] }}
        options={{ ...BAR_OPTS({ plugins: { tooltip: TT_CFG, legend: { display: false } } }), scales: makeScales(0, undefined, 'Hours') }}
      />
      {sessions.some(s => s.hours > 24) && <DataNote text="One or more devices span multiple days — regular ATAK logs accumulate across app launches" />}
    </ChartCard>
  )
}

function PliVsChat({ results }) {
  const labels     = results.map(r => shortLabel(r))
  const pliCounts  = results.map(r => r.summary?.pli_count  || 0)
  const chatCounts = results.map(r => r.summary?.chat_count || 0)
  const dominated  = chatCounts.some((c, i) => pliCounts[i] > c * 50)
  return (
    <ChartCard title="PLI vs Chat Message Split">
      <Bar
        data={{ labels, datasets: [
          { label: 'PLI',  data: pliCounts,  backgroundColor: results.map((_, i) => PALETTE[i % PALETTE.length] + 'cc'), borderRadius: 4 },
          { label: 'Chat', data: chatCounts, backgroundColor: results.map((_, i) => PALETTE[i % PALETTE.length] + '55'), borderRadius: 4 },
        ]}}
        options={{ ...BAR_OPTS(), scales: makeScales(0, undefined) }}
      />
      {dominated && <DataNote text="Chat count is very small relative to PLI — see Chat tab for chat-only view" />}
    </ChartCard>
  )
}

function HopDistribution({ results }) {
  const eligible = results.filter(r => r.log_format === 'diagnostic' || r.log_format === 'atak')
  if (!eligible.length) return <NoData message="Hop count data available in diagnostic and ATAK logs only" />
  const hops = [1,2,3,4,5,6]
  const datasets = eligible.map((r, i) => {
    const msgs  = r.log_format === 'atak' ? (r.atak_messages || []).filter(m => !m.is_sender) : (r.received_messages || [])
    const total = msgs.length || 1
    return { label: shortLabel(r), data: hops.map(h => +(msgs.filter(m => m.hop_count === h).length / total * 100).toFixed(1)), backgroundColor: PALETTE[i % PALETTE.length] + 'cc', borderRadius: 4 }
  })
  return (
    <ChartCard title="Hop Count Distribution (%)" subtitle="RSDK excluded — not genuine RF routing data">
      <Bar data={{ labels: hops.map(h => `Hop ${h}`), datasets }} options={{ ...BAR_OPTS(), scales: makeScales(0, undefined, '%') }} />
    </ChartCard>
  )
}

function HopAvg({ results }) {
  const eligible = results.filter(r => r.log_format === 'diagnostic' || r.log_format === 'atak')
  if (!eligible.length) return <NoData message="Hop count data available in diagnostic and ATAK logs only" />
  const labels = eligible.map(r => shortLabel(r))
  const data   = eligible.map(r => r.summary?.avg_hop_count ?? null)
  return (
    <ChartCard title="Average Hop Count per Device" height={200}>
      <Bar
        data={{ labels, datasets: [{ label: 'Avg Hops', data, backgroundColor: data.map(v => v == null ? '#2a3a52' : v <= 2 ? '#00e5a0cc' : v <= 3 ? '#ffd166cc' : '#ff4757cc'), borderRadius: 4 }] }}
        options={{ ...BAR_OPTS({ plugins: { tooltip: TT_CFG, legend: { display: false } } }), scales: makeScales(0, 7, 'Hops') }}
      />
    </ChartCard>
  )
}

function RssiByHop({ results }) {
  const eligible = results.filter(r => r.log_format === 'diagnostic' || r.log_format === 'atak')
  if (!eligible.length) return <NoData message="RSSI data available in diagnostic and ATAK logs only" />
  const hops = [1,2,3,4,5,6]
  const datasets = eligible.map((r, i) => {
    const msgs = r.log_format === 'atak'
      ? (r.atak_messages || []).filter(m => !m.is_sender && m.rssi_is_valid)
      : (r.received_messages || []).filter(m => m.rssi_dbm != null)
    return {
      label: shortLabel(r),
      data: hops.map(h => { const vals = msgs.filter(m => m.hop_count === h).map(m => r.log_format === 'atak' ? m.rssi : m.rssi_dbm); return vals.length ? +(vals.reduce((a,b)=>a+b,0)/vals.length).toFixed(1) : null }),
      backgroundColor: PALETTE[i % PALETTE.length] + 'cc', borderRadius: 4,
    }
  })
  return (
    <ChartCard title="Avg RSSI by Hop Count (dBm)">
      <Bar data={{ labels: hops.map(h=>`Hop ${h}`), datasets }} options={{ ...BAR_OPTS(), scales: makeScales(undefined, 0, 'dBm') }} />
    </ChartCard>
  )
}

function RssiAvgDevice({ results }) {
  const eligible = results.filter(r => r.log_format === 'diagnostic' || r.log_format === 'atak')
  if (!eligible.length) return <NoData message="RSSI data available in diagnostic and ATAK logs only" />
  const labels  = eligible.map(r => shortLabel(r))
  const avgRssi = eligible.map(r => {
    if (r.log_format === 'atak') return r.summary?.avg_rssi ?? null
    const vals = (r.received_messages || []).map(m => m.rssi_dbm).filter(v => v != null)
    return vals.length ? +(vals.reduce((a,b)=>a+b,0)/vals.length).toFixed(1) : null
  })
  return (
    <ChartCard title="Avg RSSI per Device (dBm)" subtitle="Higher (less negative) = stronger signal" height={200}>
      <Bar
        data={{ labels, datasets: [{ label: 'Avg RSSI', data: avgRssi, backgroundColor: avgRssi.map(v => v==null?'#2a3a52':v>-70?'#00e5a0cc':v>-90?'#ffd166cc':'#ff4757cc'), borderRadius: 4 }] }}
        options={{ ...BAR_OPTS({ plugins: { tooltip: TT_CFG, legend: { display: false } } }), scales: makeScales(undefined, 0, 'dBm') }}
      />
    </ChartCard>
  )
}

// ── Diagnostic-only ───────────────────────────────────────────────────────────

function ChatSentReceived({ results }) {
  const diag = results.filter(r => r.log_format === 'diagnostic')
  if (!diag.length) return null
  const labels = diag.map(r => shortLabel(r))
  return (
    <ChartCard title="Chat / Map Messages — Sent vs Received" height={200}>
      <Bar
        data={{ labels, datasets: [
          { label: 'Sent',     data: diag.map(r => r.summary?.final_chat_sent  || 0), backgroundColor: diag.map((_,i) => PALETTE[i%PALETTE.length]+'cc'), borderRadius: 4 },
          { label: 'Received', data: diag.map(r => r.summary?.final_chat_recv  || 0), backgroundColor: diag.map((_,i) => PALETTE[i%PALETTE.length]+'44'), borderRadius: 4 },
        ]}}
        options={{ ...BAR_OPTS(), scales: makeScales(0, undefined) }}
      />
    </ChartCard>
  )
}

// ── RSDK-only ─────────────────────────────────────────────────────────────────

function BleFailsTotal({ results }) {
  const rsdk = results.filter(r => r.log_format === 'rsdk')
  if (!rsdk.length) return <NoData message="BLE failure data available in RSDK logs only" />
  const labels = rsdk.map(r => shortLabel(r))
  const data   = rsdk.map(r => r.summary?.ble_fail_count || 0)
  return (
    <ChartCard title="BLE Reconnection Failures per Device" height={200}>
      <Bar
        data={{ labels, datasets: [{ label: 'BLE Failures', data, backgroundColor: data.map(v => v>200?'#ff4757cc':v>50?'#ff8c00cc':v>0?'#ffd166cc':'#1a3a1acc'), borderRadius: 4 }] }}
        options={{ ...BAR_OPTS({ plugins: { tooltip: TT_CFG, legend: { display: false } } }), scales: makeScales(0, undefined) }}
      />
    </ChartCard>
  )
}

function TxOutcomes({ results }) {
  const rsdk = results.filter(r => r.log_format === 'rsdk')
  if (!rsdk.length) return <NoData message="TX outcome data available in RSDK logs only" />
  const labels = rsdk.map(r => shortLabel(r))
  return (
    <ChartCard title="Unicast TX Outcomes (ACK / NACK / Timeout)" height={200}>
      <Bar
        data={{ labels, datasets: [
          { label: 'Final ACK', data: rsdk.map(r => r.tx_events?.filter(t=>t.outcome==='final_ack').length||0),  backgroundColor: '#00e5a0cc', borderRadius: 4 },
          { label: 'NACK',      data: rsdk.map(r => r.tx_events?.filter(t=>t.outcome==='nack').length||0),       backgroundColor: '#ffd166cc', borderRadius: 4 },
          { label: 'Timeout',   data: rsdk.map(r => r.tx_events?.filter(t=>t.outcome==='timeout').length||0),    backgroundColor: '#ff4757cc', borderRadius: 4 },
        ]}}
        options={{ ...BAR_OPTS(), scales: makeScales(0, undefined) }}
      />
    </ChartCard>
  )
}

// ── ATAK-only ─────────────────────────────────────────────────────────────────

function AtakDeliveryStatus({ results }) {
  const atak = results.filter(r => r.log_format === 'atak')
  if (!atak.length) return <NoData message="No ATAK logs loaded" />
  const labels   = atak.map(r => shortLabel(r))
  const statuses = ['SUCCESS','FULLY_RECEIVED','SENT','DELIVERED','PARTIALLY_RECEIVED']
  const colors   = { SUCCESS:'#00e5a0cc', FULLY_RECEIVED:'#22d3eecc', SENT:'#00d4ffcc', DELIVERED:'#4a90e2cc', PARTIALLY_RECEIVED:'#ff4757cc' }
  const datasets = statuses.map(s => ({
    label: s.replace(/_/g,' '),
    data: atak.map(r => (r.atak_messages||[]).filter(m=>m.delivery_status===s).length),
    backgroundColor: colors[s], borderRadius: 4,
  }))
  return (
    <ChartCard title="ATAK Message Delivery Status">
      <Bar data={{ labels, datasets }} options={{ ...BAR_OPTS(), scales: makeScales(0, undefined) }} />
      {atak.some(r=>(r.summary?.partially_received||0)>0) && <DataNote text="Partially received messages detected — typically file transfers; segments not fully delivered over mesh" />}
    </ChartCard>
  )
}

function AtakMessageTypes({ results }) {
  const atak   = results.filter(r => r.log_format === 'atak')
  if (!atak.length) return <NoData message="No ATAK logs loaded" />
  const labels = atak.map(r => shortLabel(r))
  const types  = [['pli','#00d4ffcc'],['textChat','#00e5a0cc'],['mapObject','#c77dffcc'],['fileTransfer','#ffd166cc']]
  const datasets = types.map(([type, color]) => ({
    label: type, data: atak.map(r => (r.atak_messages||[]).filter(m=>m.message_type===type).length),
    backgroundColor: color, borderRadius: 4,
  }))
  return (
    <ChartCard title="ATAK Message Types Breakdown">
      <Bar data={{ labels, datasets }} options={{ ...BAR_OPTS(), scales: makeScales(0, undefined) }} />
    </ChartCard>
  )
}

function AtakSentVsReceived({ results }) {
  const atak   = results.filter(r => r.log_format === 'atak')
  if (!atak.length) return null
  const labels = atak.map(r => shortLabel(r))
  return (
    <ChartCard title="ATAK Sent vs Received Messages" height={200}>
      <Bar
        data={{ labels, datasets: [
          { label: 'Sent',     data: atak.map(r=>r.summary?.sent_count||0),     backgroundColor: '#00d4ffcc', borderRadius: 4 },
          { label: 'Received', data: atak.map(r=>r.summary?.received_count||0), backgroundColor: '#00d4ff44', borderRadius: 4 },
        ]}}
        options={{ ...BAR_OPTS(), scales: makeScales(0, undefined) }}
      />
    </ChartCard>
  )
}

function AtakPartialReceived({ results }) {
  const atak = results.filter(r => r.log_format === 'atak')
  const rows = atak.flatMap(r => (r.atak_messages||[]).filter(m=>m.delivery_status==='PARTIALLY_RECEIVED').map(m => ({
    device: shortLabel(r), timestamp: m.timestamp?.slice(0,16), type: m.message_type, segments: m.segment_count, open: m.open_segments,
  })))
  if (!rows.length) return (
    <ChartCard title="Partially Received Messages" height={60}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--muted)', textAlign: 'center', paddingTop: 16 }}>No partially received messages</div>
    </ChartCard>
  )
  return (
    <ChartCard title="Partially Received Messages" subtitle="Messages where not all RF segments were received" height={rows.length * 32 + 40}>
      <div style={{ overflowY: 'auto', height: '100%' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--mono)', fontSize: 9 }}>
          <thead><tr style={{ borderBottom: '1px solid var(--border2)' }}>{['Device','Time','Type','Segs','Missing'].map(h=><th key={h} style={{ padding:'4px 8px', textAlign:'left', color:'var(--muted)', fontWeight:400 }}>{h}</th>)}</tr></thead>
          <tbody>{rows.map((row,i)=><tr key={i} style={{ borderBottom:'1px solid var(--border)' }}>
            <td style={{ padding:'4px 8px', color:'#c77dff' }}>{row.device}</td>
            <td style={{ padding:'4px 8px', color:'var(--muted)' }}>{row.timestamp}</td>
            <td style={{ padding:'4px 8px', color:'var(--text)' }}>{row.type}</td>
            <td style={{ padding:'4px 8px', color:'var(--text)' }}>{row.segments}</td>
            <td style={{ padding:'4px 8px', color:'#ff4757' }}>{row.open == null ? 'unknown' : row.open}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </ChartCard>
  )
}

function AtakConnectionState({ results }) {
  const atak = results.filter(r => r.log_format === 'atak')
  if (!atak.length) return <NoData message="No ATAK logs loaded" />
  const allLabels = downsample([...new Set(atak.flatMap(r=>(r.atak_health_samples||[]).map(h=>h.timestamp?.slice(11,16)).filter(Boolean)))].sort(), 40)
  const datasets = atak.map((r,i) => ({
    label: `${shortLabel(r)} — CONNECTED`,
    data: allLabels.map(t => { const h = (r.atak_health_samples||[]).find(x=>x.timestamp?.slice(11,16)===t); return h?.connection_state==='CONNECTED'?1:null }),
    borderColor: PALETTE[i%PALETTE.length], backgroundColor:'transparent',
    borderWidth: 1.5, pointRadius: 0, spanGaps: false, stepped: true,
  }))
  return (
    <ChartCard title="Radio Connection State Over Time" subtitle="1 = CONNECTED · gap = CONNECTING or disconnected">
      <Line data={{ labels: allLabels, datasets }} options={{ ...LINE_OPTS(), scales: makeScales(0, 1.2) }} />
    </ChartCard>
  )
}

function AtakEventsTimeline({ results }) {
  const atak = results.filter(r => r.log_format === 'atak')
  const eventColors = { deviceConnected:'#00e5a0', deviceDisconnected:'#ff4757', powerLevelUpdated:'#ffd166', pliSettingUpdated:'#00d4ff', frequencyUpdated:'#c77dff', firmwareUpdate:'#ff6b35', relayModeUpdated:'#3b82f6' }
  const allEvents = atak.flatMap(r => (r.atak_events||[]).map(e => ({ ...e, device: shortLabel(r) }))).sort((a,b)=>a.timestamp?.localeCompare(b.timestamp))
  if (!allEvents.length) return <ChartCard title="Device Events Timeline" height={60}><NoData message="No events recorded" /></ChartCard>

  const getDetail = e => {
    if (e.event_type==='deviceConnected')    return `Serial: ${e.serial_number} via ${e.connection_type}`
    if (e.event_type==='deviceDisconnected') {
      const loc = e.location ? ` @ ${e.location.lat?.toFixed?.(4)}, ${e.location.long?.toFixed?.(4)}` : ''
      return `via ${e.connection_type}${loc}`
    }
    if (e.event_type==='powerLevelUpdated')  return `${e.power_watts}W`
    if (e.event_type==='pliSettingUpdated')  return `${e.pli_interval_sec}s · auto=${e.pli_auto_send}`
    if (e.event_type==='frequencyUpdated') {
      const chList = (e.channels || [])
        .map(c => `${c.frequency}${c.isControlChannel ? '★' : ''}`)
        .join(', ')
      return `${e.power_watts}W · ${e.bandwidth_khz}kHz · [${chList || '—'}] MHz (★=ctrl)`
    }
    if (e.event_type==='firmwareUpdate')     return `${e.update_status}${e.update_time_ms != null ? ` · ${e.update_time_ms}ms` : ''}`
    if (e.event_type==='relayModeUpdated')   return e.relay_mode_enabled ? 'Relay mode ON' : 'Relay mode OFF'
    return ''
  }

  return (
    <ChartCard title="Device Events Timeline" subtitle="Connect · Disconnect · Power · PLI · Frequency · Relay" height={allEvents.length * 30 + 50}>
      <div style={{ overflowY: 'auto', height: '100%' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--mono)', fontSize: 9 }}>
          <thead><tr style={{ borderBottom:'1px solid var(--border2)' }}>{['Time','Device','Event','Detail'].map(h=><th key={h} style={{ padding:'4px 8px', textAlign:'left', color:'var(--muted)', fontWeight:400 }}>{h}</th>)}</tr></thead>
          <tbody>{allEvents.map((e,i)=><tr key={i} style={{ borderBottom:'1px solid var(--border)' }}>
            <td style={{ padding:'4px 8px', color:'var(--muted)' }}>{e.timestamp?.slice(0,16)}</td>
            <td style={{ padding:'4px 8px', color:'#c77dff' }}>{e.device}</td>
            <td style={{ padding:'4px 8px', color: eventColors[e.event_type]||'var(--text)' }}>{e.event_type}</td>
            <td style={{ padding:'4px 8px', color:'var(--text)' }}>{getDetail(e)}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </ChartCard>
  )
}


// ── GRIP RSSI Over Time ───────────────────────────────────────────────────────

/**
 * Build a normalized time series from grip_messages (incoming, rssi not null).
 * grip_messages is a flat array with {timestamp, rssi, rep_counter, msg_id, ...}
 * rather than the {timestamp, value} shape of system_samples, so we can't use
 * buildRelativeTimeSeries directly.
 *
 * Buckets raw messages into maxPoints normalized time slots (0%–100% of each
 * device's own session span) and averages the rssi values within each bucket.
 * Downsampling is implicit — dense logs with thousands of messages produce a
 * smooth averaged line rather than noisy per-message scatter.
 */
function buildGripRssiSeries(results, maxPoints = 40) {
  const toMs = ts => {
    if (!ts) return NaN
    const s = ts.includes('T') ? ts : ts.replace(' ', 'T')
    const ms = new Date(s.endsWith('Z') ? s : s + 'Z').getTime()
    return isNaN(ms) ? new Date(ts).getTime() : ms
  }

  const labels = Array.from({ length: maxPoints }, (_, i) =>
    `${Math.round((i / (maxPoints - 1)) * 100)}%`
  )

  const datasets = []
  const retransmitSets = []  // parallel datasets for retransmit overlay points

  results.forEach((r, ri) => {
    if (r.log_format !== 'rsdk') return
    const msgs = (r.grip_messages || [])
      .filter(g => g.direction === 'incoming' && g.rssi != null && g.timestamp)
      .map(g => ({ ms: toMs(g.timestamp), rssi: g.rssi, rep: g.rep_counter || 0 }))
      .filter(g => !isNaN(g.ms))
      .sort((a, b) => a.ms - b.ms)

    if (!msgs.length) return

    const devMin  = msgs[0].ms
    const devSpan = Math.max(1, msgs[msgs.length - 1].ms - devMin)
    const bucket  = devSpan / maxPoints

    // For each time bucket, average rssi values; track whether any had rep > 0
    const buckets = Array.from({ length: maxPoints }, () => ({ vals: [], hasRetransmit: false }))
    for (const m of msgs) {
      const idx = Math.min(maxPoints - 1, Math.floor((m.ms - devMin) / bucket))
      buckets[idx].vals.push(m.rssi)
      if (m.rep > 0) buckets[idx].hasRetransmit = true
    }

    const avgData     = buckets.map(b => b.vals.length ? Math.round(b.vals.reduce((a, v) => a + v, 0) / b.vals.length) : null)
    const retransmits = buckets.map((b, i) => b.hasRetransmit ? avgData[i] : null)  // point at same y as avg line

    const color = PALETTE[ri % PALETTE.length]
    const serial = r.device?.radio_serial || shortLabel(r)

    datasets.push({
      label: serial,
      data: avgData,
      borderColor: color,
      backgroundColor: 'transparent',
      borderWidth: 2,
      pointRadius: 2,
      pointBackgroundColor: color,
      tension: 0.4,
      spanGaps: true,
    })

    // Retransmit overlay — same color but larger filled points, no line
    retransmitSets.push({
      label: `${serial} retransmit`,
      data: retransmits,
      borderColor: 'transparent',
      backgroundColor: '#ff4757cc',
      pointRadius: 6,
      pointStyle: 'triangle',
      showLine: false,
      spanGaps: false,
    })
  })

  return { labels, datasets: [...datasets, ...retransmitSets] }
}

function GripRssiOverTime({ results }) {
  const hasData = results.some(r =>
    r.log_format === 'rsdk' &&
    (r.grip_messages || []).some(g => g.direction === 'incoming' && g.rssi != null)
  )

  if (!hasData) return (
    <NoData message="No GRIP_Receiver incoming RSSI data in loaded files — upload an RSDK log with GRIP_Receiver lines to see RSSI over time" />
  )

  const { labels, datasets } = buildGripRssiSeries(results, 40)

  // Dynamic y-axis range — pad 5 dBm above max and below min
  const allVals = datasets.flatMap(d => d.data || []).filter(v => v != null)
  const yMin = allVals.length ? Math.min(...allVals) - 5 : -120
  const yMax = allVals.length ? Math.max(...allVals) + 5 : -40

  // Annotation lines for signal quality thresholds
  // Chart.js annotation plugin not in stack — draw as extra datasets instead
  const thresholdGood = {
    label: '−70 dBm (good)',
    data: labels.map(() => -70),
    borderColor: '#00e5a040',
    borderWidth: 1,
    borderDash: [4, 4],
    pointRadius: 0,
    tension: 0,
    spanGaps: true,
  }
  const thresholdPoor = {
    label: '−85 dBm (caution)',
    data: labels.map(() => -85),
    borderColor: '#ff470740',
    borderWidth: 1,
    borderDash: [4, 4],
    pointRadius: 0,
    tension: 0,
    spanGaps: true,
  }

  const chartData = {
    labels,
    datasets: [...datasets, thresholdGood, thresholdPoor],
  }

  const options = {
    ...LINE_OPTS(),
    scales: {
      x: { grid: { color: GRID }, ticks: { ...TICK, maxTicksLimit: 10 } },
      y: {
        min: yMin, max: yMax,
        grid: { color: GRID },
        ticks: { ...TICK, callback: v => `${v} dBm` },
        title: { display: true, text: 'dBm', color: '#2a3a52', font: { size: 9 } },
      },
    },
    plugins: {
      tooltip: {
        ...TT_CFG,
        callbacks: {
          label: ctx => {
            if (ctx.dataset.label?.includes('retransmit')) return `${ctx.dataset.label.replace(' retransmit', '')} retransmit at ${ctx.parsed.y} dBm`
            if (ctx.dataset.label === '−70 dBm (good)' || ctx.dataset.label === '−85 dBm (caution)') return ctx.dataset.label
            return `${ctx.dataset.label}: ${ctx.parsed.y} dBm`
          }
        }
      },
      legend: {
        labels: {
          color: '#4a6080',
          boxWidth: 10,
          filter: item => !item.text?.includes('retransmit') && !item.text?.startsWith('−'),
        }
      },
    },
  }

  return (
    <ChartCard
      title="GRIP RSSI Over Time (dBm)"
      subtitle="Averaged per time bucket across session · ▲ = segment with retransmit (rep_counter > 0) · dashed lines = −70 / −85 dBm thresholds"
      height={320}
    >
      <Line data={chartData} options={options} />
    </ChartCard>
  )
}

// ── TAK server ────────────────────────────────────────────────────────────────

/**
 * Server receipt latency per event — receivedAt minus the device-generated
 * time, in chronological order.
 *
 * Points-only via showLine:false, the same technique BatteryOverTime uses to
 * avoid registering a separate scatter controller. Negative values are real
 * data (a source device whose clock runs fast relative to the server) and are
 * drawn red rather than clamped — see the tak row in CLAUDE.md's known data
 * limitations, and P8 in docs/parsing-requirements.md.
 */
function TakLatency({ results }) {
  const events = results
    .filter(r => r.log_format === 'tak')
    .flatMap(r => r.tak_events || [])
  const withLatency = events
    .filter(e => e.latency_ms != null)
    .sort((a, b) => a.timestamp.localeCompare(b.timestamp))

  if (!withLatency.length) {
    return (
      <ChartCard title="Server Receipt Latency" subtitle="receivedAt − time per event">
        <div style={{ fontFamily:'var(--mono)', fontSize:9, color:'#4a6080', padding:'20px 0', textAlign:'center' }}>
          No events with both a device timestamp and a server receipt timestamp.
        </div>
      </ChartCard>
    )
  }

  const negativeCount = withLatency.filter(e => e.latency_ms < 0).length

  const data = {
    labels: withLatency.map(e => e.timestamp.slice(11, 19)),
    datasets: [{
      label: 'Latency (ms)',
      data: withLatency.map(e => e.latency_ms),
      showLine: false,
      pointRadius: 3,
      pointBackgroundColor: withLatency.map(e => e.latency_ms < 0 ? '#ff4757' : '#00d4ff'),
      borderColor: 'transparent',
    }],
  }

  const options = {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      tooltip: {
        ...TT_CFG,
        callbacks: {
          label: ctx => {
            const e = withLatency[ctx.dataIndex]
            return `${e.callsign || 'unknown'} · ${e.latency_ms} ms`
          },
        },
      },
      legend: { labels: { color:'#4a6080', boxWidth: 10 } },
    },
    scales: {
      x: { grid: { color: GRID }, ticks: { ...TICK, maxTicksLimit: 10, maxRotation: 45 } },
      y: {
        grid: { color: GRID }, ticks: TICK,
        title: { display: true, text: 'ms', color: '#2a3a52', font: { size: 9 } },
      },
    },
  }

  return (
    <ChartCard
      title="Server Receipt Latency"
      subtitle={`receivedAt − time per event · ${negativeCount} event(s) show negative latency (red) — a fast device clock, not a data error`}
      height={320}
    >
      <Line data={data} options={options} />
    </ChartCard>
  )
}

// ── ht-modem only ─────────────────────────────────────────────────────────────

function HtModemTempOverTime({ results }) {
  const hm = results.filter(r => r.log_format === 'htmodem')
  if (!hm.length) return <NoData message="No ht-modem logs loaded" />

  const toMs = ts => {
    if (!ts) return NaN
    const s = ts.includes('T') ? ts : ts.replace(' ', 'T')
    const ms = new Date(s.endsWith('Z') ? s : s + 'Z').getTime()
    return isNaN(ms) ? new Date(ts).getTime() : ms
  }

  // Downsample the SAMPLE rows together (not each metric separately) so
  // LPD/FPD/PL stay aligned at the same points rather than drifting apart.
  // Elapsed-time-since-start (not absolute time): each session's own first
  // sample becomes x=0, regardless of its real calendar date. This is what
  // lets multiple sessions from wildly different dates (or even different
  // years) overlay meaningfully on one shared axis instead of a shared
  // absolute-date axis stretching to fit the full gap between them.
  const perDevice = hm.map(r => {
    const samples = (r.htmodem?.temp_samples_f || [])
      .filter(s => s.timestamp)
      .map(s => ({ ...s, ms: toMs(s.timestamp) }))
      .filter(s => !isNaN(s.ms))
      .sort((a, b) => a.ms - b.ms)
    const startMs = samples.length ? samples[0].ms : 0
    const withElapsed = samples.map(s => ({ ...s, elapsedMs: s.ms - startMs }))
    return { r, samples: downsample(withElapsed, 150) }
  })

  const anySamples = perDevice.some(d => d.samples.length > 0)
  if (!anySamples) return <NoData message="No temperature samples in this log" />

  const allElapsed = perDevice.flatMap(d => d.samples.map(s => s.elapsedMs))
  const maxElapsedHours = Math.max(...allElapsed) / 3_600_000

  // "1:23:45" for sessions over an hour, "12:34" otherwise — a stopwatch/
  // duration format, not a clock-time format, since this is elapsed time.
  const fmtDuration = ms => {
    const totalSec = Math.round(ms / 1000)
    const h = Math.floor(totalSec / 3600)
    const m = Math.floor((totalSec % 3600) / 60)
    const s = totalSec % 60
    const pad = n => String(n).padStart(2, '0')
    return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
  }

  const metrics = [['lpd_f', '#00d4ff', 'LPD'], ['fpd_f', '#ff6b35', 'FPD'], ['pl_f', '#ffd166', 'PL']]
  const datasets = perDevice.flatMap(({ r, samples }) => metrics.map(([key, color, name]) => ({
    label: hm.length > 1 ? `${shortLabel(r)} — ${name}` : `${name} Temp (°F)`,
    data: samples.map(s => ({ x: s.elapsedMs, y: s[key], _abs: s.ms })),
    borderColor: color, backgroundColor: color + '22',
    tension: 0.3, pointRadius: 0, borderWidth: 2,
  })))

  return (
    <ChartCard title="Next-Gen Modem Thermal (LPD / FPD / PL)" subtitle="Zynq MPSoC thermal zones · °F · elapsed time since each session's start">
      <Line data={{ datasets }} options={LINE_OPTS({
        parsing: false,
        scales: {
          x: {
            type: 'linear', grid: { color: GRID }, min: 0,
            ticks: { ...TICK, maxTicksLimit: 10, maxRotation: 0, callback: fmtDuration },
            title: { display: true, text: maxElapsedHours >= 1 ? 'elapsed (h:mm:ss)' : 'elapsed (m:ss)', color: '#2a3a52', font: { size: 9 } },
          },
          y: { grid: { color: GRID }, ticks: TICK, title: { display: true, text: '°F', color: '#2a3a52', font: { size: 9 } } },
        },
        plugins: {
          tooltip: {
            ...TT_CFG,
            callbacks: {
              title: items => items.length ? `+${fmtDuration(items[0].parsed.x)}` : '',
              // Absolute timestamp shown too — still useful for cross-
              // referencing a spike back to a specific line in the raw log.
              afterTitle: items => items.length && items[0].raw?._abs
                ? new Date(items[0].raw._abs).toLocaleString(undefined, {
                    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
                  })
                : '',
            },
          },
          legend: { labels: { color: '#4a6080', boxWidth: 10 } },
        },
      })} />
    </ChartCard>
  )
}

function HtModemTxOutcomes({ results }) {
  const hm = results.filter(r => r.log_format === 'htmodem')
  if (!hm.length) return <NoData message="No ht-modem logs loaded" />
  const labels = hm.map(r => shortLabel(r))
  return (
    <ChartCard title="TX Packet Outcomes" subtitle="Queued for transmission vs. dropped (CSMA queue full)" height={200}>
      <Bar
        data={{ labels, datasets: [
          { label: 'Queued',  data: hm.map(r => r.summary?.queued_count || 0),  backgroundColor: '#00e5a0cc', borderRadius: 4 },
          { label: 'Dropped', data: hm.map(r => r.summary?.dropped_count || 0), backgroundColor: '#ff4757cc', borderRadius: 4 },
        ]}}
        options={{ ...BAR_OPTS(), scales: makeScales(0, undefined) }}
      />
    </ChartCard>
  )
}

// ── ht-router only ────────────────────────────────────────────────────────────

function HtRouterConnectedTimeline({ results }) {
  const hr = results.filter(r => r.log_format === 'htrouter')
  if (!hr.length) return <NoData message="No ht-router logs loaded" />
  const adapted = hr.map(r => ({
    ...r,
    _snaps: (r.htrouter?.stat_snapshots || []).map(s => ({
      timestamp: s.timestamp,
      connected_num: s.connected === true ? 1 : s.connected === false ? 0 : null,
    })),
  }))
  const { labels, getDataset } = buildRelativeTimeSeries(adapted, '_snaps', 20)
  if (!labels.length) return <NoData message="No stat snapshots in this log" />

  const datasets = hr.map((r, i) => ({
    label: shortLabel(r), data: getDataset(adapted[i], 'connected_num'),
    borderColor: '#22d3ee', backgroundColor: '#22d3ee22',
    stepped: true, pointRadius: 0, borderWidth: 2,
  }))
  return (
    <ChartCard title="Connection State Over Time" subtitle="Derived from periodic stat snapshots">
      <Line data={{ labels, datasets }} options={LINE_OPTS({
        scales: {
          x: { grid: { color: GRID }, ticks: { ...TICK, maxTicksLimit: 10, maxRotation: 45 } },
          y: { min: 0, max: 1, grid: { color: GRID }, ticks: { ...TICK, stepSize: 1, callback: v => v === 1 ? 'Connected' : 'Disconnected' } },
        },
      })} />
    </ChartCard>
  )
}

function HtRouterCumulativeFailures({ results }) {
  const hr = results.filter(r => r.log_format === 'htrouter')
  if (!hr.length) return <NoData message="No ht-router logs loaded" />
  const adapted = hr.map(r => ({ ...r, _snaps: r.htrouter?.stat_snapshots || [] }))
  const { labels, getDataset } = buildRelativeTimeSeries(adapted, '_snaps', 20)
  if (!labels.length) return <NoData message="No stat snapshots in this log" />

  const metrics = [['output_modem_xmit_failed', '#ff4757', 'Modem TX Failures'], ['output_time_outs', '#ffd166', 'Timeouts']]
  const datasets = hr.flatMap((r, i) => metrics.map(([key, color, name]) => ({
    label: hr.length > 1 ? `${shortLabel(r)} — ${name}` : name,
    data: getDataset(adapted[i], key),
    borderColor: color, backgroundColor: color + '22',
    tension: 0.2, pointRadius: 0, borderWidth: 2,
  })))
  return (
    <ChartCard
      title="Cumulative Modem TX Failures & Timeouts"
      subtitle="Session-lifetime running totals (not per-interval counts) — a flat stretch means no new failures in that period, not zero total"
    >
      <Line data={{ labels, datasets }} options={LINE_OPTS({ scales: makeScales(0, undefined) })} />
    </ChartCard>
  )
}

function HtRouterMsgTypes({ results }) {
  const hr = results.filter(r => r.log_format === 'htrouter')
  if (!hr.length) return <NoData message="No ht-router logs loaded" />
  // Message type vocabulary is an open set — build categories from what's
  // actually present rather than a hardcoded list (same pattern as the ATAK
  // Modes tab's dynamically-built status lists).
  const allTypes = [...new Set(hr.flatMap(r => Object.keys(r.summary?.msg_type_counts || {})))]
  if (!allTypes.length) return <NoData message="No protocol messages in this log" />
  const labels = hr.map(r => shortLabel(r))
  const datasets = allTypes.map((type, i) => ({
    label: type,
    data: hr.map(r => r.summary?.msg_type_counts?.[type] || 0),
    backgroundColor: PALETTE[i % PALETTE.length] + 'cc', borderRadius: 4,
  }))
  return (
    <ChartCard title="Protocol Message Types" subtitle="client-hdr / mgt-hdr message type breakdown">
      <Bar data={{ labels, datasets }} options={{ ...BAR_OPTS(), scales: makeScales(0, undefined) }} />
    </ChartCard>
  )
}

// ── Registry ──────────────────────────────────────────────────────────────────

const CHART_MAP = {
  temp_over_time:        TempOverTime,
  temp_peak:             TempPeak,
  battery_over_time:     BatteryOverTime,
  battery_min:           BatteryMin,
  session_lengths:       SessionLengths,
  pli_vs_chat:           PliVsChat,
  hop_distribution:      HopDistribution,
  hop_avg:               HopAvg,
  rssi_by_hop:           RssiByHop,
  rssi_avg_device:       RssiAvgDevice,
  grip_rssi_over_time:   GripRssiOverTime,
  chat_sent_recv:        ChatSentReceived,
  ble_fails_total:       BleFailsTotal,
  tx_outcomes:           TxOutcomes,
  atak_delivery_status:  AtakDeliveryStatus,
  atak_message_types:    AtakMessageTypes,
  atak_sent_vs_received: AtakSentVsReceived,
  atak_partial_received: AtakPartialReceived,
  atak_connection_state: AtakConnectionState,
  atak_events_timeline:  AtakEventsTimeline,
  tak_latency:           TakLatency,
  htmodem_temp:          HtModemTempOverTime,
  htmodem_outcomes:      HtModemTxOutcomes,
  htrouter_connected:    HtRouterConnectedTimeline,
  htrouter_cumulative_failures: HtRouterCumulativeFailures,
  htrouter_msg_types:    HtRouterMsgTypes,
}

export default function ChartPanel({ results, selectedPoints }) {
  if (!selectedPoints?.length) return (
    <div style={{ textAlign:'center', padding:'32px', fontFamily:'var(--mono)', fontSize:10, color:'var(--muted)' }}>
      Select data points above to generate charts
    </div>
  )
  return (
    <div>
      {selectedPoints.map(id => {
        const Component = CHART_MAP[id]
        if (!Component) return null
        return <Component key={id} results={results} />
      })}
    </div>
  )
}
