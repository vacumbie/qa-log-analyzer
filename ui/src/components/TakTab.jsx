import { useEffect, useRef, useMemo } from 'react'
import ChartPanel from './ChartPanel'
import { useLeaflet } from '../hooks/useLeaflet'

// ── Local style constants (mirrors App.jsx / ChartPanel.jsx dark-instrument palette) ──
// The two extra entries past the canonical eight are deliberate: the map colours
// one series per callsign, and real streams carry more callsigns than any chart
// carries series. Past ten they still repeat — see the legend/palette backlog item.
const PALETTE = ['#00d4ff', '#ff6b35', '#ffd166', '#c77dff', '#00e5a0', '#ff4757', '#4a90e2', '#ff6b9d', '#94a3b8', '#3D8BFF']
const C = { accent: '#00d4ff', green: '#00e5a0', yellow: '#ffd166', red: '#ff4757', muted: '#4a6080', dim: '#2a3a52' }

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
    <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6, padding: '10px 16px', minWidth: 110, position: 'relative' }}>
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 2, background: color, borderRadius: '6px 0 0 6px' }} />
      <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>{label}</div>
      <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 22, fontWeight: 700, color, lineHeight: 1 }}>{value ?? '—'}</div>
      {sub && <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: C.dim, marginTop: 3 }}>{sub}</div>}
    </div>
  )
}

function LimitationBanner({ parseErrors }) {
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

function ChartCard({ title, subtitle, height = 320, children }) {
  return (
    <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: '16px 18px', marginBottom: 14 }}>
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 14, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: '#c8ddf4' }}>{title}</div>
        {subtitle && <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#2a3a52', marginTop: 2 }}>{subtitle}</div>}
      </div>
      <div style={{ height }}>{children}</div>
    </div>
  )
}

// ── Position map (Leaflet) ─────────────────────────────────────────────────────
// circleMarkers only — no default L.marker icons, so no need for the usual
// leaflet + bundler icon-path workaround.
function TakPositionMap({ events }) {
  const mapElRef = useRef(null)
  const mapRef = useRef(null)
  const layerGroupRef = useRef(null)
  const leafletReady = useLeaflet()

  // Colors are assigned by first-seen callsign order so they stay stable
  // across re-renders even as the time window filters events in and out.
  const colorByCallsign = useMemo(() => {
    const map = {}
    let i = 0
    for (const e of events) {
      const key = e.callsign || 'unknown'
      if (!(key in map)) {
        map[key] = PALETTE[i % PALETTE.length]
        i++
      }
    }
    return map
  }, [events])

  // has_gps_fix is already the parser's lat/lon sentinel test (see TakEvent in
  // models.py), so re-checking lat/lon here would only wrongly drop a real
  // position sitting exactly on the equator or prime meridian — and would make
  // this count disagree with the No GPS Fix KPI.
  const fixEvents = useMemo(() => events.filter(e => e.has_gps_fix), [events])

  // Two different reasons an event isn't on the map, and only one of them is a
  // data gap: a PLI or Marker with no GPS fix should have carried a position,
  // while Chat and server-control events never do. The single "excluded" number
  // conflated them and contradicted the No GPS Fix KPI.
  const noFixCount = events.filter(
    e => !e.has_gps_fix && (e.category === 'PLI' || e.category === 'Marker')
  ).length
  const noPositionCount = events.length - fixEvents.length - noFixCount

  useEffect(() => {
    if (!leafletReady || !mapElRef.current || mapRef.current) return
    const L = window.L
    mapRef.current = L.map(mapElRef.current, { attributionControl: true })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap', maxZoom: 19,
    }).addTo(mapRef.current)
    layerGroupRef.current = L.layerGroup().addTo(mapRef.current)
    return () => {
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [leafletReady])

  useEffect(() => {
    const map = mapRef.current
    const layerGroup = layerGroupRef.current
    if (!map || !layerGroup) return
    const L = window.L
    layerGroup.clearLayers()

    if (!fixEvents.length) return

    const bounds = []
    for (const e of fixEvents) {
      const color = colorByCallsign[e.callsign || 'unknown']
      L.circleMarker([e.lat, e.lon], {
        radius: 5, fillColor: color, fillOpacity: 0.8, color: '#0d1428', weight: 1, opacity: 1,
      }).bindPopup(
        `<b style="color:${color}">${e.callsign || 'Unknown'}</b> (${e.category})<br/>` +
        `${e.timestamp.slice(11, 19)} UTC · ${e.node_type || 'n/a'}` +
        (e.latency_ms != null ? `<br/>Latency: ${e.latency_ms} ms` : '')
      ).addTo(layerGroup)
      bounds.push([e.lat, e.lon])
    }
    try { map.fitBounds(bounds, { padding: [30, 30] }) } catch { /* single point or degenerate bounds */ }
    // Leaflet sizes its canvas from the container's dimensions at creation
    // time; the tab may have been hidden (display:none) on first mount, so
    // force a recalculation once real data arrives.
    setTimeout(() => map.invalidateSize(), 0)
  }, [fixEvents, colorByCallsign, leafletReady])

  const legendEntries = Object.entries(colorByCallsign)
  // Leaflet arrives from the CDN, so there is a window where positions exist but
  // no map does. Showing the container then would paint the same blank near-white
  // box the empty-state rule exists to prevent, so it waits for both.
  const hasPositions = fixEvents.length > 0 && leafletReady

  return (
    <ChartCard
      title="Device Positions"
      subtitle={mapSubtitle(events.length, fixEvents.length, noFixCount, noPositionCount)}
      height={420}
    >
      <div style={{ display: 'flex', height: '100%', gap: 12 }}>
        {/* The container stays mounted so Leaflet keeps one map instance for the
            life of the tab; it is hidden rather than unmounted when there is
            nothing to plot, because an unmounted ref would leave the creation
            effect (deps []) with nothing to attach to when data returns. An
            un-tiled Leaflet container renders as a blank near-white box, which
            is why it must not simply be left empty. */}
        <div ref={mapElRef} style={{ flex: 1, borderRadius: 6, overflow: 'hidden', display: hasPositions ? 'block' : 'none' }} />
        {!hasPositions && (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 9, color: C.muted, lineHeight: 1.8 }}>
            {!leafletReady && fixEvents.length
              ? 'Loading map…'
              : events.length
                ? 'No event in this time window carries a GPS position.'
                : 'No TAK events in the selected time window.'}
          </div>
        )}
        {hasPositions && (
          <div style={{ width: 130, overflowY: 'auto', flexShrink: 0 }}>
            {legendEntries.map(([callsign, color]) => (
              <div key={callsign} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
                <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#b8cfe8', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {callsign}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </ChartCard>
  )
}

// Spells out both exclusion reasons separately so the plotted count reconciles
// against the No GPS Fix KPI, which is PLI/Marker-scoped.
function mapSubtitle(total, plotted, noFixCount, noPositionCount) {
  if (!total) return 'no events in the selected time window'
  const reasons = []
  if (noFixCount) reasons.push(`${noFixCount} PLI/Marker with no GPS fix`)
  if (noPositionCount) reasons.push(`${noPositionCount} Chat/server-control (never carry a position)`)
  const plottedText = `${plotted} of ${total} events plotted`
  return reasons.length ? `${plottedText} · excluded: ${reasons.join(', ')}` : plottedText
}

// ── Main tab ─────────────────────────────────────────────────────────────────────
export default function TakTab({ results }) {
  const takResults = results.filter(r => r.log_format === 'tak')

  if (!takResults.length) {
    return <Note>No TAK Server logs loaded. Upload a TAK server CoT event stream (.json) to see position and latency data.</Note>
  }

  const allEvents = takResults.flatMap(r => r.tak_events || [])
  const summary = takResults.reduce((acc, r) => {
    const s = r.summary || {}
    acc.total_events += s.total_events || 0
    acc.pli_count += s.pli_count || 0
    acc.chat_count += s.chat_count || 0
    acc.marker_count += s.marker_count || 0
    acc.other_count += s.other_count || 0
    acc.no_fix_count += s.no_fix_count || 0
    acc.negative_latency_count += s.negative_latency_count || 0
    return acc
  }, { total_events: 0, pli_count: 0, chat_count: 0, marker_count: 0, other_count: 0, no_fix_count: 0, negative_latency_count: 0 })

  // Latency and callsign stats come from the summary the API already computed
  // (and App.jsx recomputes under the time window) rather than being derived a
  // second time here — two independent derivations of the same number disagree
  // eventually, and the avg was already rounding differently from the export.
  // Per-file summaries are combined the way the counts above are: callsigns are
  // unioned across files, min/max take the outer bound, and the average is
  // weighted by each file's own latency sample count.
  const uniqueCallsigns = new Set(allEvents.map(e => e.callsign).filter(Boolean)).size
  const latencyStats = takResults.reduce((acc, r) => {
    const s = r.summary || {}
    if (s.avg_latency_ms != null) {
      const n = (r.tak_events || []).filter(e => e.latency_ms != null).length
      acc.weightedSum += s.avg_latency_ms * n
      acc.n += n
    }
    if (s.max_latency_ms != null) acc.max = acc.max == null ? s.max_latency_ms : Math.max(acc.max, s.max_latency_ms)
    if (s.min_latency_ms != null) acc.min = acc.min == null ? s.min_latency_ms : Math.min(acc.min, s.min_latency_ms)
    return acc
  }, { weightedSum: 0, n: 0, max: null, min: null })
  const avgLatency = latencyStats.n ? Math.round(latencyStats.weightedSum / latencyStats.n) : null
  const maxLatency = latencyStats.max
  const minLatency = latencyStats.min

  const serverVersions = [...new Set(
    takResults.map(r => r.tak_server_info?.server_version).filter(Boolean)
  )]

  return (
    <div>
      {takResults.map((r, i) => (
        <LimitationBanner key={i} parseErrors={r.parse_errors} />
      ))}

      <SectionHeader icon="📡" title="TAK Server Overview" sub={serverVersions.length ? `Server version: ${serverVersions.join(', ')}` : undefined} />
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
        <KpiCard label="Total Events" value={summary.total_events} />
        <KpiCard label="PLI" value={summary.pli_count} color={C.green} />
        <KpiCard label="Marker" value={summary.marker_count} color={C.accent} />
        <KpiCard label="Chat" value={summary.chat_count} color={C.yellow} />
        <KpiCard label="Server Control" value={summary.other_count} color={C.muted} />
        <KpiCard label="Unique Callsigns" value={uniqueCallsigns} />
        {/* Scoped to PLI/Marker — the categories expected to carry a position.
            The sub-label states that scope rather than claiming to be the
            map-exclusion count, which also counts Chat/server-control events. */}
        <KpiCard label="No GPS Fix" value={summary.no_fix_count} color={summary.no_fix_count ? C.yellow : C.muted}
          sub="PLI/Marker only" />
        <KpiCard label="Avg Latency" value={avgLatency != null ? `${avgLatency} ms` : '—'} />
        {/* A negative minimum is a device clock ahead of the server, not a fast
            delivery — coloured red so it doesn't read as the best-case latency. */}
        <KpiCard label="Min Latency" value={minLatency != null ? `${minLatency} ms` : '—'}
          color={minLatency != null && minLatency < 0 ? C.red : C.green}
          sub={minLatency != null && minLatency < 0 ? 'device clock ahead of server' : undefined} />
        <KpiCard label="Max Latency" value={maxLatency != null ? `${maxLatency} ms` : '—'} color={C.red} />
        <KpiCard label="Clock Skew Events" value={summary.negative_latency_count} color={summary.negative_latency_count ? C.red : C.muted}
          sub={summary.negative_latency_count ? 'negative latency' : undefined} />
      </div>

      <TakPositionMap events={allEvents} />
      <ChartPanel results={takResults} selectedPoints={['tak_latency']} />
    </div>
  )
}
