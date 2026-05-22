import React, { useState, useMemo, useCallback } from 'react'
import FileUpload, { ParsingOverlay } from './components/FileUpload.jsx'
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

function KpiCard({ label, value, sub, color = C.accent, tooltip = null }) {
  const [hover, setHover] = React.useState(false)
  return (
    <div
      onMouseEnter={() => tooltip && setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6, padding: '10px 16px', minWidth: 110, position: 'relative', overflow: 'visible', cursor: tooltip ? 'default' : undefined }}
    >
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 2, background: color, borderRadius: '6px 0 0 6px' }} />
      <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>{label}</div>
      <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 22, fontWeight: 700, color, lineHeight: 1 }}>{value ?? '—'}</div>
      {sub && <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.dim, marginTop: 3 }}>{sub}</div>}
      {tooltip && hover && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, marginTop: 6, zIndex: 50,
          background: '#0d1428', border: '1px solid var(--border2)',
          borderRadius: 6, padding: '8px 12px', minWidth: 160, maxWidth: 260,
          boxShadow: '0 8px 24px #000a',
        }}>
          {tooltip.map((item, i) => (
            <div key={i} style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#c8ddf4', padding: '2px 0', borderBottom: i < tooltip.length - 1 ? '1px solid var(--border)' : 'none' }}>
              {item}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── KPI row ───────────────────────────────────────────────────────────────────

function KpiRow({ results }) {
  // Hop counts — diagnostic and ATAK only (RSDK excluded — not genuine RF data)
  const allHops = results.flatMap(r => {
    if (r.log_format === 'atak') return (r.atak_messages || []).filter(m => !m.is_sender && m.hop_count).map(m => m.hop_count)
    if (r.log_format === 'diagnostic') return (r.received_messages || []).map(m => m.hop_count).filter(Boolean)
    return [] // RSDK excluded
  })
  const avgHops = allHops.length ? (allHops.reduce((a, b) => a + b, 0) / allHops.length).toFixed(1) : null
  const hopSub  = allHops.length ? 'diagnostic + ATAK only' : 'n/a for RSDK logs'

  // Peak temp
  const peakTempF  = Math.max(0, ...results.map(r => r.summary?.peak_temp_f || 0))
  const peakDevice = results.find(r => r.summary?.peak_temp_f === peakTempF)

  // Network nodes — per format
  const nodeCount = new Set(results.flatMap(r => {
    if (r.log_format === 'atak')       return (r.atak_messages || []).map(m => m.sender_gid).filter(Boolean).map(String)
    if (r.log_format === 'diagnostic') return (r.received_messages || []).map(m => m.originator_gid).filter(Boolean)
    if (r.log_format === 'rsdk')       return Object.keys(r.contacts || {}) // unique peer UUIDs
    return []
  })).size

  const nodeSub = results.every(r => r.log_format === 'rsdk')
    ? 'Unique peers (ContactManager)'
    : 'Unique GIDs / peers observed'

  // Chat — diagnostic uses message_count_snapshots, RSDK has no chat counter, ATAK uses atak_messages
  const totalChat = results.reduce((n, r) => {
    if (r.log_format === 'diagnostic') return n + (r.summary?.chat_count || 0)
    if (r.log_format === 'atak')       return n + (r.summary?.chat_count || 0)
    return n // RSDK has no reliable chat counter
  }, 0)
  const chatSub = results.some(r => r.log_format === 'rsdk') && results.every(r => r.log_format === 'rsdk')
    ? 'not available in RSDK format'
    : 'received across all devices'

  // PLI Changers + Avg PLI Rate — diagnostic only
  const { pliChangers, avgPliRate } = (() => {
    const nodeIntervalCounts = {}  // gid -> { interval -> count }
    results.forEach(r => {
      if (r.log_format !== 'diagnostic') return
      ;(r.received_messages || []).forEach(m => {
        if (!m.originator_gid || !m.originator_pli_interval || m.originator_pli_interval === 'N/A') return
        if (!nodeIntervalCounts[m.originator_gid]) nodeIntervalCounts[m.originator_gid] = {}
        const iv = m.originator_pli_interval
        nodeIntervalCounts[m.originator_gid][iv] = (nodeIntervalCounts[m.originator_gid][iv] || 0) + 1
      })
    })

    const gids    = Object.keys(nodeIntervalCounts)
    const total   = gids.length
    const changed = gids.filter(g => Object.keys(nodeIntervalCounts[g]).length > 1).length

    // Avg PLI rate: median of each node's dominant interval
    const parseSec = s => { const m = s?.match(/^(\d+)/); return m ? parseInt(m[1], 10) : null }
    const dominantSecs = gids.map(g => {
      const counts = nodeIntervalCounts[g]
      const dom    = Object.entries(counts).sort((a,b) => b[1]-a[1])[0]?.[0]
      return parseSec(dom)
    }).filter(Boolean).sort((a,b) => a-b)

    const medianSec = dominantSecs.length
      ? dominantSecs[Math.floor(dominantSecs.length / 2)]
      : null

    // Count high-freq nodes (≤30s)
    const highFreqCount = dominantSecs.filter(s => s <= 30).length

    const label = medianSec != null
      ? (medianSec >= 60 ? `${medianSec / 60}m` : `${medianSec}s`)
      : null

    return {
      pliChangers: { changed, total },
      avgPliRate:  { label, medianSec, highFreqCount, nodeCount: total },
    }
  })()

  // Firmware
  const firmwares = [...new Set(results.map(r => r.device?.radio_firmware).filter(Boolean))]

  // App versions
  const appVersions = [...new Set(results.map(r => {
    const v = r.device?.app_version
    const b = r.device?.build_number
    return v ? (b ? `${v} (${b})` : v) : null
  }).filter(Boolean))]

  const appVersionTooltip = results.map(r => {
    const name = r.device?.callsign || r.source_filename?.replace(/\.[^.]+$/, '')
    const v    = r.device?.app_version
    const b    = r.device?.build_number
    const plat = r.device?.platform?.toUpperCase()
    return v ? `${name}  ·  v${v}${b ? ` (${b})` : ''}${plat ? `  ·  ${plat}` : ''}` : `${name}  ·  n/a`
  })

  // Device tooltip list — one entry per log
  const deviceTooltip = results.map(r => {
    const name = r.device?.callsign ||
      (r.log_format === 'rsdk' ? (r.summary?.contact_names?.[0] || r.source_filename?.replace(/\.[^.]+$/, '')) : r.source_filename?.replace(/\.[^.]+$/, ''))
    const fmt  = r.log_format?.toUpperCase()
    const fw   = r.device?.radio_firmware
    return `${name}  ·  ${fmt}${fw ? `  ·  ${fw}` : ''}`
  })

  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', padding: '12px 36px', borderBottom: '1px solid var(--border2)', background: 'rgba(5,8,15,0.75)', flexShrink: 0, backdropFilter: 'blur(4px)' }}>
      <KpiCard label="Devices Logged"  value={results.length} sub="hover for details" tooltip={deviceTooltip} />
      <KpiCard label="Network Nodes"   value={nodeCount || '—'} sub={nodeSub} color={C.green} />
      <KpiCard label="Peak Temp"       value={peakTempF ? `${peakTempF}°F` : '—'} sub={peakDevice?.device?.callsign || peakDevice?.source_filename?.slice(0,12)} color={peakTempF >= 131 ? C.red : peakTempF >= 113 ? C.yellow : C.green} />
      <KpiCard label="Avg Hop Count"   value={avgHops ?? '—'} sub={hopSub} color='#ff6b35' />
      <KpiCard label="Radio Firmware"  value={firmwares.join(' / ') || '—'} sub={firmwares.length > 1 ? '⚠ version mismatch' : 'all match'} color={firmwares.length > 1 ? C.red : C.green} />
      <KpiCard
        label="App Version"
        value={appVersions.length === 1 ? appVersions[0] : `${appVersions.length} versions`}
        sub={appVersions.length > 1 ? '⚠ version mismatch' : `${results.length} device${results.length > 1 ? 's' : ''}`}
        color={appVersions.length > 1 ? C.red : C.green}
        tooltip={appVersionTooltip}
      />
      {pliChangers.total > 0 && (
        <KpiCard label="PLI Changers" value={`${pliChangers.changed}/${pliChangers.total}`} sub={pliChangers.changed > 0 ? `${pliChangers.changed} node${pliChangers.changed > 1 ? 's' : ''} changed rate` : 'all stable'} color='#c77dff' />
      )}
      {avgPliRate.label && (
        <KpiCard
          label="Avg PLI Rate"
          value={avgPliRate.label}
          sub={avgPliRate.highFreqCount > 0 ? `⚠ ${avgPliRate.highFreqCount} high-freq node${avgPliRate.highFreqCount > 1 ? 's' : ''} ≤30s` : `median across ${avgPliRate.nodeCount} nodes`}
          color={avgPliRate.medianSec <= 30 ? C.red : avgPliRate.medianSec <= 180 ? C.yellow : C.green}
        />
      )}
      <KpiCard label="Chat Messages"   value={totalChat || '—'} sub={chatSub} />
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
      <KpiRow results={results} />
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

// ── PLI helpers ──────────────────────────────────────────────────────────────

function parsePliSeconds(intervalStr) {
  if (!intervalStr || intervalStr === 'N/A') return null
  const m = String(intervalStr).match(/^(\d+)/)
  return m ? parseInt(m[1], 10) : null
}

function pliColor(sec) {
  if (sec === null) return C.muted
  if (sec <= 30)  return C.red
  if (sec <= 180) return C.yellow
  return C.green
}

function pliLabel(sec) {
  if (sec === null) return 'UNKNOWN'
  if (sec <= 5)   return 'VERY HIGH'
  if (sec <= 15)  return 'CRITICAL'
  if (sec <= 30)  return 'HIGH'
  if (sec <= 180) return 'ELEVATED'
  return 'STANDARD'
}

function dominantInterval(intervalCounts) {
  // Most-frequently-occurring non-N/A interval by message count
  const real = Object.entries(intervalCounts).filter(([k]) => k !== 'N/A')
  if (!real.length) return null
  return real.sort((a, b) => b[1] - a[1])[0][0]
}

// Compute minutes spent at each interval using consecutive-gap method.
// N/A entries (radio temporarily disconnected) are skipped — when the same
// interval appears on both sides of an N/A gap, the gap is bridged and counted
// if it fits within 3× the interval (otherwise the node was silent too long).
function computeIntervalDurations(intervalHistory) {
  if (!intervalHistory.length) return {}
  const toMs = ts => new Date(ts.replace(' ', 'T') + 'Z').getTime()
  const durations = {}

  // Strip N/A entries — work only with real interval messages
  const real = intervalHistory.filter(e => e.interval !== 'N/A')
  if (!real.length) return {}

  for (let i = 1; i < real.length; i++) {
    const prev = real[i - 1]
    const curr = real[i]
    if (prev.interval !== curr.interval) continue  // interval changed — skip gap
    const gapMs  = toMs(curr.ts) - toMs(prev.ts)
    const secVal = parsePliSeconds(prev.interval) || 300
    const capMs  = secVal * 3 * 1000  // bridge N/A gaps up to 3× the interval
    const counted = Math.min(gapMs, capMs)
    durations[prev.interval] = (durations[prev.interval] || 0) + counted / 60000
  }

  // Credit at least one interval period per node seen (floor for single-message nodes)
  for (const { interval } of real) {
    const floor = (parsePliSeconds(interval) || 300) / 60
    if (!durations[interval]) durations[interval] = floor
  }
  return durations
}

const PLI_INTERVAL_ORDER = ['5 seconds','15 seconds','30 seconds','60 seconds','120 seconds','180 seconds','300 seconds']

function PliDurationChart({ pliNodes }) {
  // Only show nodes that have at least one real interval with computed duration
  const chartNodes = pliNodes.filter(n => Object.keys(n.durations).length > 0)
  if (!chartNodes.length) return null

  // All interval keys seen, sorted by seconds ascending
  const allIntervals = [...new Set(chartNodes.flatMap(n => Object.keys(n.durations)))]
    .filter(iv => iv !== 'N/A')
    .sort((a, b) => (parsePliSeconds(a) || 999) - (parsePliSeconds(b) || 999))

  // Bar width per node
  const barH = 22
  const labelW = 110
  const chartW = 560
  const maxMins = Math.max(...chartNodes.flatMap(n => {
    const total = Object.values(n.durations).reduce((a, b) => a + b, 0)
    return [total]
  }), 1)

  return (
    <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: '16px 18px', marginTop: 16 }}>
      <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 14, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: '#c8ddf4', marginBottom: 4 }}>
        Estimated Time per PLI Interval
      </div>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, marginBottom: 14 }}>
        Minutes observed at each interval · computed from consecutive message gaps · capped at 2× interval to exclude silence
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 12 }}>
        {allIntervals.map(iv => {
          const sec = parsePliSeconds(iv)
          const color = pliColor(sec)
          return (
            <div key={iv} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <div style={{ width: 10, height: 10, borderRadius: 2, background: color, opacity: 0.85 }} />
              <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color }}>{iv.replace(' seconds', 's')}</span>
            </div>
          )
        })}
      </div>

      {/* Bars */}
      <div style={{ overflowX: 'auto' }}>
        {chartNodes.map((node, i) => {
          const total = Object.values(node.durations).reduce((a, b) => a + b, 0)
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <div style={{ width: labelW, fontFamily: 'var(--mono)', fontSize: 9, color: '#c8ddf4', textAlign: 'right', flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {node.callsign}
              </div>
              <div style={{ flex: 1, height: barH, display: 'flex', borderRadius: 3, overflow: 'hidden', background: 'var(--bg)', minWidth: 200 }}>
                {allIntervals.map(iv => {
                  const mins = node.durations[iv] || 0
                  if (!mins) return null
                  const pct = (mins / maxMins) * 100
                  const sec = parsePliSeconds(iv)
                  const color = pliColor(sec)
                  return (
                    <div
                      key={iv}
                      title={`${iv}: ${mins.toFixed(1)} min`}
                      style={{
                        width: `${pct}%`, height: '100%',
                        background: color, opacity: 0.8,
                        borderRight: '1px solid var(--bg)',
                        minWidth: mins > 0 ? 2 : 0,
                      }}
                    />
                  )
                })}
              </div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, flexShrink: 0, width: 40 }}>
                {total.toFixed(0)}m
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function PliTab({ results }) {
  const pliNodes = useMemo(() => {
    const nodeMap = {}
    results.forEach(r => {
      r.received_messages?.forEach(m => {
        if (!m.originator_callsign) return
        const gid = m.originator_gid
        if (!nodeMap[gid]) nodeMap[gid] = {
          callsign: m.originator_callsign,
          gid,
          intervalCounts: {},
          intervalHistory: [],
        }
        const iv = m.originator_pli_interval
        const ts = m.receiver_timestamp || m.originator_timestamp || m.timestamp
        if (iv && ts) {
          nodeMap[gid].intervalCounts[iv] = (nodeMap[gid].intervalCounts[iv] || 0) + 1
          nodeMap[gid].intervalHistory.push({ ts, interval: iv })
        }
      })
    })

    return Object.values(nodeMap)
      .map(node => ({
        ...node,
        durations: computeIntervalDurations(
          node.intervalHistory.sort((a, b) => a.ts.localeCompare(b.ts))
        ),
      }))
      .sort((a, b) => a.callsign.localeCompare(b.callsign))
  }, [results])

  const hasDiag = results.some(r => r.log_format === 'diagnostic')

  return (
    <div>
      <SectionHeader icon="📶" title="Originator PLI — All Network Nodes" sub="Dominant PLI rate per observed node · ≤30s = red · 60–180s = yellow · 300s+ = green" />
      {!hasDiag && <Note>PLI interval data is available in diagnostic logs only. Upload a goTenna Pro+ diagnostic log (.txt) to see PLI frequency data.</Note>}
      {hasDiag && pliNodes.length > 0 && (() => {
        const allIvs = [...new Set(pliNodes.flatMap(n => Object.keys(n.intervalCounts).filter(iv => iv !== 'N/A')))]
          .sort((a, b) => (parsePliSeconds(a) || 999) - (parsePliSeconds(b) || 999))
        const has5s = allIvs.some(iv => parsePliSeconds(iv) <= 5)
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 10, padding: '6px 10px', background: 'var(--bg2)', borderRadius: 5, border: '1px solid var(--border)' }}>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted }}>INTERVALS IN LOADED DATA:</span>
            {allIvs.map(iv => {
              const s = parsePliSeconds(iv)
              const c = pliColor(s)
              return <span key={iv} style={{ fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 700, color: c }}>{iv.replace(' seconds', 's')}</span>
            })}
            {!has5s && <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, marginLeft: 8 }}>· no 5s data in loaded files — load RSO_HagenM or Steven logs to see 5s nodes</span>}
          </div>
        )
      })()}
      {pliNodes.length > 0 && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 6 }}>
            {pliNodes.map((node, i) => {
              const realIntervals = Object.keys(node.intervalCounts).filter(iv => iv !== 'N/A')
              const dominant = dominantInterval(node.intervalCounts)
              const domSec   = parsePliSeconds(dominant)
              const color    = pliColor(domSec)
              const label    = pliLabel(domSec)
              const otherIntervals = realIntervals
                .filter(iv => iv !== dominant)
                .sort((a, b) => (parsePliSeconds(a) || 999) - (parsePliSeconds(b) || 999))
              const hasChanges = realIntervals.length > 1

              return (
                <div key={i} style={{
                  background: 'var(--panel)',
                  border: '1px solid var(--border)',
                  borderLeft: `3px solid ${color}`,
                  borderRadius: 5,
                  padding: '10px 12px',
                }}>
                  {/* Top row: callsign + badge */}
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 6 }}>
                    <div>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: '#c8ddf4', fontWeight: 700 }}>{node.callsign}</div>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.dim, marginTop: 1 }}>{node.gid}</div>
                    </div>
                    {hasChanges && (
                      <div style={{
                        fontFamily: 'var(--mono)', fontSize: 8,
                        color: C.red,
                        background: `${C.red}15`,
                        border: `1px solid ${C.red}40`,
                        borderRadius: 3, padding: '2px 7px',
                        whiteSpace: 'nowrap',
                      }}>
                        ⚠ CHANGES
                      </div>
                    )}
                  </div>

                  {/* Dominant interval */}
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 2 }}>
                    <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 28, fontWeight: 700, color, lineHeight: 1 }}>
                      {dominant ? dominant.replace(' seconds', 's') : 'N/A'}
                    </div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color, opacity: 0.8 }}>{label}</div>
                  </div>

                  {/* Msg count */}
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.dim, marginBottom: hasChanges ? 6 : 0 }}>
                    {dominant && node.intervalCounts[dominant] ? `${node.intervalCounts[dominant]} msgs` : ''}
                  </div>

                  {/* Also observed */}
                  {hasChanges && (
                    <div style={{ borderTop: `1px solid ${C.red}25`, paddingTop: 6 }}>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.red, marginBottom: 4, letterSpacing: '0.06em' }}>
                        ALSO OBSERVED
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {otherIntervals.map(iv => {
                          const s = parsePliSeconds(iv)
                          const c = pliColor(s)
                          return (
                            <div key={iv} style={{
                              fontFamily: 'var(--mono)', fontSize: 8,
                              color: c,
                              background: `${c}12`,
                              border: `1px solid ${c}40`,
                              borderRadius: 3, padding: '2px 6px',
                            }}>
                              {iv.replace(' seconds', 's')} · {node.intervalCounts[iv]}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          <PliDurationChart pliNodes={pliNodes} />
        </>
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

// ── Log selector dropdown ─────────────────────────────────────────────────────

function LogSelector({ results, activeDevice, setActiveDevice }) {
  const [open, setOpen] = React.useState(false)

  const activeLabel = activeDevice === null
    ? `All Logs (${results.length})`
    : results[activeDevice]?.source_filename?.replace(/\.[^.]+$/, '') || `Log ${activeDevice + 1}`

  const activeColor = activeDevice === null ? '#00d4ff' : PALETTE[activeDevice % PALETTE.length]

  return (
    <div style={{ position: 'relative', marginLeft: 16 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          background: `${activeColor}15`, border: `1px solid ${activeColor}50`,
          color: activeColor, borderRadius: 5, padding: '6px 14px',
          cursor: 'pointer', fontFamily: 'var(--mono)',
          fontSize: 9, letterSpacing: '0.06em', textTransform: 'uppercase',
          display: 'flex', alignItems: 'center', gap: 8,
          minWidth: 180, maxWidth: 320,
        }}
      >
        <span style={{ flex: 1, textAlign: 'left', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {activeLabel}
        </span>
        <span style={{ opacity: 0.6, fontSize: 8, flexShrink: 0 }}>{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <>
          <div onClick={() => setOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 49 }} />
          <div style={{
            position: 'absolute', top: '100%', left: 0, marginTop: 4,
            background: 'var(--panel)', border: '1px solid var(--border2)',
            borderRadius: 6, zIndex: 50, minWidth: 280, maxWidth: 420,
            boxShadow: '0 8px 32px #000a',
            maxHeight: '60vh', overflowY: 'auto',
          }}>
            <button
              onClick={() => { setActiveDevice(null); setOpen(false) }}
              style={{
                width: '100%', textAlign: 'left',
                background: activeDevice === null ? '#00d4ff15' : 'none',
                border: 'none', borderBottom: '1px solid var(--border)',
                color: activeDevice === null ? '#00d4ff' : 'var(--text)',
                padding: '10px 14px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 10,
              }}
            >
              <span style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                All Logs
              </span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--muted)', marginLeft: 'auto' }}>
                {results.length} files
              </span>
            </button>

            {results.map((r, i) => {
              const filename = r.source_filename?.replace(/\.[^.]+$/, '') || `Log ${i + 1}`
              const color = PALETTE[i % PALETTE.length]
              const isActive = activeDevice === i
              return (
                <button
                  key={i}
                  onClick={() => { setActiveDevice(isActive ? null : i); setOpen(false) }}
                  style={{
                    width: '100%', textAlign: 'left',
                    background: isActive ? `${color}15` : 'none',
                    border: 'none',
                    borderBottom: i < results.length - 1 ? '1px solid var(--border)' : 'none',
                    color: isActive ? color : 'var(--text)',
                    padding: '10px 14px', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 10,
                  }}
                >
                  <div style={{ width: 6, height: 6, borderRadius: '50%', background: color, flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.04em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {filename}
                    </div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--muted)', marginTop: 2 }}>
                      {r.log_format?.toUpperCase()} · {r.device?.callsign || r.device?.radio_serial || '—'}
                    </div>
                  </div>
                  {r.parse_errors?.length > 0 && (
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--red)', flexShrink: 0 }}>⚠</span>
                  )}
                </button>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

export default function App() {
  const { results, loading, error, parseFiles, clearResults } = useLogData()
  const [pendingFileCount, setPendingFileCount] = useState(0)
  const [timeWindow, setTimeWindow] = useState(null)  // null = full range; {startMs, endMs}

  const handleParseFiles = useCallback((files, window = null) => {
    setPendingFileCount(files.length)
    setTimeWindow(window)
    parseFiles(files)
  }, [parseFiles])
  const [activeTab, setActiveTab] = useState('overview')
  const [activeDevice, setActiveDevice] = useState(null)

  const hasResults = results.length > 0

  // Apply time window filter and recompute summaries from filtered arrays
  const filteredResults = React.useMemo(() => {
    if (!timeWindow || !results.length) return results
    const { startMs, endMs } = timeWindow

    const inWindow = ts => {
      if (!ts) return true
      const ms = new Date(ts.replace(' ', 'T') + (ts.includes('Z') ? '' : 'Z')).getTime()
      return ms >= startMs && ms <= endMs
    }

    const avg  = arr => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null
    const rnd  = (v, d = 2) => v != null ? +v.toFixed(d) : null
    const cToF = c => c != null ? Math.round(c * 9 / 5 + 32) : null

    return results.map(r => {
      const msgs    = (r.received_messages  || []).filter(m => inWindow(m.timestamp))
      const samples = (r.system_samples     || []).filter(s => inWindow(s.timestamp))
      const bleEvts = (r.ble_fail_events    || []).filter(b => inWindow(b.timestamp))
      const txEvts  = (r.tx_events          || []).filter(t => inWindow(t.timestamp))
      const atakMsg = (r.atak_messages      || []).filter(m => inWindow(m.timestamp))
      const atakHlth= (r.atak_health_samples|| []).filter(h => inWindow(h.timestamp))

      // Recompute summary fields that derive from the filtered arrays
      const hops     = msgs.map(m => m.hop_count).filter(Boolean)
      const temps    = samples.map(s => s.pa_temp_c).filter(v => v != null && v > 0)
      const batts    = samples.map(s => s.battery_pct).filter(v => v != null && v >= 0)
      const peakC    = temps.length  ? Math.max(...temps) : null
      const atakRx   = atakMsg.filter(m => !m.is_sender)
      const rssiVals = atakRx.map(m => m.rssi).filter(v => v != null && v !== 0)

      const recomputed = r.log_format === 'atak' ? {
        total_messages:               atakMsg.length,
        pli_count:                    atakMsg.filter(m => m.message_type === 'pli').length,
        chat_count:                   atakMsg.filter(m => m.message_type === 'textChat').length,
        sent_count:                   atakMsg.filter(m =>  m.is_sender).length,
        received_count:               atakRx.length,
        unique_sender_gids:           new Set(atakMsg.map(m => m.sender_gid).filter(Boolean)).size,
        avg_hop_count:                rnd(avg(atakRx.map(m => m.hop_count).filter(Boolean))),
        max_hop_count:                atakRx.map(m => m.hop_count).filter(Boolean).reduce((a,b)=>Math.max(a,b), null),
        avg_rssi:                     rnd(avg(rssiVals), 1),
        peak_temp_c:                  peakC,
        peak_temp_f:                  cToF(peakC),
        min_battery_pct:              atakHlth.map(h=>h.battery_pct).filter(v=>v!=null&&v>=0).reduce((a,b)=>Math.min(a,b), null) ?? null,
        partially_received:           atakMsg.filter(m => m.delivery_status === 'PARTIALLY_RECEIVED').length,
        negative_delivery_time_count: atakMsg.filter(m => m.delivery_time_ms != null && m.delivery_time_ms < 0).length,
        // static — unchanged
        session_count:    r.summary?.session_count,
      } : {
        total_messages:     msgs.length,
        pli_count:          msgs.filter(m => m.message_type === 'location').length,
        chat_count:         msgs.filter(m => m.message_type === 'text').length,
        unique_originators: new Set(msgs.map(m => m.originator_gid).filter(Boolean)).size,
        avg_hop_count:      rnd(avg(hops)),
        max_hop_count:      hops.length ? Math.max(...hops) : null,
        peak_temp_c:        peakC,
        peak_temp_f:        cToF(peakC),
        min_battery_pct:    batts.length ? Math.min(...batts) : null,
        ble_fail_count:     bleEvts.length,
        tx_final_ack:       txEvts.filter(t => t.outcome === 'final_ack').length,
        tx_nack:            txEvts.filter(t => t.outcome === 'nack').length,
        tx_timeout:         txEvts.filter(t => t.outcome === 'timeout').length,
        // static — unchanged by time filter
        session_count:      r.summary?.session_count,
        final_chat_sent:    r.summary?.final_chat_sent,
        final_chat_recv:    r.summary?.final_chat_recv,
        contact_count:      r.summary?.contact_count,
        contact_names:      r.summary?.contact_names,
      }

      return {
        ...r,
        received_messages:    msgs,
        system_samples:       samples,
        ble_fail_events:      bleEvts,
        tx_events:            txEvts,
        atak_messages:        atakMsg,
        atak_health_samples:  atakHlth,
        summary: { ...r.summary, ...recomputed },
      }
    })
  }, [results, timeWindow])

  // Deduplicate: same serial + same session window = same log loaded twice
  // Keep the named file over the diagnostic_* numbered filename when there's a clash
  const dedupedResults = React.useMemo(() => {
    const seen = new Map()
    const ordered = []
    for (const r of filteredResults) {
      const key = [
        r.device?.radio_serial || '',
        r.session_start || '',
        r.session_end   || '',
      ].join('|')
      if (!key.replace(/\|/g, '') ) {
        ordered.push(r)  // no identifying info — always include
        continue
      }
      if (!seen.has(key)) {
        seen.set(key, r)
        ordered.push(r)
      }
      // silently drop duplicate
    }
    return ordered
  }, [filteredResults])

  const activeResults = activeDevice !== null ? [dedupedResults[activeDevice]] : dedupedResults
  const visibleTabs   = TABS.filter(t => !t.atakOnly || results.some(r => r.log_format === 'atak'))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      {loading && <ParsingOverlay fileCount={pendingFileCount} />}

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header style={{
        padding: '8px 36px', flexShrink: 0,
        background: 'rgba(5,8,15,0.92)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--border2)',
        display: 'flex', alignItems: 'center', gap: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 18, fontWeight: 700, letterSpacing: '0.06em', color: '#c8ddf4' }}>
            goTenna <span style={{ color: 'var(--accent)' }}>Log Parser</span>
          </div>
        </div>

        {hasResults && (
          <>
            <LogSelector
              results={results}
              activeDevice={activeDevice}
              setActiveDevice={setActiveDevice}
            />
            {timeWindow && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'var(--accent)10', border: '1px solid var(--accent)30', borderRadius: 5, padding: '4px 10px' }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--muted)', letterSpacing: '0.06em' }}>WINDOW</span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--accent)' }}>
                  {new Date(timeWindow.startMs).toISOString().slice(0,16).replace('T',' ')}
                </span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--muted)' }}>→</span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--accent)' }}>
                  {new Date(timeWindow.endMs).toISOString().slice(0,16).replace('T',' ')}
                </span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--muted)' }}>UTC</span>
                <button
                  onClick={() => setTimeWindow(null)}
                  title="Remove time filter"
                  style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 11, lineHeight: 1, padding: '0 2px', marginLeft: 2 }}
                >✕</button>
              </div>
            )}
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
              <FileUpload onFiles={handleParseFiles} loading={loading} error={null} variant="header" />
              <button onClick={() => { clearResults(); setActiveDevice(null); setActiveTab('overview'); setTimeWindow(null) }}
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
          <FileUpload onFiles={handleParseFiles} loading={loading} error={error} variant="page" />
        </main>
      ) : (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

          {/* Tab bar */}
          <div style={{ display: 'flex', gap: 0, padding: '0 36px', borderBottom: '1px solid var(--border2)', background: 'rgba(5,8,15,0.80)', flexShrink: 0, flexWrap: 'wrap', alignItems: 'center', backdropFilter: 'blur(4px)' }}>
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
