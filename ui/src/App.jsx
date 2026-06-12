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
  { id:'relay-health', label:'Relay Health', relayOnly: true },
  { id:'atak',      label:'ATAK', atakOnly: true },
  { id:'fw-log',    label:'FW Log', fwOnly: true },
]

// ── Shared sub-components ─────────────────────────────────────────────────────

function EmptyTabState({ message, detail }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '60vh', gap: 12 }}>
      <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 20, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#2a3a52' }}>
        {message}
      </div>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: C.muted, letterSpacing: '0.04em', maxWidth: 420, textAlign: 'center' }}>
        {detail}
      </div>
    </div>
  )
}

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
  // When all loaded logs are relay_manager format, the standard KPI cards don't
  // apply (no RF messages, PLI, chat, etc.). Show a compact relay summary instead.
  const allRelay = results.length > 0 && results.every(r => r.log_format === 'relay_manager')
  if (allRelay) return <RelayKpiRow results={results} />

  // Hop counts — diagnostic, ATAK, and RSDK via GRIP_Receiver incoming messages
  const allHops = results.flatMap(r => {
    if (r.log_format === 'atak')
      return (r.atak_messages || []).filter(m => !m.is_sender && m.hop_count).map(m => m.hop_count)
    if (r.log_format === 'diagnostic')
      return (r.received_messages || []).map(m => m.hop_count).filter(Boolean)
    if (r.log_format === 'rsdk') {
      // GRIP_Receiver incoming fields lines carry genuine RF hop counts
      return (r.grip_messages || [])
        .filter(g => g.direction === 'incoming' && g.hops != null)
        .map(g => g.hops)
    }
    return []
  })
  const avgHops = allHops.length ? (allHops.reduce((a, b) => a + b, 0) / allHops.length).toFixed(1) : null
  const hasGripHopsKpi = results.some(r => r.log_format === 'rsdk' && (r.grip_messages || []).some(g => g.hops != null))
  const hopSub  = allHops.length
    ? (hasGripHopsKpi ? 'diagnostic + ATAK + GRIP (RSDK)' : 'diagnostic + ATAK only')
    : 'n/a — no hop data in loaded files'

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

function dominantInterval(intervalCounts) {
  // Most-frequently-occurring non-N/A interval by message count
  const real = Object.entries(intervalCounts).filter(([k]) => k !== 'N/A')
  if (!real.length) return null
  return real.sort((a, b) => b[1] - a[1])[0][0]
}

// ── PLI Settings Summary (ATAK) ───────────────────────────────────────────────

function PliSettingsSection({ results }) {
  const atakResults = results.filter(r => r.log_format === 'atak')
  if (!atakResults.length) return null

  // Build per-device PLI setting timeline from atak_events
  const deviceSettings = atakResults.map(r => {
    const callsign = r.device?.callsign || r.source_filename
    const events = (r.atak_events || [])
      .filter(e => e.event_type === 'pliSettingUpdated')
      .sort((a, b) => a.timestamp.localeCompare(b.timestamp))

    if (!events.length) return { callsign, initial: null, changes: [] }

    const toSetting = e => ({
      ts:         e.timestamp?.slice(11, 19) || '—',
      interval:   e.pli_interval_sec,
      isDistance: e.pli_is_distance,
      autoSend:   e.pli_auto_send,
    })

    const initial = toSetting(events[0])
    const changes = events.slice(1).map(toSetting)

    return { callsign, initial, changes }
  }).filter(d => d.initial !== null)

  if (!deviceSettings.length) return null

  const fmtInterval = (interval, isDistance) => {
    if (interval == null) return '—'
    const unit = isDistance ? 'm' : 's'
    return `${interval}${unit}`
  }

  const intervalColor = (interval, isDistance) => {
    if (isDistance) return C.yellow  // distance-based — can't compare directly to time threshold
    if (interval == null) return C.muted
    if (interval < 60) return C.red    // accelerated — highlight per requirement
    if (interval <= 180) return C.yellow
    return C.green
  }

  return (
    <>
      <SectionHeader
        icon="📡"
        title="PLI Settings per Device"
        sub="Session-start setting and mid-session changes · intervals < 60s highlighted red"
      />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 10, marginBottom: 16 }}>
        {deviceSettings.map((d, i) => {
          const iv = d.initial
          const color = intervalColor(iv.interval, iv.isDistance)
          const hasChanges = d.changes.length > 0
          return (
            <div key={i} style={{ background: 'var(--panel)', border: `1px solid var(--border)`, borderLeft: `3px solid ${color}`, borderRadius: 6, padding: '12px 14px' }}>
              {/* Device name */}
              <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 13, color: PALETTE[i % PALETTE.length], marginBottom: 8 }}>
                {d.callsign}
              </div>

              {/* Session-start setting */}
              <div style={{ display: 'flex', gap: 12, marginBottom: hasChanges ? 8 : 0, flexWrap: 'wrap' }}>
                <div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, marginBottom: 2 }}>INTERVAL</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 700, color }}>
                    {fmtInterval(iv.interval, iv.isDistance)}
                    {iv.isDistance && <span style={{ fontSize: 8, color: C.yellow, marginLeft: 4 }}>distance</span>}
                    {!iv.isDistance && iv.interval != null && iv.interval < 60 && <span style={{ fontSize: 8, color: C.red, marginLeft: 4 }}>⚠ accelerated</span>}
                  </div>
                </div>
                <div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, marginBottom: 2 }}>AUTO SEND</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: iv.autoSend ? C.green : C.muted }}>
                    {iv.autoSend ? 'Yes' : 'No'}
                  </div>
                </div>
                <div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, marginBottom: 2 }}>FIRST SEEN</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#94a3b8' }}>{iv.ts}</div>
                </div>
              </div>

              {/* Mid-session changes */}
              {hasChanges && (
                <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8 }}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    Changes during session ({d.changes.length})
                  </div>
                  {d.changes.map((c, j) => {
                    const cc = intervalColor(c.interval, c.isDistance)
                    return (
                      <div key={j} style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 4 }}>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#334155', flexShrink: 0 }}>{c.ts}</span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 700, color: cc }}>
                          {fmtInterval(c.interval, c.isDistance)}
                          {c.isDistance && <span style={{ fontSize: 8, color: C.yellow, marginLeft: 3 }}>dist</span>}
                          {!c.isDistance && c.interval != null && c.interval < 60 && <span style={{ fontSize: 8, color: C.red, marginLeft: 3 }}>⚠</span>}
                        </span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: c.autoSend ? C.green : C.muted }}>
                          auto={c.autoSend ? 'on' : 'off'}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>
      <Note>
        PLI settings from ATAK logs only. Interval &lt; 60s is highlighted red per test requirements.
        Distance-based PLI (meters) is highlighted yellow — cannot be directly compared to time-based intervals.
        deviceDisconnected events do not include serial numbers — see parsing-requirements.md for the LIFO assumption.
      </Note>
    </>
  )
}


function PliTab({ results }) {
  const pliNodes = useMemo(() => {
    const nodeMap = {}
    results.forEach(r => {
      // Diagnostic format — received_messages with originator_pli_interval
      r.received_messages?.forEach(m => {
        if (!m.originator_callsign) return
        const gid = m.originator_gid
        if (!nodeMap[gid]) nodeMap[gid] = {
          callsign: m.originator_callsign,
          gid,
          intervalCounts: {},
        }
        const iv = m.originator_pli_interval
        if (iv) nodeMap[gid].intervalCounts[iv] = (nodeMap[gid].intervalCounts[iv] || 0) + 1
      })
      // ATAK format — infer interval from actual sent PLI message gaps
      // pliSettingUpdated is a config event, not a network transmission —
      // it belongs in PliSettingsSection only, not in message traffic analysis
      if (r.log_format === 'atak') {
        // Extract callsign from filename: drop the 'diagnostic_' and optional
        // 'ATAK_' prefixes, then everything from the GID onward
        const fnCallsign = r.source_filename
          ? r.source_filename.replace(/^diagnostic_/, '').replace(/^ATAK_/, '').replace(/_?\d{10,}_.*$/, '').replace(/_/g, ' ').trim()
          : ''
        const callsign = r.device?.callsign || fnCallsign || r.source_filename
        const gid = r.device?.gid || callsign
        // Use gid+filename as key — two logs can share a GID (same account)
        // CL_B and gt_Sassy_B_Net share GID 90194071247761 in 2026-06-04 session
        const nodeKey = `${gid}|${r.source_filename || callsign}`
        if (!nodeMap[nodeKey]) nodeMap[nodeKey] = { callsign, gid, intervalCounts: {} }
        const sentPli = (r.atak_messages || [])
          .filter(m => m.message_type === 'pli' && m.is_sender && m.timestamp)
          .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
        if (sentPli.length >= 2) {
          const gaps = []
          for (let i = 1; i < sentPli.length; i++) {
            const ms = new Date(sentPli[i].timestamp.replace(' ','T')+'Z').getTime()
                     - new Date(sentPli[i-1].timestamp.replace(' ','T')+'Z').getTime()
            const sec = Math.round(ms / 1000)
            if (sec > 0 && sec < 600) gaps.push(sec)
          }
          if (gaps.length) {
            const common = [15,30,60,120,180,300,600]
            // Bucket each gap with ±25% tolerance — gaps outside tolerance are noise, discarded
            // Then filter intervals with < 1 min estimated duration (count × interval < 60s)
            gaps.forEach(sec => {
              const nearest = common.reduce((a,b)=>Math.abs(b-sec)<Math.abs(a-sec)?b:a)
              // Only assign if gap is within ±25% of the nearest bucket
              if (Math.abs(sec - nearest) / nearest <= 0.25) {
                const iv = `${nearest} seconds`
                nodeMap[nodeKey].intervalCounts[iv] = (nodeMap[nodeKey].intervalCounts[iv] || 0) + 1
              }
            })
            // Remove intervals with < 1 min estimated duration (noise filter)
            Object.keys(nodeMap[nodeKey].intervalCounts).forEach(iv => {
              const sec = parseInt(iv)
              const totalSec = sec * nodeMap[nodeKey].intervalCounts[iv]
              if (totalSec < 60) delete nodeMap[nodeKey].intervalCounts[iv]
            })
            nodeMap[nodeKey].inferred = true
          }
        }
      }
    })

    return Object.values(nodeMap)
      .map(node => ({ ...node }))
      .sort((a, b) => a.callsign.localeCompare(b.callsign))
  }, [results])

  const hasDiag = results.some(r => r.log_format === 'diagnostic')
  const hasAtak = results.some(r => r.log_format === 'atak')
  const hasPliData = hasDiag || hasAtak

  return (
    <div>
      <SectionHeader icon="📶" title="Originator PLI — All Network Nodes" sub="Dominant PLI rate per observed node · ≤30s = red · 60–180s = yellow · 300s+ = green" />
      {!hasPliData && <Note>PLI interval data is available in diagnostic and ATAK enhanced logs. Upload a goTenna Pro+ diagnostic log (.txt) or ATAK diagnostic log to see PLI frequency data.</Note>}
      {hasPliData && pliNodes.length > 0 && (() => {
        const allIvs = [...new Set(pliNodes.flatMap(n => Object.keys(n.intervalCounts).filter(iv => iv !== 'N/A')))]
          .sort((a, b) => (parsePliSeconds(a) || 999) - (parsePliSeconds(b) || 999))
        const has5s = allIvs.some(iv => parsePliSeconds(iv) <= 5)
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 10, padding: '6px 10px', background: 'var(--bg2)', borderRadius: 5, border: '1px solid var(--border)' }}>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted }}>INTERVALS IN LOADED DATA:</span>
            {allIvs.filter(iv => !iv.includes('meters')).map(iv => {
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
              // Card left-border color is keyed to the dominant (most-counted) interval
              const domSec   = parsePliSeconds(dominantInterval(node.intervalCounts))
              const color    = pliColor(domSec)
              const hasChanges = realIntervals.length > 1

              // Duration: count × interval_sec → h/m
              const fmtDur = (iv, count) => {
                const sec = parsePliSeconds(iv)
                if (!sec || !count) return '—'
                const t = sec * count
                const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60)
                return h > 0 ? `${h}h ${m}m` : `${m}m`
              }
              return (
                <div key={i} style={{
                  background: 'var(--panel)',
                  border: '1px solid var(--border)',
                  borderLeft: `3px solid ${color}`,
                  borderRadius: 5,
                  padding: '10px 12px',
                  minHeight: 140,
                }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: '#c8ddf4', fontWeight: 700 }}>{node.callsign}</div>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.dim, marginTop: 1 }}>{node.gid}</div>
                    </div>
                    {hasChanges && (
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.yellow, background: `${C.yellow}15`, border: `1px solid ${C.yellow}40`, borderRadius: 3, padding: '2px 7px', whiteSpace: 'nowrap' }}>
                        ⚠ MIXED
                      </div>
                    )}
                  </div>
                  {realIntervals.filter(iv => !iv.includes('meters')).map(iv => {
                    const ivSec = parsePliSeconds(iv)
                    const ivColor = pliColor(ivSec)
                    const cnt = node.intervalCounts[iv] || 0
                    return (
                      <div key={iv} style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
                        <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 22, fontWeight: 700, color: ivColor, lineHeight: 1, minWidth: 52 }}>
                          {iv.replace(' seconds', 's')}
                        </span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#94a3b8' }}>
                          {fmtDur(iv, cnt)}
                        </span>
                        {ivSec !== null && ivSec < 60 && (
                          <span style={{ fontFamily: 'var(--mono)', fontSize: 7, color: C.red }}>⚠ accelerated</span>
                        )}
                      </div>
                    )
                  })}
                </div>
              )
            })}
          </div>

        </>
      )}
      <PliSettingsSection results={results} />
    </div>
  )
}

// ── GRIP delivery time histogram ─────────────────────────────────────────────
function GripDeliveryChart({ transfers }) {
  if (!transfers || !transfers.length) return null
  const completed = transfers.filter(t => t.delivery_ms != null)
  if (!completed.length) return null

  // Bucket into bins: 0-500ms, 500-1000, 1000-2000, 2000-5000, 5000+
  const BINS = [
    { label: '<500ms',    min: 0,    max: 500   },
    { label: '500ms–1s',  min: 500,  max: 1000  },
    { label: '1–2s',      min: 1000, max: 2000  },
    { label: '2–5s',      min: 2000, max: 5000  },
    { label: '5s+',       min: 5000, max: Infinity },
  ]
  const counts = BINS.map(b => ({
    ...b,
    count: completed.filter(t => t.delivery_ms >= b.min && t.delivery_ms < b.max).length,
  }))
  const max = Math.max(...counts.map(b => b.count), 1)
  const avg = Math.round(completed.reduce((s, t) => s + t.delivery_ms, 0) / completed.length)

  return (
    <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: '16px 18px', marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14 }}>
        <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 14, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: '#c8ddf4' }}>
          Delivery Time Distribution
        </div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted }}>
          avg {avg.toLocaleString()}ms · {completed.length} transfers
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 80 }}>
        {counts.map((b, i) => {
          const pct = (b.count / max) * 100
          const color = b.min >= 5000 ? C.red : b.min >= 2000 ? C.yellow : C.green
          return (
            <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted }}>{b.count || ''}</div>
              <div style={{ width: '100%', background: 'var(--bg)', borderRadius: '3px 3px 0 0', height: 56, display: 'flex', alignItems: 'flex-end' }}>
                <div style={{ width: '100%', height: `${Math.max(pct, b.count ? 4 : 0)}%`, background: color, opacity: 0.85, borderRadius: '3px 3px 0 0', transition: 'height 0.3s ease' }} />
              </div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, textAlign: 'center' }}>{b.label}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function GripOutcomeBar({ transfers }) {
  if (!transfers || !transfers.length) return null
  const delivered  = transfers.filter(t => t.outcome === 'delivered').length
  const cancelled  = transfers.filter(t => t.outcome === 'cancelled').length
  const incomplete = transfers.filter(t => t.outcome === 'incomplete').length
  const total = transfers.length
  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
      {[
        { label: 'Delivered',  count: delivered,  color: C.green },
        { label: 'Cancelled',  count: cancelled,  color: C.red   },
        { label: 'Incomplete', count: incomplete, color: C.yellow },
      ].filter(x => x.count > 0).map(({ label, count, color }) => (
        <div key={label} style={{ background: `${color}12`, border: `1px solid ${color}40`, borderRadius: 6, padding: '8px 14px', minWidth: 100 }}>
          <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 24, fontWeight: 700, color, lineHeight: 1 }}>{count}</div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, marginTop: 3 }}>{label} · {Math.round(count/total*100)}%</div>
        </div>
      ))}
      {transfers.some(t => t.max_rep_counter > 0) && (
        <div style={{ background: `${C.yellow}12`, border: `1px solid ${C.yellow}40`, borderRadius: 6, padding: '8px 14px', minWidth: 100 }}>
          <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 24, fontWeight: 700, color: C.yellow, lineHeight: 1 }}>
            {transfers.filter(t => t.max_rep_counter > 0).length}
          </div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, marginTop: 3 }}>Had retransmits</div>
        </div>
      )}
    </div>
  )
}

function TxRxTab({ results }) {
  const allGripTransfers = results.flatMap(r => r.grip_transfers || [])
  const hasGrip = allGripTransfers.length > 0

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

      {hasGrip && (
        <>
          <SectionHeader
            icon="🔁"
            title="GRIP Transfer Analysis"
            sub="From GRIP_SENDER / GRIP_Receiver structured log fields — RSDK logs only"
          />
          <Note>
            GRIP data is sourced from structured <code>Outgoing/Incoming message fields</code> log lines.
            Delivery time = sender-side &quot;File transmission started&quot; → &quot;File has been successfully delivered&quot;.
            repCounter tracks retransmissions per segment; max 3 before firmware cancels the transfer.
          </Note>
          <GripOutcomeBar transfers={allGripTransfers} />
          <GripDeliveryChart transfers={allGripTransfers} />

          {/* Retransmit detail — only show if any occurred */}
          {allGripTransfers.some(t => t.max_rep_counter > 0) && (
            <>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8, marginTop: 4 }}>
                Transfers with retransmissions
              </div>
              <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 16px', marginBottom: 16 }}>
                {allGripTransfers.filter(t => t.max_rep_counter > 0).map((t, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '5px 0', borderBottom: '1px solid var(--bg2)' }}>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, minWidth: 130 }}>{t.start_timestamp?.slice(5, 19)}</span>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#94a3b8' }}>id {t.msg_id}</span>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: t.max_rep_counter >= 2 ? C.red : C.yellow }}>
                      max rep {t.max_rep_counter}/2
                    </span>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted }}>{t.segment_count != null ? `${t.segment_count} seg` : ''}</span>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: t.delivery_ms != null ? C.green : C.muted }}>
                      {t.delivery_ms != null ? `${t.delivery_ms.toLocaleString()}ms` : t.outcome}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}
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
      <SectionHeader icon="🔋" title="Battery Level Over Time" sub="Red threshold at 30% · critical below 10%" />
      <ChartPanel results={results} selectedPoints={['battery_over_time']} />
      <SectionHeader icon="📉" title="Minimum Battery Recorded" />
      <ChartPanel results={results} selectedPoints={['battery_min']} />
    </div>
  )
}

// ── Hop Count Map ─────────────────────────────────────────────────────────────

const HOP_COLORS = {
  1: '#00e5a0',   // green  — direct
  2: '#ffd166',   // yellow — one relay
  3: '#ff6b35',   // orange — two relays
  4: '#ff4757',   // red    — three relays
}
const hopColor = (h) => HOP_COLORS[h] || '#ef4444'

const rssiColor = (rssi) => {
  if (rssi == null) return '#4a6080'
  if (rssi >= -70)  return '#00e5a0'
  if (rssi >= -85)  return '#ffd166'
  if (rssi >= -100) return '#ff6b35'
  return '#ff4757'
}
const rssiLabel = (rssi) => {
  if (rssi == null) return 'Unknown'
  if (rssi >= -70)  return 'Strong'
  if (rssi >= -85)  return 'Medium'
  if (rssi >= -100) return 'Weak'
  return 'Poor'
}
const haversineDistance = (lat1, lon1, lat2, lon2) => {
  const R = 3958.8
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLon = (lon2 - lon1) * Math.PI / 180
  const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLon/2)**2
  const mi = R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a))
  return { mi, ft: mi*5280, label: mi >= 0.1 ? mi.toFixed(2)+' mi' : Math.round(mi*5280)+' ft' }
}

function HopCountMap({ results }) {
  const mapRef    = React.useRef(null)
  const leafletRef = React.useRef(null)
  const markersRef = React.useRef([])
  const linesRef   = React.useRef([])

  // Build device list from ATAK results that have location data
  const atakResults = React.useMemo(() => results.filter(r => r.log_format === 'atak'), [results])

  const deviceOptions = React.useMemo(() => {
    return atakResults.map(r => ({
      label: r.device?.callsign || r.source_filename,
      filename: r.source_filename,
    }))
  }, [atakResults])

  const [selectedDevice, setSelectedDevice] = React.useState(deviceOptions[0]?.filename || '')
  const [selectedSender, setSelectedSender]  = React.useState('ALL')
  const [showLinks, setShowLinks]             = React.useState(true)
  const [leafletReady, setLeafletReady]       = React.useState(!!window.L)

  // Load Leaflet from CDN if not already present
  React.useEffect(() => {
    if (window.L) { setLeafletReady(true); return }

    // CSS
    const link = document.createElement('link')
    link.rel  = 'stylesheet'
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
    document.head.appendChild(link)

    // JS
    const script = document.createElement('script')
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
    script.onload = () => setLeafletReady(true)
    document.head.appendChild(script)
  }, [])

  // Build map data for selected device
  const { points, senderOptions } = React.useMemo(() => {
    const r = atakResults.find(r => r.source_filename === selectedDevice)
    if (!r) return { points: [], senderOptions: [] }

    const msgs = (r.atak_messages || []).filter(m =>
      !m.is_sender &&
      m.logging_user_location?.lat &&
      m.transmitted_location?.lat &&
      m.hop_count != null
    )

    const senders = ['ALL', ...new Set(msgs.map(m => m.originator_callsign || 'Unknown').filter(Boolean).sort())]
    
    const filtered = selectedSender === 'ALL'
      ? msgs
      : msgs.filter(m => (m.originator_callsign || 'Unknown') === selectedSender)

    const pts = filtered.map(m => ({
      lat:        m.logging_user_location.lat,
      lon:        m.logging_user_location.long,
      senderLat:  m.transmitted_location.lat,
      senderLon:  m.transmitted_location.long,
      hops:       m.hop_count,
      rssi:       m.rssi,
      sender:     m.originator_callsign || 'Unknown',
      time:       m.timestamp,
      msgType:    m.message_type,
    }))

    return { points: pts, senderOptions: senders }
  }, [atakResults, selectedDevice, selectedSender])

  // Init map once Leaflet is ready
  React.useEffect(() => {
    if (!leafletReady || !mapRef.current) return
    if (leafletRef.current) return // already initialized

    const L = window.L
    const map = L.map(mapRef.current, {
      center: [45.31, -111.80],
      zoom: 11,
      zoomControl: true,
    })

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map)

    leafletRef.current = map
    return () => {
      map.remove()
      leafletRef.current = null
    }
  }, [leafletReady])

  // Update markers whenever data or toggles change
  React.useEffect(() => {
    const L = window.L
    if (!L || !leafletRef.current || !points.length) return
    const map = leafletRef.current

    // Clear existing
    markersRef.current.forEach(m => m.remove())
    linesRef.current.forEach(l => l.remove())
    markersRef.current = []
    linesRef.current   = []

    const bounds = []
    let linkCount = 0          // cap RF lines at 80 for readability
    const seenHopDiamonds = new Set()  // one diamond per hop count (max 4)

    points.forEach(p => {
      const color = hopColor(p.hops)
      const radius = p.hops === 1 ? 7 : p.hops === 2 ? 6 : 5

      // Receiver dot
      const circle = L.circleMarker([p.lat, p.lon], {
        radius,
        fillColor:   color,
        color:       '#0d1428',
        weight:      1.5,
        opacity:     1,
        fillOpacity: 0.85,
      }).bindPopup(`
        <div style="font-family:monospace;font-size:11px;line-height:1.6">
          <b style="color:${color}">${p.hops} hop${p.hops !== 1 ? 's' : ''}</b> from <b>${p.sender}</b><br/>
          RSSI: ${p.rssi} dBm (${rssiLabel(p.rssi)})<br/>
          Type: ${p.msgType}<br/>
          Time: ${p.time?.slice(11,19) || '—'}
        </div>
      `).addTo(map)
      markersRef.current.push(circle)
      bounds.push([p.lat, p.lon])

      // RF link line to sender position
      if (showLinks && p.senderLat) {
        const lc = rssiColor(p.rssi)
        const dist = haversineDistance(p.lat, p.lon, p.senderLat, p.senderLon)
        // Thin lines when many points — sample to max 150 RF lines for readability
        if (linkCount < 80) {
          linkCount++
          const line = L.polyline([[p.lat,p.lon],[p.senderLat,p.senderLon]],
            { color: lc, weight: 1.5, opacity: 0.4, dashArray: '4,5' }).addTo(map)
          linesRef.current.push(line)
          // One midpoint diamond per unique hop count — keeps map uncluttered
          if (!seenHopDiamonds.has(p.hops)) {
            seenHopDiamonds.add(p.hops)
            const ml = (p.lat+p.senderLat)/2, mn = (p.lon+p.senderLon)/2
            const hc = hopColor(p.hops)
            const mid = L.marker([ml,mn], {
              icon: L.divIcon({
                className: '',
                html: '<div style="width:8px;height:8px;background:'+hc+';border:2px solid #0d1428;transform:rotate(45deg);cursor:pointer"></div>',
                iconAnchor: [6,6],
              })
            }).bindPopup(
              '<div style="font-family:monospace;font-size:11px;line-height:1.7">'
              +'<b style="color:'+hc+'">'+p.hops+' hop'+(p.hops !== 1 ? 's' : '')+'</b> — '+dist.label+' to sender<br/>'
              +'RSSI: '+p.rssi+' dBm <span style="color:'+lc+'">('+rssiLabel(p.rssi)+')</span><br/>'
              +'From: '+p.sender+'<br/>'
              +'Time: '+(p.time ? p.time.slice(11,19) : '—')
              +'</div>'
            ).addTo(map)
            linesRef.current.push(mid)
          }
        }
      }
    })

    if (bounds.length > 1) {
      try { map.fitBounds(bounds, { padding: [32, 32] }) } catch { /* degenerate bounds — leave the current view */ }
    } else if (bounds.length === 1) {
      map.setView(bounds[0], 13)
    }
  }, [points, showLinks, leafletReady])

  if (!atakResults.length) return null

  const hopCounts = [1,2,3,4]
  const countByHop = points.reduce((acc, p) => {
    acc[p.hops] = (acc[p.hops] || 0) + 1
    return acc
  }, {})

  return (
    <div style={{ marginTop: 24 }}>
      {/* Controls */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 12 }}>
        {/* Device selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Device</span>
          <select
            value={selectedDevice}
            onChange={e => setSelectedDevice(e.target.value)}
            style={{ fontFamily: 'var(--mono)', fontSize: 9, background: 'var(--panel)', color: '#c8ddf4', border: '1px solid var(--border)', borderRadius: 4, padding: '3px 8px', cursor: 'pointer' }}
          >
            {deviceOptions.map(d => (
              <option key={d.filename} value={d.filename}>{d.label}</option>
            ))}
          </select>
        </div>

        {/* Sender filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Sender</span>
          <select
            value={selectedSender}
            onChange={e => setSelectedSender(e.target.value)}
            style={{ fontFamily: 'var(--mono)', fontSize: 9, background: 'var(--panel)', color: '#c8ddf4', border: '1px solid var(--border)', borderRadius: 4, padding: '3px 8px', cursor: 'pointer' }}
          >
            {senderOptions.map(s => (
              <option key={s} value={s}>{s === 'ALL' ? 'All Senders' : s}</option>
            ))}
          </select>
        </div>

        {/* RF link toggle */}
        <label style={{ display: 'flex', alignItems: 'center', gap: 5, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showLinks}
            onChange={e => setShowLinks(e.target.checked)}
            style={{ accentColor: C.accent }}
          />
          <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted }}>Show RF links</span>
        </label>

        {/* Point count */}
        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#334155', marginLeft: 'auto' }}>
          {points.length.toLocaleString()} points
        </span>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 14, marginBottom: 10, flexWrap: 'wrap' }}>
        {hopCounts.map(h => (
          <div key={h} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: hopColor(h), border: '1.5px solid #0d1428' }} />
            <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#94a3b8' }}>
              {h}{h === 4 ? '+' : ''} hop{h !== 1 ? 's' : ''}
              {countByHop[h] ? <span style={{ color: '#334155' }}> ({countByHop[h]})</span> : ''}
            </span>
          </div>
        ))}
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <div style={{ width: 18, height: 0, borderTop: '1px dashed #4a6080' }} />
          <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#334155' }}>RF link (color=RSSI, label=distance)</span>
        </div>
      </div>

      {showLinks && (
        <div style={{ display:'flex', gap:12, flexWrap:'wrap', alignItems:'center', marginBottom:10 }}>
          <span style={{ fontFamily:'var(--mono)', fontSize:8, color:C.muted, textTransform:'uppercase', letterSpacing:'0.08em' }}>RF Signal:</span>
          {[
            { label:'Strong', sub:'>= -70 dBm',       color:'#00e5a0' },
            { label:'Medium', sub:'-70 to -85 dBm',   color:'#ffd166' },
            { label:'Weak',   sub:'-85 to -100 dBm',  color:'#ff6b35' },
            { label:'Poor',   sub:'< -100 dBm',       color:'#ff4757' },
          ].map(s => (
            <div key={s.label} style={{ display:'flex', alignItems:'center', gap:5 }}>
              <div style={{ width:16, height:0, borderTop:'2px dashed '+s.color }} />
              <span style={{ fontFamily:'var(--mono)', fontSize:8, color:s.color }}>{s.label}</span>
              <span style={{ fontFamily:'var(--mono)', fontSize:7, color:'#334155' }}>{s.sub}</span>
            </div>
          ))}
        </div>
      )}

      {/* Map container */}
      {!leafletReady ? (
        <div style={{ height: 480, background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted }}>Loading map…</span>
        </div>
      ) : (
        <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden', position: 'relative' }}>
          <div ref={mapRef} style={{ height: 480, width: '100%' }} />
        </div>
      )}

      <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#334155', marginTop: 8 }}>
        Dot = receiver position · color = hop count · Dashed line = RF link (color = RSSI) · ◆ = hover for distance & signal details
      </div>
    </div>
  )
}


function HopsTab({ results }) {
  const hasRsdk   = results.some(r => r.log_format === 'rsdk')
  const hasGripHops = results.some(r =>
    (r.grip_messages || []).some(g => g.direction === 'incoming' && g.hops != null)
  )

  // Build a per-device hop summary from GRIP incoming messages
  const gripHopSummary = React.useMemo(() => {
    return results
      .filter(r => r.log_format === 'rsdk')
      .map(r => {
        const incoming = (r.grip_messages || []).filter(g => g.direction === 'incoming' && g.hops != null)
        if (!incoming.length) return null
        const hops = incoming.map(g => g.hops)
        const avg  = (hops.reduce((a, b) => a + b, 0) / hops.length).toFixed(1)
        const dist = hops.reduce((acc, h) => { acc[h] = (acc[h] || 0) + 1; return acc }, {})
        return {
          serial: r.device?.radio_serial || r.source_filename,
          avg,
          dist,
          count: incoming.length,
        }
      })
      .filter(Boolean)
  }, [results])

  return (
    <div>
      <SectionHeader
        icon="🔁"
        title="Hop Count Distribution"
        sub="Diagnostic · ATAK · RSDK via GRIP_Receiver incoming fields (genuine RF data)"
      />
      {hasRsdk && !hasGripHops && (
        <Note>⚠ RSDK logs present but no GRIP_Receiver incoming fields found — hop count unavailable for these logs. Legacy SendMessageResponse hop count (SDK sequence counter) is excluded.</Note>
      )}
      {hasRsdk && hasGripHops && (
        <Note>RSDK hop counts sourced from <code>GRIP_Receiver</code> incoming message fields — genuine RF mesh routing data. Distinct from legacy SDK sequence counter (excluded).</Note>
      )}
      <ChartPanel results={results} selectedPoints={['hop_distribution']} />
      <SectionHeader icon="📊" title="Average Hop Count per Device" />
      <ChartPanel results={results} selectedPoints={['hop_avg']} />

      {gripHopSummary.length > 0 && (
        <>
          <SectionHeader icon="📡" title="GRIP Hop Count Detail" sub="Per-device breakdown from RSDK GRIP_Receiver incoming lines" />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 10 }}>
            {gripHopSummary.map((s, i) => (
              <div key={i} style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: '14px 16px' }}>
                <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 14, fontWeight: 700, color: PALETTE[i % PALETTE.length], marginBottom: 10 }}>
                  {s.serial}
                </div>
                <div style={{ display: 'flex', gap: 16, marginBottom: 10 }}>
                  <div>
                    <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 28, fontWeight: 700, color: '#ff6b35', lineHeight: 1 }}>{s.avg}</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted }}>avg hops</div>
                  </div>
                  <div>
                    <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 28, fontWeight: 700, color: '#94a3b8', lineHeight: 1 }}>{s.count}</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted }}>messages</div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {Object.entries(s.dist).sort((a,b)=>Number(a[0])-Number(b[0])).map(([hop, cnt]) => (
                    <div key={hop} style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#94a3b8', background: 'var(--bg2)', borderRadius: 3, padding: '2px 7px' }}>
                      {hop} hop{hop !== '1' ? 's' : ''}: {cnt}
                    </div>
                  ))}
                </div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#334155', marginTop: 8 }}>Source: GRIP (RSDK)</div>
              </div>
            ))}
          </div>
        </>
      )}

      {results.some(r => r.log_format === 'atak' && (r.atak_messages || []).some(m => m.logging_user_location)) && (
        <>
          <SectionHeader
            icon="🗺️"
            title="Hop Count Map"
            sub="Receiver position colored by hop count · click any dot for details · filter by sender to track approach"
          />
          <HopCountMap results={results} />
        </>
      )}
    </div>
  )
}

function RssiTab({ results }) {
  const hasGripRssi = results.some(r =>
    (r.grip_messages || []).some(g => g.direction === 'incoming' && g.rssi != null)
  )

  // Per-device GRIP RSSI summary cards (avg/min/max)
  const gripRssiSummary = React.useMemo(() => {
    return results
      .filter(r => r.log_format === 'rsdk')
      .map(r => {
        const incoming = (r.grip_messages || []).filter(g => g.direction === 'incoming' && g.rssi != null)
        if (!incoming.length) return null
        const vals = incoming.map(g => g.rssi)
        const avg  = Math.round(vals.reduce((a, b) => a + b, 0) / vals.length)
        const min  = Math.min(...vals)
        const max  = Math.max(...vals)
        const retransmitMsgs = (r.grip_messages || []).filter(g => g.direction === 'incoming' && g.rep_counter > 0).length
        return {
          serial: r.device?.radio_serial || r.source_filename,
          avg, min, max,
          count: incoming.length,
          retransmitMsgs,
        }
      })
      .filter(Boolean)
  }, [results])

  const rssiColor = (dbm) => dbm >= -70 ? C.green : dbm >= -85 ? C.yellow : C.red

  return (
    <div>
      <SectionHeader
        icon="📡"
        title="RSSI by Hop Count"
        sub="Real dBm — diagnostic: unsigned byte (value − 256) · ATAK/RSDK GRIP: already signed dBm"
      />
      <ChartPanel results={results} selectedPoints={['rssi_by_hop']} />
      <SectionHeader icon="📶" title="Average RSSI per Device" />
      <ChartPanel results={results} selectedPoints={['rssi_avg_device']} />
      <Note>
        Diagnostic RSSI stored as unsigned byte (137–237). Real dBm = value − 256 (−119 to −19 dBm).
        ATAK and RSDK GRIP RSSI values are already signed dBm — no conversion needed.
        Sent-message RSSI (always 0) is excluded.
      </Note>

      {hasGripRssi && (
        <>
          <SectionHeader
            icon="📈"
            title="GRIP RSSI Over Time"
            sub="RSDK · GRIP_Receiver incoming fields · bucketed average · ▲ = retransmit event"
          />

          {/* Summary cards — compact header above the chart */}
          {gripRssiSummary.length > 0 && (
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
              {gripRssiSummary.map((s, i) => (
                <div key={i} style={{ background: 'var(--panel)', border: `1px solid ${PALETTE[i % PALETTE.length]}30`, borderLeft: `3px solid ${PALETTE[i % PALETTE.length]}`, borderRadius: 6, padding: '10px 14px', display: 'flex', gap: 16, alignItems: 'center' }}>
                  <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 13, fontWeight: 700, color: PALETTE[i % PALETTE.length], minWidth: 90 }}>
                    {s.serial}
                  </div>
                  <div style={{ display: 'flex', gap: 14 }}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 20, fontWeight: 700, color: rssiColor(s.avg), lineHeight: 1 }}>{s.avg}</div>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 7, color: C.muted }}>avg dBm</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 20, fontWeight: 700, color: rssiColor(s.min), lineHeight: 1 }}>{s.min}</div>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 7, color: C.muted }}>min dBm</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 20, fontWeight: 700, color: rssiColor(s.max), lineHeight: 1 }}>{s.max}</div>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 7, color: C.muted }}>max dBm</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 20, fontWeight: 700, color: '#94a3b8', lineHeight: 1 }}>{s.count}</div>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 7, color: C.muted }}>msgs</div>
                    </div>
                    {s.retransmitMsgs > 0 && (
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 20, fontWeight: 700, color: C.yellow, lineHeight: 1 }}>{s.retransmitMsgs}</div>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 7, color: C.muted }}>retransmits</div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Line chart */}
          <ChartPanel results={results} selectedPoints={['grip_rssi_over_time']} />

          <Note>
            X-axis shows normalized session progress (0–100%) so sessions of different lengths
            render fully across the chart. Each point is the average RSSI of all incoming GRIP
            messages within that time bucket. ▲ markers indicate a bucket containing at least one
            message with rep_counter &gt; 0 (retransmission). Dashed lines at −70 dBm (good) and
            −85 dBm (caution).
          </Note>
        </>
      )}
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

// The Health Score dimensions (thermal, battery, BLE, RSSI, queue) all come from
// device logs. relay_manager summaries carry none of them, so a relay_manager card
// would default-pass every dimension and show a misleading 5/5 — scope the tab to
// device formats and drop relay_manager.
const HEALTH_FORMATS = ['atak', 'diagnostic', 'rsdk']

function HealthTab({ results }) {
  const deviceResults = React.useMemo(() => results.filter(r => HEALTH_FORMATS.includes(r.log_format)), [results])
  if (deviceResults.length === 0) {
    return <Note>No device logs loaded. The Health Score applies to ATAK, diagnostic, and RSDK logs — upload one to see per-device health.</Note>
  }
  return (
    <div>
      <SectionHeader icon="💊" title="Per-Device Health Score" sub="Composite score — 5 dimensions · thresholds pending field validation" />
      <Note>
        ⚠ Thresholds are initial estimates pending field validation.
        Pass criteria: Thermal &lt; 113°F · Battery &gt; 30% (critical &lt; 10%) · no BLE failures · avg RSSI &gt; −95 dBm · peak queue &lt; 5 msgs.
        Hop count is excluded — it reflects network topology, not device health.
        See <code>docs/ui-requirements.md</code> for full criteria.
      </Note>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
        {deviceResults.map((r, i) => {
          const s = r.summary || {}
          // pass: true = passed, false = failed, null = N/A (no data for this format —
          // excluded from the score denominator rather than counted as a free pass).
          const dims = [
            { label: 'Thermal',  pass: (s.peak_temp_f || 0) < 113,              value: s.peak_temp_f != null ? `${s.peak_temp_f}°F peak` : '—',          threshold: '< 113°F' },
            { label: 'Battery',  pass: (s.min_battery_pct || 100) > 30,         value: s.min_battery_pct != null ? `${s.min_battery_pct}% min` : '—',     threshold: '> 30%', critical: s.min_battery_pct != null && s.min_battery_pct < 10 },
            { label: 'BLE',      pass: !s.ble_fail_count,                       value: s.ble_fail_count ? `${s.ble_fail_count} failures` : 'No failures',  threshold: 'no failures' },
            { label: 'RSSI',     pass: s.avg_rssi == null ? null : s.avg_rssi > -95,  value: s.avg_rssi != null ? `${s.avg_rssi} dBm avg` : 'N/A',          threshold: '> −95 dBm' },
            { label: 'Queue',    pass: (s.max_stored_messages || 0) < 5,        value: s.max_stored_messages ? `${s.max_stored_messages} peak` : '0 peak', threshold: '< 5 msgs' },
          ]
          const score = dims.filter(d => d.pass === true).length
          const total = dims.filter(d => d.pass !== null).length
          const ratio = total ? score / total : 0
          const color = ratio >= 0.8 ? C.green : ratio >= 0.6 ? C.yellow : C.red
          return (
            <div key={i} style={{ background: 'var(--panel)', border: `1px solid var(--border)`, borderRadius: 8, padding: '16px 18px', display: 'flex', gap: 16, alignItems: 'flex-start', minWidth: 0 }}>
              {/* Score block */}
              <div style={{ textAlign: 'center', flexShrink: 0, width: 72 }}>
                <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 11, color: PALETTE[i % PALETTE.length], marginBottom: 8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 72 }}>
                  {r.device?.callsign || r.source_filename?.split('_')[1] || r.source_filename}
                </div>
                <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 44, fontWeight: 700, color, lineHeight: 1 }}>
                  {score}<span style={{ fontSize: 16, color: C.muted }}>/{total}</span>
                </div>
              </div>
              {/* Dimension rows */}
              <div style={{ flex: 1, minWidth: 0 }}>
                {dims.map(d => {
                  const na = d.pass === null
                  const failed = d.pass === false
                  return (
                    <div key={d.label} style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 5 }}>
                      <span style={{ fontSize: 9, lineHeight: 1, flexShrink: 0, color: na ? C.muted : undefined }}>{na ? '–' : d.pass ? '✓' : d.critical ? '🔴' : '✗'}</span>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: failed ? C.red : C.muted, width: 52, flexShrink: 0 }}>{d.label}</span>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: failed ? (d.critical ? '#ff4757' : C.red) : na ? C.muted : '#c8ddf4', fontWeight: failed ? 700 : 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.value}{d.critical ? ' ⚠ CRITICAL' : ''}</span>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 7, color: '#2a3a52', marginLeft: 'auto', flexShrink: 0 }}>{d.threshold}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      {/* Stored Messages section */}
      {deviceResults.some(r => (r.summary?.max_stored_messages || 0) > 0) && (
        <>
          <SectionHeader
            icon="📥"
            title="Radio Message Queue"
            sub="storedMessages — messages queued in radio buffer waiting to be pulled by the app"
          />
          <Note>
            ⚠ When <code>storedMessages &gt; 0</code>, the radio has received messages that the app has not yet
            pulled from the BLE buffer. A large queue can cause a burst of PLI appearing simultaneously
            after an app restart or BLE reconnect — seen on HOTLIPS (2026-06-03 field session, peak=30).
            A value of 30 likely represents the firmware buffer ceiling.
          </Note>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 10 }}>
            {deviceResults.map((r, i) => {
              const peak = r.summary?.max_stored_messages || 0
              if (peak === 0) return null
              const color = peak >= 20 ? C.red : peak >= 5 ? C.yellow : C.muted
              const label = peak >= 20 ? 'High — possible queue backup' : peak >= 5 ? 'Moderate' : 'Low'
              return (
                <div key={i} style={{ background: 'var(--panel)', border: `1px solid ${color}40`, borderLeft: `3px solid ${color}`, borderRadius: 6, padding: '12px 14px' }}>
                  <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 12, color: PALETTE[i % PALETTE.length], marginBottom: 6 }}>
                    {r.device?.callsign || r.source_filename}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                    <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 36, fontWeight: 700, color, lineHeight: 1 }}>{peak}</span>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted }}>peak msgs</span>
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color, marginTop: 4 }}>{label}</div>
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

// ── FW Log Tab ────────────────────────────────────────────────────────────────

function FwLogTab({ results }) {
  const fwResults = results.filter(r => r.log_format === 'fw_log')
  if (!fwResults.length) return null

  return (
    <div>
      {fwResults.map((r, i) => {
        const fw = r.fw_log || {}
        const rf = fw.rf_config || {}
        const routing = fw.routing || {}
        const energy = fw.energy_summary || {}
        const buckets = fw.buckets || []
        const s = r.summary || {}

        const durationMin = fw.duration_ms ? Math.round(fw.duration_ms / 60000) : 0
        const totalBucketRx = buckets.reduce((a, b) => a + b.rx, 0)
        const totalBucketRelayed = buckets.reduce((a, b) => a + b.relayed, 0)

        return (
          <div key={i} style={{ marginBottom: 32 }}>
            {/* Header */}
            <SectionHeader
              icon="📡"
              title={`FW Log — ${fw.origin_hash ? fw.origin_hash.toUpperCase() : 'Unknown'}`}
              sub={`${r.source_filename} · ${durationMin} min · ${(fw.parsed_lines || 0).toLocaleString()} lines parsed · ${(fw.skipped_debug || 0).toLocaleString()} DEBUG skipped`}
            />

            {/* KPI row */}
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
              <KpiCard label="Origin Hash"    value={fw.origin_hash?.toUpperCase() || '—'}   color={C.accent} />
              <KpiCard label="Session"        value={`${durationMin} min`}                    color={C.muted} />
              <KpiCard label="RHC Polls"      value={fw.rhc_poll_count ?? '—'}               color={C.green} />
              <KpiCard label="Neighbors"      value={s.neighbor_count ?? 0}                  color='#c77dff' />
              <KpiCard label="Energy Avg"     value={energy.avg_dbm != null ? `${energy.avg_dbm} dBm` : '—'} color={C.yellow} />
              <KpiCard label="Battery Errors" value={(fw.battery_error_count || 0).toLocaleString()}
                color={fw.battery_error_count > 0 ? C.yellow : C.green}
                tooltip={fw.battery_error_count > 0 ? ["Known firmware quirk — not hardware failure"] : undefined} />
            </div>

            {/* RF Configuration */}
            <SectionHeader icon="📶" title="RF Configuration" sub="From TRX INFO config block" />
            <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: '14px 18px', marginBottom: 16, display: 'flex', gap: 32, flexWrap: 'wrap' }}>
              {[
                { label: 'Device',    value: rf.device_type || '—' },
                { label: 'Region',    value: rf.region || '—' },
                { label: 'Tx Power',  value: rf.tx_power != null ? rf.tx_power : '—' },
                { label: 'Bit Rate',  value: rf.bit_rate ? `${rf.bit_rate.toLocaleString()} bps` : '—' },
                { label: 'Ctrl Ch',   value: rf.control_channels?.join(', ') || '—' },
                { label: 'Data Ch',   value: rf.data_channels?.join(', ') || '—' },
              ].map(item => (
                <div key={item.label}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 3 }}>{item.label}</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: '#c8ddf4' }}>{item.value}</div>
                </div>
              ))}
              <div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 3 }}>Frequencies</div>
                {(rf.frequencies_hz || []).map(f => (
                  <div key={f} style={{ fontFamily: 'var(--mono)', fontSize: 11, color: '#c8ddf4' }}>
                    {(f / 1e6).toFixed(3)} MHz
                  </div>
                ))}
              </div>
            </div>

            {/* Message Bucket History */}
            <SectionHeader icon="🪣" title="Message Bucket History" sub="6-hour windows — last RHC health poll snapshot · bucket[11] = most recent 6 hrs" />
            <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: '14px 18px', marginBottom: 16 }}>
              <div style={{ display: 'flex', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
                <KpiCard label="Total Rx (72hr)"     value={totalBucketRx.toLocaleString()}     color={C.accent} />
                <KpiCard label="Total Relayed (72hr)" value={totalBucketRelayed.toLocaleString()} color={C.green} />
                <KpiCard label="Relay Rate"
                  value={totalBucketRx > 0 ? `${Math.round(totalBucketRelayed/totalBucketRx*100)}%` : '—'}
                  color={C.yellow} />
              </div>
              {buckets.length === 0 ? (
                <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted }}>No bucket data found.</div>
              ) : (
                <div>
                  {/* Column headers */}
                  <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr 80px 80px 60px', gap: 8, marginBottom: 6 }}>
                    {['Window', 'Rx (bar)', 'Rx', 'Relayed', 'Tx'].map(h => (
                      <div key={h} style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</div>
                    ))}
                  </div>
                  {buckets.map(b => {
                    const maxRx = Math.max(...buckets.map(x => x.rx), 1)
                    const pct = Math.max(2, Math.round((b.rx / maxRx) * 100))
                    return (
                      <div key={b.bucket_index} style={{ display: 'grid', gridTemplateColumns: '120px 1fr 80px 80px 60px', gap: 8, marginBottom: 5, alignItems: 'center' }}>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#c8ddf4' }}>
                          {b.hrs_start}–{b.hrs_end} hrs ago
                        </div>
                        <div style={{ height: 8, background: 'var(--bg)', borderRadius: 2, overflow: 'hidden' }}>
                          <div style={{ width: `${pct}%`, height: '100%', background: C.accent, borderRadius: 2, opacity: 0.7 }} />
                        </div>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#c8ddf4' }}>{b.rx.toLocaleString()}</div>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted }}>{b.relayed.toLocaleString()}</div>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted }}>{b.tx}</div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Routing Decisions */}
            <SectionHeader icon="🔀" title="Relay Routing" sub="From RELAY INFO message decisions" />
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
              {[
                { label: 'Relayed',    value: routing.transmit,  color: C.green,  tip: 'transmitMsg=1 — forwarded to mesh' },
                { label: 'Echo',       value: routing.echo,      color: C.accent, tip: 'echo=1 — already received, skipped' },
                { label: 'Vine',       value: routing.vine,      color: '#c77dff', tip: 'vine=1 — vine routing protocol' },
                { label: 'Flood',      value: routing.flood,     color: C.red,    tip: 'flooding=1 — broadcast flood' },
                { label: 'Skip Rx',    value: routing.skip_rx,   color: C.muted,  tip: 'Already received — not processed again' },
                { label: 'Skip Tx',    value: routing.skip_tx,   color: C.muted,  tip: 'Already transmitted — not sent again' },
              ].map(item => (
                <KpiCard key={item.label} label={item.label} value={(item.value || 0).toLocaleString()}
                  color={item.color} tooltip={[item.tip]} />
              ))}
            </div>

            {/* Energy / Signal */}
            <SectionHeader icon="📊" title="Channel Energy" sub="TRX INFO energy samples — last_rssi per preamble detection (INFO level proxy for RSSI)" />
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
              {[
                { label: 'Avg',     value: energy.avg_dbm != null ? `${energy.avg_dbm} dBm` : '—' },
                { label: 'Min',     value: energy.min_dbm != null ? `${energy.min_dbm} dBm` : '—' },
                { label: 'Max',     value: energy.max_dbm != null ? `${energy.max_dbm} dBm` : '—' },
                { label: 'Samples', value: (energy.sample_count || 0).toLocaleString() },
              ].map(item => (
                <KpiCard key={item.label} label={item.label} value={item.value} color={C.yellow} />
              ))}
            </div>

            {/* Neighbors */}
            {(fw.neighbor_hashes || []).length > 0 && (
              <>
                <SectionHeader icon="🕸️" title="Neighbor Table" sub="Unique node hashes seen via RELAY INFO neighborAdd" />
                <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 16px', marginBottom: 16 }}>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {fw.neighbor_hashes.map(h => (
                      <span key={h} style={{ fontFamily: 'var(--mono)', fontSize: 10, color: C.accent,
                        background: `${C.accent}12`, border: `1px solid ${C.accent}30`,
                        borderRadius: 4, padding: '2px 8px' }}>
                        {h.toUpperCase()}
                      </span>
                    ))}
                  </div>
                </div>
              </>
            )}

            {/* Errors and Warnings */}
            {(Object.keys(fw.error_counts || {}).length > 0 || Object.keys(fw.warn_counts || {}).length > 0) && (
              <>
                <SectionHeader icon="⚠️" title="Errors & Warnings" sub="ERROR and WARN lines by module — battery stabilization shown separately" />
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                  <div style={{ background: 'var(--panel)', border: `1px solid ${C.red}30`, borderRadius: 8, padding: '12px 16px' }}>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.red, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Errors</div>
                    {Object.entries(fw.error_counts || {}).map(([mod, cnt]) => (
                      <div key={mod} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#94a3b8' }}>{mod}</span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.red }}>{cnt}</span>
                      </div>
                    ))}
                    {(fw.error_messages || []).map((msg, j) => (
                      <div key={j} style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#334155', marginTop: 4, paddingTop: 4, borderTop: j === 0 ? '1px solid var(--border)' : 'none' }}>
                        • {msg}
                      </div>
                    ))}
                  </div>
                  <div style={{ background: 'var(--panel)', border: `1px solid ${C.yellow}30`, borderRadius: 8, padding: '12px 16px' }}>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.yellow, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Warnings</div>
                    {Object.entries(fw.warn_counts || {}).map(([mod, cnt]) => (
                      <div key={mod} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#94a3b8' }}>{mod}</span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.yellow }}>{cnt}</span>
                      </div>
                    ))}
                    {(fw.warn_messages || []).map((msg, j) => (
                      <div key={j} style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#334155', marginTop: 4, paddingTop: 4, borderTop: j === 0 ? '1px solid var(--border)' : 'none' }}>
                        • {msg}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}

            {/* Data limitations */}
            {(r.parse_errors || []).some(e => e.startsWith('DATA LIMITATION')) && (
              <Note>
                {r.parse_errors.filter(e => e.startsWith('DATA LIMITATION')).map((e, j) => (
                  <div key={j} style={{ marginBottom: 4 }}>⚠ {e.replace('DATA LIMITATION — ', '')}</div>
                ))}
              </Note>
            )}
          </div>
        )
      })}
    </div>
  )
}


// ── SDK Logging 2.0 Summary Card ─────────────────────────────────────────────

function SdkLogSummaryCard({ summary }) {
  const [expanded, setExpanded] = React.useState(false)
  if (!summary || !summary.total_count) return null

  const tagEntries = Object.entries(summary.counts_by_tag || {}).sort((a, b) => b[1] - a[1])
  const infoEntries = Object.entries(summary.counts_by_info || {}).sort((a, b) => b[1] - a[1])
  const total = summary.total_count
  const maxCount = tagEntries.length ? tagEntries[0][1] : 1

  const tagColor = (tag) => {
    if (tag.includes('BLE'))   return '#3b82f6'
    if (tag.includes('RADIO')) return '#f59e0b'
    return '#64748b'
  }

  return (
    <div style={{ background: 'var(--panel)', border: '1px solid #1e3a4a', borderRadius: 8, marginBottom: 16, overflow: 'hidden' }}>
      {/* Header — always visible */}
      <div
        onClick={() => setExpanded(e => !e)}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', cursor: 'pointer', userSelect: 'none' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 14 }}>🔧</span>
          <div>
            <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 14, fontWeight: 700, color: '#94a3b8', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              SDK Logging 2.0
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, marginLeft: 10 }}>
              {total.toLocaleString()} records · {tagEntries.length} tag type{tagEntries.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {tagEntries.slice(0, 3).map(([tag, count]) => (
              <span key={tag} style={{
                fontFamily: 'var(--mono)', fontSize: 8,
                color: tagColor(tag),
                background: `${tagColor(tag)}15`,
                border: `1px solid ${tagColor(tag)}40`,
                borderRadius: 3, padding: '1px 7px'
              }}>
                {tag}: {count.toLocaleString()}
              </span>
            ))}
          </div>
        </div>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted }}>
          {expanded ? '▲ collapse' : '▼ expand'}
        </span>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{ padding: '0 16px 16px', borderTop: '1px solid var(--border)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginTop: 14 }}>

            {/* Tag breakdown bar chart */}
            <div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>
                Tag Breakdown
              </div>
              {tagEntries.map(([tag, count]) => {
                const pct = Math.max(2, Math.round((count / maxCount) * 100))
                const color = tagColor(tag)
                return (
                  <div key={tag} style={{ marginBottom: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color }}>{tag}</span>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted }}>
                        {count.toLocaleString()} ({Math.round(count / total * 100)}%)
                      </span>
                    </div>
                    <div style={{ height: 4, background: 'var(--bg)', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2 }} />
                    </div>
                  </div>
                )
              })}
              <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#334155', marginTop: 8 }}>
                {summary.first_timestamp?.slice(0, 19)} → {summary.last_timestamp?.slice(0, 19)}
              </div>
            </div>

            {/* Unique messages — additionalInfo with occurrence counts */}
            <div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>
                Unique Messages
              </div>
              <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                {infoEntries.map(([msg, count], i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontFamily: 'var(--mono)', fontSize: 8, color: '#64748b', padding: '3px 0', borderBottom: '1px solid var(--bg2)' }}>
                    <span>• {msg}</span>
                    <span style={{ color: C.muted, flexShrink: 0 }}>{count.toLocaleString()}</span>
                  </div>
                ))}
                {infoEntries.length === 0 && (
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#334155' }}>No additionalInfo messages found.</div>
                )}
              </div>
            </div>
          </div>

          <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#334155', marginTop: 12, padding: '8px 10px', background: 'var(--bg)', borderRadius: 4 }}>
            ℹ SDK Logging 2.0 records are high-volume structured log events from the ATAK plugin.
            They are not stored individually — this is an aggregated summary only.
            Whether these records appear in regular (non-enhanced) logs from firmware 3.2.10/3.2.11 is currently unknown.
          </div>
        </div>
      )}
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

      {/* SDK Logging 2.0 — one card per ATAK result that has sdk_log data */}
      {atakResults.some(r => r.atak_sdk_error_summary?.total_count > 0) && (
        <>
          <SectionHeader
            icon="🔧"
            title="SDK Logging 2.0"
            sub="Structured SDK log events — aggregated counts and unique messages only"
          />
          {atakResults.map((r, i) => r.atak_sdk_error_summary?.total_count > 0 && (
            <div key={i} style={{ marginBottom: 8 }}>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, marginBottom: 4 }}>
                {r.source_filename}
              </div>
              <SdkLogSummaryCard summary={r.atak_sdk_error_summary} />
            </div>
          ))}
        </>
      )}

      <Note>
        ⚠ Callsign and UUID fields are always empty in ATAK log format — identity is GID-only.
        {totalClockSkew > 0 && ` ${totalClockSkew} records have negative delivery times due to clock skew between devices (most common at hop counts 3–4).`}
      </Note>
    </div>
  )
}


// ── Relay Manager helpers ─────────────────────────────────────────────────────

const NOTIF_LABELS = {
  8:   'BLE keepalive',
  9:   'BLE secondary event',
  72:  'BLE poll heartbeat',
  73:  'Health response ready',
  74:  'Device alert',
  75:  'Device alert variant',
  104: 'Battery/charging change',
}

const NOTIF_COLORS = {
  8:   '#6366f1',
  9:   '#64748b',
  72:  '#3b82f6',
  73:  '#10b981',
  74:  '#f59e0b',
  75:  '#f59e0b',
  104: '#8b5cf6',
}

const EVENT_COLORS = {
  health_response_ready: '#10b981',
  device_alert:          '#f59e0b',
  battery_state_changed: '#8b5cf6',
  empty_sender_uuid:     '#64748b',
}

const EVENT_LABELS = {
  health_response_ready: 'Health Response Ready',
  device_alert:          'Device Alert',
  battery_state_changed: 'Battery State Changed',
  empty_sender_uuid:     'Empty Sender UUID',
}

function RelayLimitationBanner({ parseErrors }) {
  const limits = (parseErrors || []).filter(e => e.startsWith('DATA LIMITATION'))
  if (!limits.length) return null
  return (
    <div style={{ background: '#1c1400', border: '1px solid #854d0e', borderRadius: 8, padding: '12px 16px', marginBottom: 20 }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#fbbf24', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 8 }}>
        ⚠️ Data Limitations
      </div>
      {limits.map((item, i) => (
        <div key={i} style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#d97706', marginBottom: i < limits.length - 1 ? 6 : 0, paddingLeft: 12 }}>
          • {item.replace('DATA LIMITATION — ', '')}
        </div>
      ))}
    </div>
  )
}

function RelayKpiRow({ results }) {
  // Compact KPI strip shown in the Overview when all logs are relay_manager format
  const totalRequests = results.reduce((n, r) => n + (r.summary?.health_request_count || 0), 0)
  const totalResponses = results.reduce((n, r) => n + (r.summary?.response_ready_count || 0), 0)
  const totalAlerts    = results.reduce((n, r) => n + (r.summary?.device_alert_count || 0), 0)
  const subtypes = [...new Set(results.map(r => r.summary?.subtype).filter(Boolean))]
  const envs     = [...new Set(results.map(r => r.summary?.environment).filter(Boolean))]

  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', padding: '12px 36px', borderBottom: '1px solid var(--border2)', background: 'rgba(5,8,15,0.75)', flexShrink: 0, backdropFilter: 'blur(4px)' }}>
      <KpiCard label="Logs Loaded"       value={results.length}   sub="relay manager format"          color='#22d3ee' />
      <KpiCard label="Health Requests"   value={totalRequests}    sub="relayHealthRequestCall events"  color='#22d3ee' />
      <KpiCard label="Responses Ready"   value={totalResponses}   sub="health response ready events"  color='#10b981' />
      <KpiCard label="Device Alerts"     value={totalAlerts || '—'} sub="unsolicited pull-required alerts" color='#f59e0b' />
      <KpiCard label="Sub-Type"          value={subtypes.join(' + ') || '—'} sub="auto-detected"      color='#6366f1' />
      <KpiCard label="Environment"       value={envs.join(' / ').toUpperCase() || '—'} sub="stage confirmed · prod TBD" color={envs.includes('stage') ? '#22d3ee' : '#f59e0b'} />
    </div>
  )
}

function RelayNotifChart({ notifCounts }) {
  // notifCounts is { "72": 6612, "73": 27, ... } — string keys from JSON
  const entries = Object.entries(notifCounts || {})
    .map(([code, count]) => ({ code: parseInt(code), count }))
    .sort((a, b) => b.count - a.count)
  if (!entries.length) return <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted }}>No notification data.</div>

  const max = entries[0].count
  return (
    <div>
      {entries.map(({ code, count }) => {
        const label = NOTIF_LABELS[code] || `Type ${code}`
        const color = NOTIF_COLORS[code] || '#64748b'
        const pct   = Math.max(1, Math.round((count / max) * 100))
        return (
          <div key={code} style={{ marginBottom: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#94a3b8' }}>
                <span style={{ color, marginRight: 6 }}>type {code}</span>{label}
              </span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted }}>{count.toLocaleString()}</span>
            </div>
            <div style={{ height: 4, background: 'var(--bg)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2 }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

function RelayEventList({ events }) {
  if (!events?.length) return <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted }}>No events recorded.</div>
  // Show max 60 events
  const shown = events.slice(0, 60)
  return (
    <div style={{ maxHeight: 280, overflowY: 'auto' }}>
      {shown.map((ev, i) => {
        const color = EVENT_COLORS[ev.event_type] || C.muted
        const label = EVENT_LABELS[ev.event_type] || ev.event_type
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '4px 0', borderBottom: '1px solid var(--bg2)' }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: color, marginTop: 4, flexShrink: 0 }} />
            <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, minWidth: 135, flexShrink: 0 }}>{ev.timestamp?.slice(0, 19)}</span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color }}>{label}</span>
          </div>
        )
      })}
      {events.length > 60 && (
        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, padding: '6px 0' }}>
          +{events.length - 60} more events
        </div>
      )}
    </div>
  )
}

function RelayHealthTab({ results }) {
  const relayResults = results.filter(r => r.log_format === 'relay_manager')
  if (!relayResults.length) {
    return (
      <Note>No Relay Manager logs loaded. Upload a networkPolling or scheduledHealthRequest logcat .txt file to see relay health data.</Note>
    )
  }

  return (
    <div>
      {relayResults.map((r, i) => {
        const rm     = r.relay_manager || {}
        const sum    = r.summary || {}
        const color  = PALETTE[i % PALETTE.length]

        const subtype = rm.subtype || sum.subtype || '—'
        const env     = rm.environment || sum.environment || '—'
        const envColor = env === 'stage' ? '#22d3ee' : '#f59e0b'

        // Average interval label
        const avgSec = sum.avg_interval_sec
        const intervalLabel = avgSec
          ? (avgSec >= 3600 ? `~${(avgSec/3600).toFixed(1)}h` : avgSec >= 60 ? `~${Math.round(avgSec/60)}m` : `~${Math.round(avgSec)}s`)
          : '—'

        return (
          <div key={i} style={{ marginBottom: 24 }}>
            {/* Session header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, paddingBottom: 10, borderBottom: `1px solid ${color}30` }}>
              <div style={{ width: 3, height: 32, background: color, borderRadius: 2, flexShrink: 0 }} />
              <div>
                <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 16, fontWeight: 700, color }}>{r.source_filename}</div>
                <div style={{ display: 'flex', gap: 8, marginTop: 3, flexWrap: 'wrap' }}>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: envColor, background: `${envColor}15`, border: `1px solid ${envColor}40`, borderRadius: 3, padding: '1px 7px', textTransform: 'uppercase' }}>{env}</span>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#6366f1', background: '#6366f115', border: '1px solid #6366f140', borderRadius: 3, padding: '1px 7px' }}>{subtype || 'unknown subtype'}</span>
                </div>
              </div>
            </div>

            {/* Data limitations banner */}
            <RelayLimitationBanner parseErrors={r.parse_errors} />

            {/* Two-column layout */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>

              {/* Session Info */}
              <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 12 }}>Session Info</div>
                {[
                  ['Device Serial',  rm.relay_serial || r.device?.radio_serial || '—'],
                  ['BLE Address',    rm.ble_address || '—'],
                  ['App PID',        rm.app_pid || '—'],
                  ['Session Start',  r.session_start?.slice(0, 19) || '—'],
                  ['Session End',    r.session_end?.slice(0, 19)   || '—'],
                  ['Gaps',           r.session_gaps?.length ? `${r.session_gaps.length} gap(s)` : 'none detected'],
                ].map(([k, v]) => (
                  <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid var(--bg2)' }}>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted }}>{k}</span>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#94a3b8', maxWidth: '55%', textAlign: 'right', wordBreak: 'break-all' }}>{v}</span>
                  </div>
                ))}
              </div>

              {/* Health Requests */}
              <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 12 }}>Health Requests</div>
                <div style={{ display: 'flex', gap: 20, marginBottom: 12 }}>
                  <div>
                    <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 28, fontWeight: 700, color: '#22d3ee', lineHeight: 1 }}>{sum.health_request_count ?? '—'}</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, marginTop: 2 }}>total requests</div>
                  </div>
                  <div>
                    <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 28, fontWeight: 700, color: '#38bdf8', lineHeight: 1 }}>{intervalLabel}</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, marginTop: 2 }}>avg interval</div>
                  </div>
                  <div>
                    <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 28, fontWeight: 700, color: '#10b981', lineHeight: 1 }}>{sum.response_ready_count ?? '—'}</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, marginTop: 2 }}>responses ready</div>
                  </div>
                </div>
                {(rm.health_requests || []).length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {(rm.health_requests || []).map((req, j) => (
                      <div key={j} style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 4, padding: '3px 8px', fontFamily: 'var(--mono)', fontSize: 8, color: '#22d3ee' }}>
                        {req.timestamp?.slice(5, 19)}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Notification breakdown + event log side by side */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 12 }}>Firmware Notifications</div>
                <RelayNotifChart notifCounts={rm.notification_counts} />
                <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#334155', marginTop: 10 }}>
                  Types 72/8 = BLE keepalive · 73 = response ready · 74 = device alert · 104 = battery event
                </div>
              </div>

              <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 12 }}>Event Log</div>
                <RelayEventList events={rm.events} />
              </div>
            </div>
          </div>
        )
      })}
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
    case 'health':      return <HealthTab      results={results} />
    case 'relay-health':
      if (!results.some(r => r.log_format === 'relay_manager'))
        return <EmptyTabState message="No Relay Manager Logs Uploaded" detail="Upload an Android logcat file from com.gotenna.relaymanager to analyze relay health data." />
      return <RelayHealthTab results={results} />
    case 'atak':         return <AtakTab        results={results} />
    case 'fw-log':
      if (!results.some(r => r.log_format === 'fw_log'))
        return <EmptyTabState message="No Firmware Logs Uploaded" detail="Upload a UART/USB debug log from the goTenna relay radio to analyze firmware data." />
      return <FwLogTab results={results} />
    default:          return null
  }
}

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
      const msgs      = (r.received_messages  || []).filter(m => inWindow(m.timestamp))
      const samples   = (r.system_samples     || []).filter(s => inWindow(s.timestamp))
      const bleEvts   = (r.ble_fail_events    || []).filter(b => inWindow(b.timestamp))
      const txEvts    = (r.tx_events          || []).filter(t => inWindow(t.timestamp))
      const atakMsg   = (r.atak_messages      || []).filter(m => inWindow(m.timestamp))
      const atakHlth  = (r.atak_health_samples|| []).filter(h => inWindow(h.timestamp))
      const gripMsgs  = (r.grip_messages      || []).filter(g => inWindow(g.timestamp))
      const gripXfers = (r.grip_transfers     || []).filter(t => inWindow(t.start_timestamp))

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
        min_battery_pct:              (batPcts => batPcts.length ? Math.min(...batPcts) : null)(atakHlth.map(h=>h.battery_pct).filter(v=>v!=null&&v>=0)),
        // Full-session minimum from the API — carried over unchanged so the
        // BatteryMin fallback survives even when the window excludes all samples
        min_battery_unfiltered:       r.summary?.min_battery_unfiltered ?? null,
        partially_received:           atakMsg.filter(m => m.delivery_status === 'PARTIALLY_RECEIVED').length,
        negative_delivery_time_count: atakMsg.filter(m => m.delivery_time_ms != null && m.delivery_time_ms < 0).length,
        // static — unchanged
        session_count:    r.summary?.session_count,
        // BLE failures derive from the SDK-error aggregate — not time-windowable, carried over whole
        ble_fail_count:   r.summary?.ble_fail_count,
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
        // RSSI dimension input — GRIP incoming RSSI, recomputed from the windowed
        // grip messages; null (→ N/A) for diagnostic, which has no GRIP data
        avg_rssi:           rnd(avg(gripMsgs.map(g => g.rssi).filter(v => v != null)), 1),
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
        // always 0 for non-ATAK (SystemSample has no storedMessages); carried
        // explicitly so it survives the spread if a parser ever populates it
        max_stored_messages: r.summary?.max_stored_messages ?? 0,
      }

      return {
        ...r,
        received_messages:    msgs,
        system_samples:       samples,
        ble_fail_events:      bleEvts,
        tx_events:            txEvts,
        atak_messages:        atakMsg,
        atak_health_samples:  atakHlth,
        grip_messages:        gripMsgs,
        grip_transfers:       gripXfers,
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
  const visibleTabs   = TABS.filter(t => {
    if (t.atakOnly)   return results.some(r => r.log_format === 'atak')
    // relay-health and fw-log are always visible — dimmed when no relevant log loaded
    return true
  })

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
            {visibleTabs.map(t => {
              const hasRelay = results.some(r => r.log_format === 'relay_manager')
              const hasFw    = results.some(r => r.log_format === 'fw_log')
              const inactive = (t.relayOnly && !hasRelay) || (t.fwOnly && !hasFw)
              return (
                <button key={t.id} onClick={() => setActiveTab(t.id)} style={{
                  background: 'none', border: 'none', cursor: inactive ? 'default' : 'pointer',
                  padding: '10px 16px 12px',
                  fontFamily: "'Barlow Condensed',sans-serif", fontSize: 13, fontWeight: 600,
                  letterSpacing: '0.06em', textTransform: 'uppercase',
                  color: activeTab === t.id ? 'var(--accent)' : inactive ? '#2a3a52' : C.muted,
                  borderBottom: `2px solid ${activeTab === t.id ? 'var(--accent)' : 'transparent'}`,
                  marginBottom: -1, transition: 'color 0.15s, border-color 0.15s',
                  opacity: inactive ? 0.45 : 1,
                }}>
                  {t.label}
                  {t.atakOnly  && <span style={{ marginLeft: 4, fontSize: 8, color: C.yellow,   fontFamily: 'var(--mono)' }}>α</span>}
                  {t.relayOnly && <span style={{ marginLeft: 4, fontSize: 8, color: inactive ? '#2a3a52' : '#22d3ee', fontFamily: 'var(--mono)' }}>📡</span>}
                </button>
              )
            })}
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
