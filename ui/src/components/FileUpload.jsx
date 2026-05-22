import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'

// ── Modal drop zone ───────────────────────────────────────────────────────────

function UploadModal({ onFiles, loading, onClose }) {
  const onDrop = useCallback((accepted) => {
    if (accepted.length > 0) {
      onFiles(accepted)
      onClose()
    }
  }, [onFiles, onClose])

  const { getRootProps, getInputProps, isDragActive, acceptedFiles } = useDropzone({
    onDrop,
    accept: {
      'text/plain': ['.txt'],
      'application/octet-stream': ['.log'],
      'text/x-log': ['.log'],
    },
    multiple: true,
    disabled: loading,
  })

  return (
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
        zIndex: 101, width: 520, maxWidth: '90vw',
        background: 'var(--panel)', border: '1px solid var(--border2)',
        borderRadius: 10, padding: 28,
        boxShadow: '0 24px 80px #000a',
      }}>
        {/* Modal header */}
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
          <div>
            <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 16, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: '#c8ddf4' }}>
              Add Log Files
            </div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--muted)', marginTop: 2 }}>
              Accepts .txt · .log · diagnostic, RSDK, and ATAK formats
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 18, lineHeight: 1, padding: '2px 6px' }}
          >
            ✕
          </button>
        </div>

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
          <div style={{ fontSize: 32, marginBottom: 10 }}>📂</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#c8ddf4', marginBottom: 6 }}>
            {loading ? 'Parsing…' : isDragActive ? 'Drop files here' : 'Drag & drop log files here'}
          </div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--muted)', marginBottom: 16 }}>
            or
          </div>
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
        </div>
      </div>
    </>
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

  // Header button variant (used when results are loaded)
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
