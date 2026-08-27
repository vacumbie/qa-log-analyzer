// tests/js/run_extract_time_range.mjs
//
// Executes the REAL extractTimeRange() out of ui/src/components/FileUpload.jsx
// and prints its result as JSON. Driven by tests/test_time_range_exec.py.
//
// Why this exists: tests/test_time_range_scan.py guards the regex *literals* by
// re-running them in Python, which cannot see the union order, ctimeToMs()'s
// month lookup, UTC-vs-local, or the head/tail sampling. Those are the parts
// that turn three correct regexes into one wrong range.
//
// Why it isn't a JS test runner: CLAUDE.md forbids adding npm packages unless
// Chart.js/React/plain CSS can't do the job. Node is already required to run
// Vite, so shelling out to it adds no dependency. Nothing is imported from the
// component — it is a JSX module with React imports, so it can't be imported
// directly; the pure functions are lifted out by name instead.
//
// Usage:  node run_extract_time_range.mjs <out.json> <FileUpload.jsx> <input...>
// Writes: {"minMs":…,"maxMs":…} | null   (or {"error":…} with exit 1) to out.json
//
// The result goes to a file rather than stdout because `node` on Windows often
// resolves to a WindowsApps .CMD shim that echoes the command line before the
// program's own output, which is not stripped by capture and is not valid JSON.

import { readFileSync, writeFileSync } from 'node:fs'

const [, , outPath, componentPath, ...inputPaths] = process.argv

function emit(value, code = 0) {
  writeFileSync(outPath, JSON.stringify(value), 'utf8')
  process.exit(code)
}

function fail(message) {
  emit({ error: message }, 1)
}

if (!outPath || !componentPath || inputPaths.length === 0) {
  console.error('usage: run_extract_time_range.mjs <out.json> <FileUpload.jsx> <input...>')
  process.exit(2)
}

const source = readFileSync(componentPath, 'utf8')

// Lift the pure scanner out of the component by name. Each pattern must match
// exactly once — if a refactor renames or removes one, this fails loudly rather
// than silently testing a stale copy.
const CONSTS = ['TS_RE', 'EPOCH_MS_RE', 'XML_TS_ATTR_RE', 'CTIME_RE', 'CTIME_MONTHS']
const FUNCS = ['extractTimeRange', 'normaliseTs', 'ctimeToMs']

const parts = []
for (const name of CONSTS) {
  const m = source.match(new RegExp(`^const ${name} = .*$`, 'm'))
  if (!m) fail(`FileUpload.jsx no longer defines a top-level const ${name}`)
  parts.push(m[0])
}
for (const name of FUNCS) {
  // Brace-balanced to the closing brace at column 0 — these are all top-level.
  const m = source.match(new RegExp(`^function ${name}\\([\\s\\S]*?\\n\\}`, 'm'))
  if (!m) fail(`FileUpload.jsx no longer defines a top-level function ${name}`)
  parts.push(m[0])
}

let extractTimeRange
try {
  extractTimeRange = new Function(`${parts.join('\n')}\nreturn extractTimeRange`)()
} catch (e) {
  fail(`lifted scanner did not evaluate: ${e.message}`)
}

// Multiple inputs are concatenated the way FileUpload's onDrop concatenates the
// sampled text of several dropped files into one combined range.
const text = inputPaths.map(p => readFileSync(p, 'utf8')).join('\n')
emit(extractTimeRange(text))
