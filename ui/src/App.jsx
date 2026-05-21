import { useState, useMemo } from 'react'
import FileUpload from './components/FileUpload.jsx'
import ChartPanel from './components/ChartPanel.jsx'
import useLogData from './hooks/useLogData.js'

// ── Palette & constants ───────────────────────────────────────────────────────
const PALETTE = ['#00d4ff','#ff6b35','#ffd166','#c77dff','#00e5a0','#ff4757','#4a90e2','#ff6b9d']
const C = { accent:'#00d4ff', green:'#00e5a0', yellow:'#ffd166', red:'#ff4757', muted:'#4a6080', dim:'#2a3a52' }

const TABS = [
  { id:'overview',  label:'Overview' },
  { id:'pli',       label:'PLI Frequency' },
  { id:'txrx',      label:'TX / RX' },
  { id:'sessions',  label:'Sessions' },
  { id:'thermal',   label:'Thermal' },
  { id:'battery',   label:'Battery' },
  { id:'hops',      label:'Hop Count' },
  { id:'rssi',      label:'RSSI' },
  { id:'chat',      label:'Chat' },
  { id:'health',    label:'Health Score' },
  { id:'atak',      label:'ATAK', atakOnly: true },
]

// ── Shared sub-components ─────────────────────────────────────────────────────

function SectionHeader({ icon, title, sub }) {
  return (
    <div style={{ marginBottom: 14, marginTop: 28 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
        {icon && <span style={{ fontSize: 16 }}>{icon}</span>}
        <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 16, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: '#c8ddf4' }}>{title}</span>
      </div>
      {sub && <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, letterSpacing: '0.04em' }}>{sub}</div>}
    </div>
  )
}

function Note({ children }) {
  return (
    <div style={{ background: '#00d4ff08', border: '1px solid #00d4ff20', borderRadius: 6, padding: '12px 16px', fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, lineHeight: 1.7, marginBottom: 16 }}>
      {children}
    </div>
  )
}

function KpiCard({ label, value, sub, color = C.accent }) {
  return (
    <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6, padding: '10px 16px', minWidth: 110, position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 2, background: color }} />
      <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>{label}</div>
      <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 22, fontWeight: 700, color, lineHeight: 1 }}>{value ?? '—'}</div>
      {sub && <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.dim, marginTop: 3 }}>{sub}</div>}
    </div>
  )
}

// ── KPI row ───────────────────────────────────────────────────────────────────

function KpiRow({ results }) {
  const allHops = results.flatMap(r => {
    if (r.log_format === 'atak') return (r.atak_messages || []).filter(m => !m.is_sender && m.hop_count).map(m => m.hop_count)
    return (r.received_messages || []).map(m => m.hop_count).filter(Boolean)
  })
  const peakTempF  = Math.max(0, ...results.map(r => r.summary?.peak_temp_f || 0))
  const peakDevice = results.find(r => r.summary?.peak_temp_f === peakTempF)
  const totalChat  = results.reduce((n, r) => n + (r.summary?.chat_count || 0), 0)
  const firmwares  = [...new Set(results.map(r => r.device?.radio_firmware).filter(Boolean))]
  const avgHops    = allHops.length ? (allHops.reduce((a, b) => a + b, 0) / allHops.length).toFixed(1) : null
  const nodeCount  = new Set(results.flatMap(r => {
    if (r.log_format === 'atak') return (r.atak_messages || []).map(m => m.sender_gid).filter(Boolean)
    return (r.received_messages || []).map(m => m.originator_gid).filter(Boolean)
  })).size

  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', padding: '12px 36px', borderBottom: '1px solid var(--border)', background: 'var(--bg2)', flexShrink: 0 }}>
      <KpiCard label="Devices Logged"  value={results.length} sub={results.map(r => r.device?.callsign || '?').join(' · ')} />
      <KpiCard label="Network Nodes"   value={nodeCount || '—'} sub="Unique GIDs observed" color={C.green} />
      <KpiCard label="Peak Temp"       value={peakTempF ? `${peakTempF}°F` : '—'} sub={peakDevice?.device?.callsign} color={peakTempF >= 131 ? C.red : peakTempF >= 113 ? C.yellow : C.green} />
      <KpiCard label="Avg Hop Count"   value={avgHops ?? '—'} sub="across all logs" color='#ff6b35' />
      <KpiCard label="Radio Firmware"  value={firmwares.join(' / ') || '—'} sub={firmwares.length > 1 ? '⚠ version mismatch' : 'all match'} color={firmwares.length > 1 ? C.red : C.green} />
      <KpiCard label="Chat Messages"   value={totalChat} sub="received across all devices" />
    </div>
  )
}

// ── Tab panels ────────────────────────────────────────────────────────────────

function OverviewTab({ results }) {
  const allOriginators = useMemo(() => {
    const seen = {}
    results.forEach(r => {
      if (r.log_format === 'diagnostic') {
        r.received_messages?.forEach(m => {
          if (m.originator_callsign && !seen[m.originator_gid]) {
            seen[m.originator_gid] = { callsign: m.originator_callsign, gid: m.originator_gid, pli: m.originator_pli_interval }
          }
        })
      }
      if (r.log_format === 'atak') {
        const gids = new Set((r.atak_messages || []).map(m => m.sender_gid).filter(Boolean))
        gids.forEach(gid => { if (!seen[gid]) seen[gid] = { callsign: `GID ${gid}`, gid: String(gid) } })
      }
    })
    return Object.values(seen)
  }, [results])

  return (
    <div>
      <SectionHeader icon="📅" title="Session Timeline" sub="Active windows per logging device" />
      <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: 16, marginBottom: 16 }}>
        {results.map((r, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
            <div style={{ width: 150, fontFamily: 'var(--mono)', fontSize: 9, color: PALETTE[i % PALETTE.length], flexShrink: 0 }}>
              {r.device?.callsign || r.source_filename?.slice(0, 16)}
            </div>
            <div style={{ flex: 1, height: 24, background: 'var(--bg)', borderRadius: 3, position: 'relative' }}>
              <div style={{ position: 'absolute', inset: 0, background: `linear-gradient(90deg,${PALETTE[i%PALETTE.length]}50,${PALETTE[i%PALETTE.length]}25)`, borderRadius: 3, border: `1px solid ${PALETTE[i%PALETTE.length]}40`, display: 'flex', alignItems: 'center', padding: '0 10px' }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: PALETTE[i % PALETTE.length] }}>
                  {r.session_start?.slice(0, 16)} → {r.session_end?.slice(0, 16)}
                  {r.session_gaps?.length > 0 && <span style={{ color: C.yellow, marginLeft: 8 }}>{r.session_gaps.length} gap{r.session_gaps.length > 1 ? 's' : ''}</span>}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <SectionHeader icon="📊" title="Messages Received by Device" sub="PLI vs chat breakdown" />
      <ChartPanel results={results} selectedPoints={['pli_vs_chat']} />

      {allOriginators.length > 0 && (
        <>
          <SectionHeader icon="📡" title="Network Participants" sub={`${allOriginators.length} unique originators observed`} />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 6 }}>
            {allOriginators.map((o, i) => (
              <div key={i} style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderLeft: `3px solid ${C.muted}`, borderRadius: 5, padding: '8px 10px' }}>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: '#c8ddf4', fontWeight: 700 }}>{o.callsign}</div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.dim }}>{o.gid}{o.pli ? ` · PLI ${o.pli}` : ''}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function PliTab({ results }) {
  const pliNodes = useMemo(() => {
    const nodeMap = {}
    results.forEach(r => {
      r.received_messages?.forEach(m => {
        if (!m.originator_callsign) return
        if (!nodeMap[m.originator_gid]) nodeMap[m.originator_gid] = { callsign: m.originator_callsign, gid: m.originator_gid, intervals: new Set() }
        if (m.originator_pli_interval) nodeMap[m.originator_gid].intervals.add(m.originator_pli_interval)
      })
    })
    return Object.values(nodeMap).sort((a, b) => a.callsign.localeCompare(b.callsign))
  }, [results])

  const hasDiag = results.some(r => r.log_format === 'diagnostic')

  return (
    <div>
      <SectionHeader icon="📶" title="Originator PLI — All Network Nodes" sub="Dominant PLI rate per observed node" />
      {!hasDiag && <Note>PLI interval data is available in diagnostic logs only. Upload a goTenna Pro+ diagnostic log (.txt) to see PLI frequency data.</Note>}
      {pliNodes.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 6 }}>
          {pliNodes.map((node, i) => {
            const changing = node.intervals.size > 1
            return (
              <div key={i} style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderLeft: `3px solid ${changing ? C.red : C.green}`, borderRadius: 5, padding: '8px 10px', display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: '#c8ddf4', fontWeight: 700 }}>{node.callsign}</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.dim }}>{node.gid}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 14, fontWeight: 700, color: changing ? C.yellow : C.green }}>{[...node.intervals].join(' / ')}</div>
                  {changing && <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.red }}>⚠ changing</div>}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function TxRxTab({ results }) {
  return (
    <div>
      <SectionHeader icon="📤" title="Sent vs Received" sub="App-reported cumulative totals" />
      <ChartPanel results={results} selectedPoints={['chat_sent_recv', 'atak_sent_vs_received']} />
      <SectionHeader icon="📦" title="Message Types Breakdown" />
      <ChartPanel results={results} selectedPoints={['atak_message_types']} />
      <SectionHeader icon="✅" title="TX Outcomes (RSDK only)" sub="Unicast ACK / NACK / Timeout" />
      <ChartPanel results={results} selectedPoints={['tx_outcomes']} />
      <SectionHeader icon="⚠️" title="Partially Received (ATAK only)" />
      <ChartPanel results={results} selectedPoints={['atak_partial_received']} />
    </div>
  )
}

function SessionsTab({ results }) {
  const hasDiag = results.some(r => r.log_format === 'diagnostic')
  return (
    <div>
      <SectionHeader icon="📱" title="App Version" sub="From Device & Application Info block or ATAK app launch record" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 8, marginBottom: 16 }}>
        {results.map((r, i) => (
          <div key={i} style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6, padding: '12px 14px' }}>
            <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 14, fontWeight: 700, color: PALETTE[i % PALETTE.length], marginBottom: 8 }}>{r.device?.callsign || r.source_filename}</div>
            {[['Format', r.log_format?.toUpperCase()], ['App', r.device?.app_version], ['Build', r.device?.build_number], ['Platform', r.device?.platform?.toUpperCase()], ['Model', r.device?.device_model], ['Radio FW', r.device?.radio_firmware], ['Serial', r.device?.radio_serial]].map(([label, val]) => val ? (
              <div key={label} style={{ fontFamily: 'var(--mono)', fontSize: 8, marginBottom: 2 }}>
                <span style={{ color: C.muted }}>{label}: </span><span style={{ color: '#c8ddf4' }}>{val}</span>
              </div>
            ) : null)}
          </div>
        ))}
      </div>
      {hasDiag && (
        <>
          <SectionHeader icon="⚠️" title="App Crash Detection" sub="Diagnostic log format v1 — no explicit crash markers present" />
          <Note>
            The goTenna Pro+ diagnostic log does not record crashes directly. No stack traces or lifecycle events are present.<br /><br />
            <strong style={{ color: '#c8ddf4' }}>Crash proxy indicators:</strong> Timestamp gaps &gt;30 min = app closed or backgrounded. One Device &amp; Application Info block per file = single launch session. Gaps in 5-minute System Information polling = app not in foreground.
          </Note>
        </>
      )}
      <SectionHeader icon="⏱" title="Active Session Lengths" />
      <ChartPanel results={results} selectedPoints={['session_lengths']} />
    </div>
  )
}

function ThermalTab({ results }) {
  return (
    <div>
      <SectionHeader icon="🌡️" title="PA Temperature Over Time (°F)" sub="Yellow threshold 113°F · Red threshold 131°F" />
      <ChartPanel results={results} selectedPoints={['temp_over_time']} />
      <SectionHeader icon="🔥" title="Peak Temperature by Device" />
      <ChartPanel results={results} selectedPoints={['temp_peak']} />
    </div>
  )
}

function BatteryTab({ results }) {
  return (
    <div>
      <SectionHeader icon="🔋" title="Battery Level Over Time" sub="Red threshold at 30%" />
      <ChartPanel results={results} selectedPoints={['battery_over_time']} />
      <SectionHeader icon="📉" title="Minimum Battery Recorded" />
      <ChartPanel results={results} selectedPoints={['battery_min']} />
    </div>
  )
}

function HopsTab({ results }) {
  const hasRsdk = results.some(r => r.log_format === 'rsdk')
  return (
    <div>
      <SectionHeader icon="🔁" title="Hop Count Distribution" sub="Diagnostic and ATAK logs only — RSDK hop count is not genuine RF routing data" />
      {hasRsdk && <Note>⚠ RSDK logs are present but excluded — hop count in RSDK format does not reflect real RF mesh routing.</Note>}
      <ChartPanel results={results} selectedPoints={['hop_distribution']} />
      <SectionHeader icon="📊" title="Average Hop Count per Device" />
      <ChartPanel results={results} selectedPoints={['hop_avg']} />
    </div>
  )
}

function RssiTab({ results }) {
  return (
    <div>
      <SectionHeader icon="📡" title="RSSI by Hop Count" sub="Real dBm — diagnostic format stores as unsigned byte (value − 256)" />
      <ChartPanel results={results} selectedPoints={['rssi_by_hop']} />
      <SectionHeader icon="📶" title="Average RSSI per Device" />
      <ChartPanel results={results} selectedPoints={['rssi_avg_device']} />
      <Note>Diagnostic RSSI stored as unsigned byte (137–237). Real dBm = value − 256 (−119 to −19 dBm). ATAK RSSI values are already signed dBm. Sent-message RSSI (always 0) is excluded.</Note>
    </div>
  )
}

function ChatTab({ results }) {
  return (
    <div>
      <SectionHeader icon="💬" title="Chat / Map Message Split" />
      <ChartPanel results={results} selectedPoints={['pli_vs_chat']} />
      <SectionHeader icon="📊" title="TX Outcomes" sub="RSDK logs only" />
      <ChartPanel results={results} selectedPoints={['tx_outcomes']} />
    </div>
  )
}

function HealthTab({ results }) {
  return (
    <div>
      <SectionHeader icon="💊" title="Per-Device Health Score" sub="Composite score — Alpha · Dimensions TBD" />
      <Note>⚠ Health Score dimensions are not yet fully defined. This is a placeholder composite score.</Note>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
        {results.map((r, i) => {
          const s = r.summary || {}
          const checks = [(s.peak_temp_f || 0) < 113, (s.min_battery_pct || 100) > 30, !s.ble_fail_count, (s.avg_hop_count || 99) < 4]
          const score = checks.filter(Boolean).length
          const color = score >= 3 ? C.green : score >= 2 ? C.yellow : C.red
          return (
            <div key={i} style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: 20, textAlign: 'center' }}>
              <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 13, color: PALETTE[i % PALETTE.length], marginBottom: 12 }}>{r.device?.callsign || r.source_filename}</div>
              <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 52, fontWeight: 700, color, lineHeight: 1 }}>{score}<span style={{ fontSize: 20, color: C.muted }}>/4</span></div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, marginTop: 8 }}>Thermal · Battery · BLE · Hops</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function AtakTab({ results }) {
  const atakResults = results.filter(r => r.log_format === 'atak')
  if (atakResults.length === 0) return <Note>No ATAK logs loaded. Upload an ATAK plug-in .log file to see this tab.</Note>
  const totalClockSkew = atakResults.reduce((n, r) => n + (r.summary?.negative_delivery_time_count || 0), 0)

  return (
    <div>
      <SectionHeader icon="🗺️" title="Message Delivery Status" sub="Breakdown across all ATAK messages" />
      <ChartPanel results={atakResults} selectedPoints={['atak_delivery_status']} />

      <SectionHeader icon="📨" title="Message Types" sub="PLI · Chat · Map Objects · File Transfers" />
      <ChartPanel results={atakResults} selectedPoints={['atak_message_types']} />

      <SectionHeader icon="📡" title="Connection State Over Time" sub="CONNECTED vs CONNECTING health samples" />
      <ChartPanel results={atakResults} selectedPoints={['atak_connection_state']} />

      <SectionHeader icon="🗓️" title="Device Events Timeline" sub="Connect · Disconnect · Power · PLI · Frequency changes" />
      <ChartPanel results={atakResults} selectedPoints={['atak_events_timeline']} />

      {atakResults.some(r => (r.summary?.partially_received || 0) > 0) && (
        <>
          <SectionHeader icon="⚠️" title="Partially Received Messages" />
          <ChartPanel results={atakResults} selectedPoints={['atak_partial_received']} />
        </>
      )}

      {atakResults.some(r => (r.atak_app_launches?.length || 0) > 1) && (
        <>
          <SectionHeader icon="🔄" title="App Launches" sub="Regular ATAK logs accumulate across multiple launches" />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 8 }}>
            {atakResults.flatMap(r => (r.atak_app_launches || []).map((a, i) => (
              <div key={i} style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6, padding: '10px 14px' }}>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted }}>Launch {i + 1}</div>
                <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 13, color: C.accent }}>{a.launch_timestamp?.slice(0, 16)}</div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.dim, marginTop: 3 }}>v{a.app_version} · ATAK {a.atak_version}</div>
              </div>
            )))}
          </div>
        </>
      )}

      <Note>
        ⚠ Callsign and UUID fields are always empty in ATAK log format — identity is GID-only.
        {totalClockSkew > 0 && ` ${totalClockSkew} records have negative delivery times due to clock skew between devices (most common at hop counts 3–4).`}
      </Note>
    </div>
  )
}

// ── Tab content router ────────────────────────────────────────────────────────

function TabContent({ tab, results }) {
  switch (tab) {
    case 'overview':  return <OverviewTab  results={results} />
    case 'pli':       return <PliTab       results={results} />
    case 'txrx':      return <TxRxTab      results={results} />
    case 'sessions':  return <SessionsTab  results={results} />
    case 'thermal':   return <ThermalTab   results={results} />
    case 'battery':   return <BatteryTab   results={results} />
    case 'hops':      return <HopsTab      results={results} />
    case 'rssi':      return <RssiTab      results={results} />
    case 'chat':      return <ChatTab      results={results} />
    case 'health':    return <HealthTab    results={results} />
    case 'atak':      return <AtakTab      results={results} />
    default:          return null
  }
}

// ── Device filter button style ────────────────────────────────────────────────

function deviceBtnStyle(active, color = '#00d4ff') {
  return {
    background: active ? `${color}20` : 'none',
    border: `1px solid ${active ? color : '#1e2f4a'}`,
    color: active ? color : '#4a6080',
    borderRadius: 4, padding: '4px 11px', cursor: 'pointer',
    fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.06em',
    textTransform: 'uppercase', transition: 'all 0.1s',
  }
}

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  const { results, loading, error, parseFiles, clearResults } = useLogData()
  const [activeTab, setActiveTab] = useState('overview')
  const [activeDevice, setActiveDevice] = useState(null)

  const hasResults    = results.length > 0
  const activeResults = activeDevice !== null ? [results[activeDevice]] : results
  const visibleTabs   = TABS.filter(t => !t.atakOnly || results.some(r => r.log_format === 'atak'))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header style={{
        padding: '14px 36px', borderBottom: '1px solid var(--border2)', flexShrink: 0,
        background: 'linear-gradient(180deg,#08111f 0%,transparent 100%)',
        backgroundImage: 'repeating-linear-gradient(90deg,transparent,transparent 40px,#ffffff03 40px,#ffffff03 41px)',
        display: 'flex', alignItems: 'center', gap: 20,
      }}>
        <div>
          <div style={{ fontSize: 9, fontFamily: 'var(--mono)', color: C.muted, letterSpacing: '0.15em', textTransform: 'uppercase', marginBottom: 2 }}>goTenna Mesh · Log Analysis</div>
          <div style={{ fontSize: 26, fontWeight: 800, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#e8f4ff', fontFamily: "'Barlow Condensed',sans-serif" }}>
            Log <span style={{ color: 'var(--accent)' }}>Analyzer</span>
          </div>
        </div>

        {hasResults && (
          <>
            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginLeft: 16 }}>
              <button onClick={() => setActiveDevice(null)} style={deviceBtnStyle(activeDevice === null)}>All</button>
              {results.map((r, i) => {
                const filename = r.source_filename?.replace(/\.[^.]+$/, '') || '?'
                return (
                  <button key={i} onClick={() => setActiveDevice(activeDevice === i ? null : i)} style={{ ...deviceBtnStyle(activeDevice === i, PALETTE[i % PALETTE.length]), maxWidth: 300, textAlign: 'left' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      <span style={{ fontSize: 9, letterSpacing: '0.04em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 280 }}>
                        {filename}
                      </span>
                      <span style={{ opacity: 0.5, fontSize: 8, fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                        {r.log_format}
                      </span>
                    </div>
                  </button>
                )
              })}
            </div>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
              <FileUpload onFiles={parseFiles} loading={loading} error={null} variant="header" />
              <button onClick={() => { clearResults(); setActiveDevice(null); setActiveTab('overview') }}
                style={{ background: 'none', border: '1px solid var(--border2)', color: C.muted, borderRadius: 4, padding: '5px 12px', cursor: 'pointer', fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                Clear
              </button>
            </div>
          </>
        )}
      </header>

      {/* ── Upload ──────────────────────────────────────────────────────── */}
      {!hasResults ? (
        <main style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
          <FileUpload onFiles={parseFiles} loading={loading} error={error} variant="page" />
        </main>
      ) : (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

          {/* KPI row */}
          <KpiRow results={activeResults} />

          {/* Tab bar */}
          <div style={{ display: 'flex', gap: 0, padding: '0 36px', borderBottom: '1px solid var(--border)', background: 'var(--bg2)', flexShrink: 0, flexWrap: 'wrap', alignItems: 'center' }}>
            {visibleTabs.map(t => (
              <button key={t.id} onClick={() => setActiveTab(t.id)} style={{
                background: 'none', border: 'none', cursor: 'pointer',
                padding: '10px 16px 12px',
                fontFamily: "'Barlow Condensed',sans-serif", fontSize: 13, fontWeight: 600,
                letterSpacing: '0.06em', textTransform: 'uppercase',
                color: activeTab === t.id ? 'var(--accent)' : C.muted,
                borderBottom: `2px solid ${activeTab === t.id ? 'var(--accent)' : 'transparent'}`,
                marginBottom: -1, transition: 'color 0.15s, border-color 0.15s',
              }}>
                {t.label}
                {t.atakOnly && <span style={{ marginLeft: 4, fontSize: 8, color: C.yellow, fontFamily: 'var(--mono)' }}>α</span>}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '4px 36px 32px' }}>
            <TabContent tab={activeTab} results={activeResults} />
          </div>

        </div>
      )}
    </div>
  )
}
