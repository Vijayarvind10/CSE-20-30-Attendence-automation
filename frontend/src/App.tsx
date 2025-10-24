import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { fetchHealth, fetchHistory, processAttendance } from './api/client'
import type { AttendanceProcessResponse, HistoryItem } from './types'

const joinModeOptions = [
  { value: 'auto', label: 'Auto (ID or Email)' },
  { value: 'id', label: 'Force ID Match' },
  { value: 'email', label: 'Force Email Match' },
  { value: 'none', label: 'No Gradebook Join' },
]

const formatInputDate = (date: Date) => date.toISOString().slice(0, 10)

function App() {
  const today = useMemo(() => new Date(), [])
  const defaultStart = useMemo(() => {
    const copy = new Date(today)
    copy.setDate(copy.getDate() - 7)
    return formatInputDate(copy)
  }, [today])

  const [health, setHealth] = useState<'loading' | 'online' | 'offline'>('loading')
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [attendanceFile, setAttendanceFile] = useState<File | null>(null)
  const [gradebookFile, setGradebookFile] = useState<File | null>(null)
  const [startDate, setStartDate] = useState(defaultStart)
  const [endDate, setEndDate] = useState(formatInputDate(today))
  const [joinMode, setJoinMode] = useState('auto')
  const [outPrefix, setOutPrefix] = useState('CSE20_Week1_2')
  const [matrix, setMatrix] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<AttendanceProcessResponse | null>(null)

  useEffect(() => {
    fetchHealth()
      .then(() => setHealth('online'))
      .catch(() => setHealth('offline'))
    fetchHistory()
      .then((res) => setHistory(res.items))
      .catch(() => setHistory([]))
  }, [])

  const statusBadge = {
    loading: 'bg-yellow-100 text-yellow-700',
    online: 'bg-emerald-100 text-emerald-700',
    offline: 'bg-rose-100 text-rose-700',
  }[health]

  const handleSubmit = async (evt: FormEvent<HTMLFormElement>) => {
    evt.preventDefault()
    setError(null)

    if (!attendanceFile) {
      setError('Upload an attendance CSV first.')
      return
    }

    setIsSubmitting(true)
    try {
      const response = await processAttendance({
        attendanceFile,
        gradebookFile: joinMode === 'none' ? null : gradebookFile,
        startDate,
        endDate,
        joinMode,
        outPrefix,
        matrix,
      })
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unexpected error')
    } finally {
      setIsSubmitting(false)
    }
  }

  const renderPreviewTable = () => {
    if (!result) return null
    if (!result.counts_preview.length) {
      return <p className="text-slate-500 text-sm">No rows to preview.</p>
    }

    const columns = Object.keys(result.counts_preview[0])
    return (
      <div className="overflow-auto rounded-xl border border-slate-100">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              {columns.map((col) => (
                <th key={col} className="px-4 py-2 text-left font-semibold text-slate-600">
                  {col.replace(/_/g, ' ')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.counts_preview.map((row, idx) => {
              const rowKey = String(row['Student'] ?? row['ID'] ?? idx)
              return (
                <tr key={`${rowKey}-${idx}`} className="odd:bg-white even:bg-slate-50/50">
                  {columns.map((col) => (
                    <td key={col} className="px-4 py-2 text-slate-700">
                      {row[col] ?? ''}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className="px-4 py-10 sm:px-6 lg:px-10">
      <div className="mx-auto max-w-6xl space-y-10">
        <header className="rounded-3xl bg-white/80 p-8 shadow-card backdrop-blur">
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-white">
              UCSC Faculty Tooling
            </span>
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusBadge}`}>
              API {health}
            </span>
          </div>
          <div className="mt-6 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h1 className="text-3xl font-bold text-slate-900 sm:text-4xl">
                Attendance Automator Web Platform
              </h1>
              <p className="mt-3 max-w-2xl text-lg text-slate-600">
                Import Zoom exports, generate attendance matrices, and sync to Canvas in one guided flow.
              </p>
            </div>
            <div className="rounded-2xl border border-slate-100 bg-slate-50 px-5 py-3 text-sm text-slate-600">
              <p className="font-semibold text-slate-900">Current Window</p>
              <p>
                {startDate} → {endDate}
              </p>
            </div>
          </div>
        </header>

        <main className="grid gap-8 lg:grid-cols-[2fr,1fr]">
          <section className="space-y-8">
            <form onSubmit={handleSubmit} className="space-y-6 rounded-3xl bg-white p-8 shadow-card">
              <div className="grid gap-6 lg:grid-cols-2">
                <div>
                  <label className="text-sm font-medium text-slate-700">Attendance CSV *</label>
                  <input
                    type="file"
                    accept=".csv,.tsv,.xlsx"
                    onChange={(evt) => setAttendanceFile(evt.target.files?.[0] ?? null)}
                    className="mt-2 w-full rounded-2xl border border-dashed border-slate-300 bg-slate-50/50 px-4 py-3 text-sm"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700">Canvas Gradebook (optional)</label>
                  <input
                    type="file"
                    accept=".csv,.tsv,.xlsx"
                    disabled={joinMode === 'none'}
                    onChange={(evt) => setGradebookFile(evt.target.files?.[0] ?? null)}
                    className="mt-2 w-full rounded-2xl border border-dashed border-slate-300 bg-slate-50/50 px-4 py-3 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700">Start date</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(evt) => setStartDate(evt.target.value)}
                    className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700">End date</label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(evt) => setEndDate(evt.target.value)}
                    className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700">Output prefix</label>
                  <input
                    type="text"
                    value={outPrefix}
                    onChange={(evt) => setOutPrefix(evt.target.value)}
                    className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700">Join mode</label>
                  <select
                    value={joinMode}
                    onChange={(evt) => setJoinMode(evt.target.value)}
                    className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm"
                  >
                    {joinModeOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-slate-50 px-4 py-3">
                <label className="flex items-center gap-3 text-sm font-medium text-slate-700">
                  <input
                    type="checkbox"
                    checked={matrix}
                    onChange={(evt) => setMatrix(evt.target.checked)}
                    className="h-4 w-4 rounded border-slate-300 text-secondary focus:ring-secondary"
                  />
                  Generate per-lecture matrix CSV
                </label>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="rounded-2xl bg-secondary px-6 py-2 text-sm font-semibold text-white shadow-lg transition hover:bg-secondary/90 disabled:opacity-50"
                >
                  {isSubmitting ? 'Processing...' : 'Process Attendance'}
                </button>
              </div>

              {error && <p className="text-sm text-rose-600">{error}</p>}
            </form>

            {result && (
              <section className="space-y-6 rounded-3xl bg-white p-8 shadow-card">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-500">Latest run</p>
                    <h2 className="text-2xl font-semibold text-slate-900">{result.message}</h2>
                  </div>
                  <div className="text-right text-sm text-slate-500">
                    <p>
                      Students covered:{' '}
                      <span className="font-semibold text-slate-900">
                        {result.summary.students_with_attendance}/{result.summary.students_total}
                      </span>
                    </p>
                    <p>Coverage {result.summary.coverage_pct.toFixed(1)}%</p>
                  </div>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-2xl border border-slate-100 p-4">
                    <p className="text-xs font-semibold uppercase text-slate-500">Counts CSV</p>
                    <p className="text-sm text-slate-900">{result.counts_artifact.filename}</p>
                    <p className="text-xs text-slate-500">{result.counts_artifact.relative_path}</p>
                  </div>
                  {result.matrix_artifact && (
                    <div className="rounded-2xl border border-slate-100 p-4">
                      <p className="text-xs font-semibold uppercase text-slate-500">Matrix CSV</p>
                      <p className="text-sm text-slate-900">{result.matrix_artifact.filename}</p>
                      <p className="text-xs text-slate-500">{result.matrix_artifact.relative_path}</p>
                    </div>
                  )}
                </div>
                <div>
                  <p className="mb-3 text-sm font-semibold text-slate-600">Preview (first 20 rows)</p>
                  {renderPreviewTable()}
                </div>
              </section>
            )}
          </section>

          <aside className="space-y-6 rounded-3xl bg-white p-6 shadow-card">
            <div>
              <h3 className="text-lg font-semibold text-slate-900">Recent runs</h3>
              <p className="text-sm text-slate-500">Canvas sync audit trail</p>
            </div>
            <div className="space-y-5">
              {history.map((item) => (
                <div key={item.id} className="rounded-2xl border border-slate-100 p-4">
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span>{new Date(item.run_at).toLocaleString()}</span>
                    <span
                      className={`rounded-full px-2 py-1 font-semibold ${
                        item.status === 'success'
                          ? 'bg-emerald-100 text-emerald-700'
                          : item.status === 'pending'
                            ? 'bg-amber-100 text-amber-700'
                            : 'bg-rose-100 text-rose-700'
                      }`}
                    >
                      {item.status}
                    </span>
                  </div>
                  <p className="mt-2 text-sm font-semibold text-slate-900">{item.course}</p>
                  <p className="text-xs text-slate-500">Requested by {item.requested_by}</p>
                  {item.notes && <p className="mt-2 text-xs text-slate-500">{item.notes}</p>}
                </div>
              ))}
              {!history.length && (
                <p className="text-sm text-slate-500">History will appear after your first run.</p>
              )}
            </div>
          </aside>
        </main>
      </div>
    </div>
  )
}

export default App
