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

function makeScales(yMin, yMax, yLabel = '') {
  return {
    x: { grid: { color: GRID }, ticks: TICK },
    y: {
      min: yMin, max: yMax,
      grid: { color: GRID }, ticks: TICK,
      ...(yLabel ? { title: { display: true, text: yLabel, color: '#2a3a52', font: { size: 9 } } } : {}),
    },
  }
}

function ChartCard({ title, children }) {
  return (
    <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: '16px 18px', marginBottom: 10 }}>
      <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 14, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: '#c8ddf4', marginBottom: 12 }}>
        {title}
      </div>
      {children}
    </div>
  )
}

// ── Chart builders ────────────────────────────────────────────────────────────

function TempOverTime({ results }) {
  const labels = [...new Set(
    results.flatMap(r => r.system_samples.map(s => s.timestamp?.slice(11,16)))
  )].sort()

  const datasets = results.map((r, i) => ({
    label: r.device?.callsign || r.source_filename,
    data: labels.map(t => {
      const s = r.system_samples.find(x => x.timestamp?.slice(11,16) === t)
      return s?.pa_temp_f ?? null
    }),
    borderColor: PALETTE[i % PALETTE.length],
    backgroundColor: 'transparent',
    borderWidth: 1.5, pointRadius: 3, tension: 0.3, spanGaps: true,
  }))

  return (
    <ChartCard title="PA Temperature Over Time (°F)">
      <Line data={{ labels, datasets }} options={{ responsive: true, plugins: { tooltip: TT_CFG, legend: { labels: { color: '#4a6080' } } }, scales: makeScales(80, 145, '°F') }} />
    </ChartCard>
  )
}

function BatteryOverTime({ results }) {
  const labels = [...new Set(
    results.flatMap(r => r.system_samples.map(s => s.timestamp?.slice(11,16)))
  )].sort()

  const datasets = results.map((r, i) => ({
    label: r.device?.callsign || r.source_filename,
    data: labels.map(t => {
      const s = r.system_samples.find(x => x.timestamp?.slice(11,16) === t)
      return s?.battery_pct ?? null
    }),
    borderColor: PALETTE[i % PALETTE.length],
    backgroundColor: 'transparent',
    borderWidth: 1.5, pointRadius: 3, tension: 0.3, spanGaps: true,
  }))

  return (
    <ChartCard title="Battery % Over Time">
      <Line data={{ labels, datasets }} options={{ responsive: true, plugins: { tooltip: TT_CFG, legend: { labels: { color: '#4a6080' } } }, scales: makeScales(0, 105, '%') }} />
    </ChartCard>
  )
}

function HopDistribution({ results }) {
  const hops = [1,2,3,4,5,6]
  const datasets = results.map((r, i) => {
    const total = r.received_messages?.length || 1
    const counts = hops.map(h => r.received_messages?.filter(m => m.hop_count === h).length || 0)
    return {
      label: r.device?.callsign || r.source_filename,
      data: counts.map(c => +(c / total * 100).toFixed(1)),
      backgroundColor: PALETTE[i % PALETTE.length] + 'cc',
      borderRadius: 4,
    }
  })

  return (
    <ChartCard title="Hop Count Distribution (%)">
      <Bar data={{ labels: hops.map(h => `Hop ${h}`), datasets }} options={{ responsive: true, plugins: { tooltip: TT_CFG, legend: { labels: { color: '#4a6080' } } }, scales: makeScales(0, undefined, '%') }} />
    </ChartCard>
  )
}

function ChatSentReceived({ results }) {
  const labels  = results.map(r => r.device?.callsign || r.source_filename)
  const sentArr = results.map(r => r.summary?.final_chat_sent  || 0)
  const recvArr = results.map(r => r.summary?.final_chat_recv  || 0)

  return (
    <ChartCard title="Chat / Map Messages — Sent vs Received">
      <Bar
        data={{
          labels,
          datasets: [
            { label: 'Sent',     data: sentArr, backgroundColor: results.map((_, i) => PALETTE[i % PALETTE.length] + 'cc'), borderRadius: 4 },
            { label: 'Received', data: recvArr, backgroundColor: results.map((_, i) => PALETTE[i % PALETTE.length] + '44'), borderRadius: 4 },
          ],
        }}
        options={{ responsive: true, plugins: { tooltip: TT_CFG, legend: { labels: { color: '#4a6080' } } }, scales: makeScales(0, undefined) }}
      />
    </ChartCard>
  )
}

function BleFailsTotal({ results }) {
  const labels = results.map(r => r.device?.callsign || r.source_filename)
  const data   = results.map(r => r.summary?.ble_fail_count || 0)

  return (
    <ChartCard title="BLE Reconnection Failures per Device">
      <Bar
        data={{ labels, datasets: [{ label: 'BLE Failures', data, backgroundColor: data.map(v => v > 200 ? '#ff4757cc' : v > 50 ? '#ff8c00cc' : v > 0 ? '#ffd166cc' : '#1a3a1acc'), borderRadius: 4 }] }}
        options={{ responsive: true, plugins: { tooltip: TT_CFG, legend: { display: false } }, scales: makeScales(0, undefined) }}
      />
    </ChartCard>
  )
}

function TxOutcomes({ results }) {
  const labels   = results.map(r => r.device?.callsign || r.source_filename)
  const acks     = results.map(r => r.tx_events?.filter(t => t.outcome === 'final_ack').length || 0)
  const nacks    = results.map(r => r.tx_events?.filter(t => t.outcome === 'nack').length || 0)
  const timeouts = results.map(r => r.tx_events?.filter(t => t.outcome === 'timeout').length || 0)

  return (
    <ChartCard title="Unicast TX Outcomes (ACK / NACK / Timeout)">
      <Bar
        data={{
          labels,
          datasets: [
            { label: 'Final ACK', data: acks,     backgroundColor: '#00e5a0cc', borderRadius: 4 },
            { label: 'NACK',      data: nacks,     backgroundColor: '#ffd166cc', borderRadius: 4 },
            { label: 'Timeout',   data: timeouts,  backgroundColor: '#ff4757cc', borderRadius: 4 },
          ],
        }}
        options={{ responsive: true, plugins: { tooltip: TT_CFG, legend: { labels: { color: '#4a6080' } } }, scales: makeScales(0, undefined) }}
      />
    </ChartCard>
  )
}

function SessionLengths({ results }) {
  const allSessions = results.flatMap(r => {
    const gaps  = r.session_gaps || []
    const start = r.session_start
    const end   = r.session_end
    if (!start || !end) return []
    // Simple: one bar per device showing total active span
    const spanMin = (new Date(end) - new Date(start)) / 60000
    return [{ label: r.device?.callsign || r.source_filename, minutes: Math.round(spanMin) }]
  })

  return (
    <ChartCard title="Session Span per Device (minutes)">
      <Bar
        data={{
          labels: allSessions.map(s => s.label),
          datasets: [{ label: 'Session Span (min)', data: allSessions.map(s => s.minutes), backgroundColor: allSessions.map((_, i) => PALETTE[i % PALETTE.length] + 'cc'), borderRadius: 4 }],
        }}
        options={{ responsive: true, plugins: { tooltip: TT_CFG, legend: { display: false } }, scales: makeScales(0, undefined, 'Minutes') }}
      />
    </ChartCard>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────────

const CHART_MAP = {
  temp_over_time:    TempOverTime,
  battery_over_time: BatteryOverTime,
  hop_distribution:  HopDistribution,
  chat_sent_recv:    ChatSentReceived,
  ble_fails_total:   BleFailsTotal,
  tx_outcomes:       TxOutcomes,
  session_lengths:   SessionLengths,
}

export default function ChartPanel({ results, selectedPoints }) {
  if (selectedPoints.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '32px', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--muted)' }}>
        Select data points above to generate charts
      </div>
    )
  }

  return (
    <div>
      {selectedPoints.map(id => {
        const Component = CHART_MAP[id]
        if (!Component) return (
          <ChartCard key={id} title={id}>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--muted)' }}>Chart coming soon</div>
          </ChartCard>
        )
        return <Component key={id} results={results} />
      })}
    </div>
  )
}
