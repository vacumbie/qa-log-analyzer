import { useState, useCallback, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useDropzone } from 'react-dropzone'

// ── Parsing overlay — shown app-wide while API is processing ──────────────────
export function ParsingOverlay({ fileCount }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200,
      background: 'rgba(5, 8, 15, 0.88)',
      backdropFilter: 'blur(4px)',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: 20,
    }}>
      {/* Animated pulse ring */}
      <div style={{ position: 'relative', width: 64, height: 64 }}>
        <div style={{
          position: 'absolute', inset: 0, borderRadius: '50%',
          border: '2px solid var(--accent)',
          animation: 'pulse-ring 1.4s ease-out infinite',
        }} />
        <div style={{
          position: 'absolute', inset: 8, borderRadius: '50%',
          border: '2px solid var(--accent)',
          opacity: 0.5,
          animation: 'pulse-ring 1.4s ease-out infinite 0.4s',
        }} />
        <div style={{
          position: 'absolute', inset: '50%', transform: 'translate(-50%,-50%)',
          width: 12, height: 12, borderRadius: '50%',
          background: 'var(--accent)',
        }} />
      </div>

      <div style={{ textAlign: 'center' }}>
        <div style={{
          fontFamily: "'Barlow Condensed', sans-serif", fontSize: 20,
          fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
          color: '#e8f4ff', marginBottom: 6,
        }}>
          Parsing {fileCount > 1 ? `${fileCount} files` : 'log file'}
        </div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--muted)', letterSpacing: '0.1em' }}>
          Analyzing log entries · extracting data points · building results
        </div>
      </div>

      <div style={{
        fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--accent)',
        opacity: 0.6, letterSpacing: '0.1em',
        animation: 'blink 1.2s step-end infinite',
      }}>
        Please wait…
      </div>

      <style>{`
        @keyframes pulse-ring {
          0%   { transform: scale(0.8); opacity: 1; }
          100% { transform: scale(1.8); opacity: 0; }
        }
        @keyframes blink {
          0%, 100% { opacity: 0.6; }
          50%       { opacity: 0.1; }
        }
      `}</style>
    </div>
  )
}

// ── Timestamp extraction (client-side, no parse needed) ──────────────────────

const TS_RE = /\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}/g

function extractTimeRange(text) {
  const hits = text.match(TS_RE)
  if (!hits || !hits.length) return null
  const sorted = hits.slice().sort()
  return { min: sorted[0], max: sorted[sorted.length - 1] }
}

function normaliseTs(ts) {
  // Make both formats comparable as Date objects
  return new Date(ts.replace(' ', 'T') + (ts.includes('Z') ? '' : 'Z'))
}

// ── Dual-handle range slider — hour-snapping ─────────────────────────────────

const HOUR_MS = 3_600_000

function snapDown(ms) { return Math.floor(ms / HOUR_MS) * HOUR_MS }
function snapUp(ms)   { return Math.ceil(ms  / HOUR_MS) * HOUR_MS }

function fmtHandle(ms) {
  // Show date only when span > 24h (multi-day sessions)
  const d = new Date(ms)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth()+1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:00 UTC`
}

function RangeSlider({ globalMin, globalMax, startMs, endMs, onChange }) {
  const trackRef = useRef(null)
  const span     = globalMax - globalMin || 1
  const spanHrs  = span / HOUR_MS

  // Adaptive tick interval: every 1hr if ≤24hrs, every 6hrs if >24hrs
  const tickIntervalHrs = spanHrs > 24 ? 6 : 1
  const tickIntervalMs  = tickIntervalHrs * HOUR_MS

  const pct = ms => ((ms - globalMin) / span) * 100

  const handleDrag = useCallback((which, e) => {
    e.preventDefault()
    const track = trackRef.current
    if (!track) return

    const move = (ev) => {
      const clientX = ev.touches ? ev.touches[0].clientX : ev.clientX
      const rect    = track.getBoundingClientRect()
      const ratio   = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
      const rawMs   = globalMin + ratio * span

      if (which === 'start') {
        // Snap down to hour — start rounds earlier to capture data
        const snapped = snapDown(rawMs)
        onChange(Math.min(snapped, endMs - HOUR_MS), endMs)
      } else {
        // Snap up to hour — end rounds later to capture data
        const snapped = snapUp(rawMs)
        onChange(startMs, Math.max(snapped, startMs + HOUR_MS))
      }
    }

    const up = () => {
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseup', up)
      window.removeEventListener('touchmove', move)
      window.removeEventListener('touchend', up)
    }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
    window.addEventListener('touchmove', move)
    window.addEventListener('touchend', up)
  }, [globalMin, startMs, endMs, onChange, span])

  const startPct = pct(startMs)
  const endPct   = pct(endMs)

  // Build tick marks at adaptive interval
  const ticks = []
  const firstTick = snapUp(globalMin)
  for (let t = firstTick; t <= globalMax; t += tickIntervalMs) {
    ticks.push(t)
  }

  return (
    <div style={{ padding: '4px 0 12px' }}>
      {/* Selected window labels */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--accent)', background: 'var(--accent)15', border: '1px solid var(--accent)40', borderRadius: 3, padding: '3px 8px' }}>
          ▶ {fmtHandle(startMs)}
        </div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--accent)', background: 'var(--accent)15', border: '1px solid var(--accent)40', borderRadius: 3, padding: '3px 8px' }}>
          {fmtHandle(endMs)} ◀
        </div>
      </div>

      {/* Track + handles */}
      <div ref={trackRef} style={{ position: 'relative', height: 8, background: 'var(--border2)', borderRadius: 4, userSelect: 'none', margin: '0 8px' }}>

        {/* Tick marks */}
        {ticks.map(t => (
          <div key={t} style={{
            position: 'absolute', top: 0, bottom: 0,
            left: `${pct(t)}%`,
            width: 1, background: '#ffffff18',
            pointerEvents: 'none',
          }} />
        ))}

        {/* Active range fill */}
        <div style={{
          position: 'absolute', top: 0, bottom: 0, borderRadius: 4,
          left: `${startPct}%`, width: `${endPct - startPct}%`,
          background: 'var(--accent)', opacity: 0.45,
        }} />

        {/* Start handle */}
        <div
          onMouseDown={e => handleDrag('start', e)}
          onTouchStart={e => handleDrag('start', e)}
          style={{
            position: 'absolute', top: '50%', left: `${startPct}%`,
            transform: 'translate(-50%, -50%)',
            width: 18, height: 18, borderRadius: '50%',
            background: 'var(--accent)', border: '2px solid #05080f',
            cursor: 'ew-resize', zIndex: 2,
            boxShadow: '0 0 8px var(--accent)',
          }}
        />

        {/* End handle */}
        <div
          onMouseDown={e => handleDrag('end', e)}
          onTouchStart={e => handleDrag('end', e)}
          style={{
            position: 'absolute', top: '50%', left: `${endPct}%`,
            transform: 'translate(-50%, -50%)',
            width: 18, height: 18, borderRadius: '50%',
            background: 'var(--accent)', border: '2px solid #05080f',
            cursor: 'ew-resize', zIndex: 2,
            boxShadow: '0 0 8px var(--accent)',
          }}
        />
      </div>

      {/* Tick labels — show every other tick to avoid crowding */}
      <div style={{ position: 'relative', height: 20, margin: '4px 8px 0' }}>
        {ticks.filter((_, i) => i % 2 === 0).map(t => {
          const d = new Date(t)
          const pad = n => String(n).padStart(2, '0')
          const label = spanHrs > 24
            ? `${pad(d.getUTCMonth()+1)}/${pad(d.getUTCDate())} ${pad(d.getUTCHours())}h`
            : `${pad(d.getUTCHours())}:00`
          return (
            <div key={t} style={{
              position: 'absolute',
              left: `${pct(t)}%`,
              transform: 'translateX(-50%)',
              fontFamily: 'var(--mono)', fontSize: 7,
              color: 'var(--muted)', whiteSpace: 'nowrap',
            }}>
              {label}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Modal drop zone ───────────────────────────────────────────────────────────

function UploadModal({ onFiles, loading, onClose }) {
  const [step,      setStep]     = useState('drop')   // 'drop' | 'range'
  const [pending,   setPending]  = useState([])
  const [globalMin, setGlobalMin] = useState(0)
  const [globalMax, setGlobalMax] = useState(0)
  const [startMs,   setStartMs]  = useState(0)
  const [endMs,     setEndMs]    = useState(0)
  const [scanning,  setScanning] = useState(false)

  const onDrop = useCallback(async (accepted) => {
    if (!accepted.length) return
    setPending(accepted)
    setScanning(true)

    // Scan files client-side for timestamps — no upload needed yet
    let absMin = Infinity, absMax = -Infinity
    for (const file of accepted) {
      try {
        // Read a sample: first 64KB + last 64KB is enough to find min/max timestamps
        const headSlice = file.slice(0, 65536)
        const tailSlice = file.slice(Math.max(0, file.size - 65536))
        const [headText, tailText] = await Promise.all([
          headSlice.text(),
          tailSlice.text(),
        ])
        const combined = headText + tailText
        const range = extractTimeRange(combined)
        if (range) {
          const minMs = normaliseTs(range.min).getTime()
          const maxMs = normaliseTs(range.max).getTime()
          if (minMs < absMin) absMin = minMs
          if (maxMs > absMax) absMax = maxMs
        }
      } catch { /* unparseable timestamps in this file — skip it for range scan */ }
    }

    setScanning(false)

    if (absMin === Infinity || absMax === -Infinity || absMin >= absMax) {
      // Could not detect timestamps — show the range step in a disabled state
      // so the user knows why filtering is unavailable rather than silently skipping
      setPending(accepted)
      setStep('range-unavailable')
      return
    }

    const snappedMin = snapDown(absMin)
    const snappedMax = snapUp(absMax)
    setGlobalMin(snappedMin)
    setGlobalMax(snappedMax)
    setStartMs(snappedMin)
    setEndMs(snappedMax)
    setStep('range')
  }, [onFiles, onClose])

  const handleConfirm = useCallback(() => {
    onFiles(pending, { startMs, endMs })
    onClose()
  }, [pending, startMs, endMs, onFiles, onClose])

  const handleRangeChange = useCallback((s, e) => {
    setStartMs(s)
    setEndMs(e)
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/plain': ['.txt'],
      'application/octet-stream': ['.log'],
      'text/x-log': ['.log'],
    },
    multiple: true,
    disabled: loading || step === 'range',
  })

  return createPortal(
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, background: '#00000080',
          zIndex: 100, backdropFilter: 'blur(2px)',
        }}
      />

      {/* Modal */}
      <div style={{
        position: 'fixed', top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)',
        zIndex: 101, width: step === 'range' ? 580 : 520, maxWidth: '90vw',
        background: 'var(--panel)', border: '1px solid var(--border2)',
        borderRadius: 10, padding: 28,
        boxShadow: '0 24px 80px #000a',
        transition: 'width 0.2s',
      }}>
        {/* Modal header */}
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
          <div>
            <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 16, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: '#c8ddf4' }}>
              {step === 'drop' ? 'Add Log Files' : step === 'range-unavailable' ? 'Select Time Window' : 'Select Time Window'}
            </div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--muted)', marginTop: 2 }}>
              {step === 'drop'
                ? 'Accepts .txt · .log · diagnostic, RSDK, ATAK, and Relay Manager formats'
                : step === 'range-unavailable'
                ? `${pending.length} file${pending.length > 1 ? 's' : ''} · time filtering unavailable · full log will be analysed`
                : `${pending.length} file${pending.length > 1 ? 's' : ''} · drag handles to narrow the analysis window · all times UTC`}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 18, lineHeight: 1, padding: '2px 6px' }}
          >
            ✕
          </button>
        </div>

        {step === 'drop' ? (
          <>
            {/* Drop zone */}
            <div
              {...getRootProps()}
              style={{
                border: `2px dashed ${isDragActive ? 'var(--accent)' : 'var(--border2)'}`,
                borderRadius: 8, padding: '36px 24px', textAlign: 'center',
                cursor: loading ? 'not-allowed' : 'pointer',
                background: isDragActive ? 'var(--accent)08' : 'var(--bg2)',
                transition: 'border-color 0.15s, background 0.15s',
              }}
            >
              <input {...getInputProps()} />
              {scanning ? (
                <>
                  <div style={{ fontSize: 24, marginBottom: 8 }}>🔍</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--accent)' }}>Scanning timestamps…</div>
                </>
              ) : (
                <>
                  <div style={{ fontSize: 32, marginBottom: 10 }}>📂</div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: '#c8ddf4', marginBottom: 6 }}>
                    {isDragActive ? 'Drop files here' : 'Drag & drop log files here'}
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--muted)', marginBottom: 16 }}>or</div>
                  <div style={{
                    display: 'inline-block', background: 'var(--accent)15',
                    border: '1px solid var(--accent)50', borderRadius: 5,
                    padding: '7px 20px', color: 'var(--accent)',
                    fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '0.06em',
                    textTransform: 'uppercase', cursor: 'pointer',
                  }}>
                    Browse Files
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--muted)', marginTop: 14 }}>
                    Multiple files supported · .txt and .log formats
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--accent)', marginTop: 6, opacity: 0.7 }}>
                    Tip: hold Ctrl (Windows) or ⌘ Cmd (Mac) to select multiple files at once
                  </div>
                </>
              )}
            </div>
          </>
        ) : step === 'range-unavailable' ? (
          <>
            {/* Time filtering unavailable — no parseable timestamps found */}
            <div style={{ padding: '8px 0 20px' }}>
              <div style={{
                background: '#ffd16615', border: '1px solid #ffd16640',
                borderRadius: 6, padding: '12px 16px', marginBottom: 20,
                display: 'flex', gap: 10, alignItems: 'flex-start',
              }}>
                <span style={{ fontSize: 14, marginTop: 1 }}>⚠</span>
                <div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: '#ffd166', letterSpacing: '0.04em', marginBottom: 4 }}>
                    Time filtering unavailable
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--muted)', lineHeight: 1.6 }}>
                    No parseable timestamps were found in {pending.length > 1 ? 'these files' : 'this file'}.
                    Relay Manager logcat logs omit the year from timestamps — the time window
                    step requires a full date to work. Analysis will use the full log contents.
                  </div>
                </div>
              </div>

              {/* Disabled slider placeholder */}
              <div style={{ opacity: 0.25, pointerEvents: 'none', padding: '4px 0 12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--muted)', background: 'var(--border2)', border: '1px solid var(--border2)', borderRadius: 3, padding: '3px 8px' }}>▶ — unavailable —</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--muted)', background: 'var(--border2)', border: '1px solid var(--border2)', borderRadius: 3, padding: '3px 8px' }}>— unavailable — ◀</div>
                </div>
                <div style={{ height: 8, background: 'var(--border2)', borderRadius: 4, margin: '0 8px' }} />
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setStep('drop')}
                style={{ background: 'none', border: '1px solid var(--border2)', color: 'var(--muted)', borderRadius: 4, padding: '7px 14px', cursor: 'pointer', fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.06em', textTransform: 'uppercase' }}
              >
                ← Back
              </button>
              <button
                onClick={() => { onFiles(pending); onClose() }}
                style={{ background: 'var(--accent)15', border: '1px solid var(--accent)50', color: 'var(--accent)', borderRadius: 4, padding: '7px 20px', cursor: 'pointer', fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.06em', textTransform: 'uppercase' }}
              >
                Analyse →
              </button>
            </div>
          </>
        ) : (
          <>
            {/* Range slider step */}
            <RangeSlider
              globalMin={globalMin}
              globalMax={globalMax}
              startMs={startMs}
              endMs={endMs}
              onChange={handleRangeChange}
            />

            {/* Duration summary */}
            <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--muted)', textAlign: 'center', marginBottom: 18 }}>
              {(() => {
                const mins = Math.round((endMs - startMs) / 60000)
                const hrs  = Math.floor(mins / 60)
                const rem  = mins % 60
                return hrs > 0 ? `${hrs}h ${rem}m selected` : `${mins}m selected`
              })()}
            </div>

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => { setStartMs(globalMin); setEndMs(globalMax) }}
                style={{ background: 'none', border: '1px solid var(--border2)', color: 'var(--muted)', borderRadius: 4, padding: '7px 14px', cursor: 'pointer', fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.06em', textTransform: 'uppercase' }}
              >
                Full Range
              </button>
              <button
                onClick={() => setStep('drop')}
                style={{ background: 'none', border: '1px solid var(--border2)', color: 'var(--muted)', borderRadius: 4, padding: '7px 14px', cursor: 'pointer', fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.06em', textTransform: 'uppercase' }}
              >
                ← Back
              </button>
              <button
                onClick={handleConfirm}
                style={{ background: 'var(--accent)15', border: '1px solid var(--accent)50', color: 'var(--accent)', borderRadius: 4, padding: '7px 20px', cursor: 'pointer', fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.06em', textTransform: 'uppercase' }}
              >
                Analyse →
              </button>
            </div>
          </>
        )}
      </div>
    </>,
    document.body
  )
}

// ── Trigger button + modal ────────────────────────────────────────────────────

export default function FileUpload({ onFiles, loading, error, variant = 'header' }) {
  const [open, setOpen] = useState(false)

  // Initial full-page upload (no results yet)
  if (variant === 'page') {
    return (
      <>
        <div style={{ maxWidth: 520, margin: '0 auto', width: '100%', textAlign: 'center' }}>
          <div style={{ fontSize: 42, marginBottom: 16 }}>📡</div>
          <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 28, fontWeight: 400, letterSpacing: '0.04em', color: '#e8f4ff', marginBottom: 8 }}>
            go<span style={{ color: '#e8f4ff' }}>Tenna</span> Log Parser
          </div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--muted)', marginBottom: 28 }}>
            Upload diagnostic, RSDK, or ATAK log files to begin analysis
          </div>
          <button
            onClick={() => setOpen(true)}
            style={{
              background: 'var(--accent)15', border: '1px solid var(--accent)60',
              color: 'var(--accent)', borderRadius: 6, padding: '12px 32px',
              cursor: 'pointer', fontFamily: "'Barlow Condensed', sans-serif",
              fontSize: 16, fontWeight: 700, letterSpacing: '0.08em',
              textTransform: 'uppercase', transition: 'background 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--accent)25'}
            onMouseLeave={e => e.currentTarget.style.background = 'var(--accent)15'}
          >
            Upload Log Files
          </button>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--muted)', marginTop: 12 }}>
            .txt · .log · multiple files supported
          </div>
          {error && (
            <div style={{ marginTop: 16, padding: '10px 14px', background: 'var(--red)15', border: '1px solid var(--red)40', borderRadius: 6, fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--red)' }}>
              ⚠ {error}
            </div>
          )}
        </div>

        {open && <UploadModal onFiles={onFiles} loading={loading} onClose={() => setOpen(false)} />}
      </>
    )
  }

  // Header button variant
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        style={{
          background: 'var(--accent)15', border: '1px solid var(--accent)40',
          color: 'var(--accent)', borderRadius: 4, padding: '5px 12px',
          cursor: 'pointer', fontFamily: 'var(--mono)', fontSize: 9,
          letterSpacing: '0.06em', textTransform: 'uppercase',
          transition: 'background 0.15s',
        }}
        onMouseEnter={e => e.currentTarget.style.background = 'var(--accent)25'}
        onMouseLeave={e => e.currentTarget.style.background = 'var(--accent)15'}
      >
        + Add Log Files
      </button>

      {open && <UploadModal onFiles={onFiles} loading={loading} onClose={() => setOpen(false)} />}
    </>
  )
}
