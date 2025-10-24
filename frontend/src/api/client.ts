import type {
  AttendanceProcessResponse,
  HistoryResponse,
  ProcessAttendancePayload,
} from '../types'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api/v1'

export async function processAttendance(
  payload: ProcessAttendancePayload,
): Promise<AttendanceProcessResponse> {
  const formData = new FormData()
  formData.append('attendance_file', payload.attendanceFile)
  if (payload.gradebookFile) {
    formData.append('gradebook_file', payload.gradebookFile)
  }
  formData.append('start_date', payload.startDate)
  formData.append('end_date', payload.endDate)
  formData.append('out_prefix', payload.outPrefix)
  formData.append('join_mode', payload.joinMode)
  formData.append('matrix', String(payload.matrix))

  const response = await fetch(`${API_BASE}/attendance/process`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || 'Unable to process attendance')
  }

  return response.json()
}

export async function fetchHistory(): Promise<HistoryResponse> {
  const response = await fetch(`${API_BASE}/history`)
  if (!response.ok) {
    throw new Error('Unable to fetch history')
  }
  return response.json()
}

export async function fetchHealth(): Promise<{ app: string; status: string }> {
  const base = API_BASE.endsWith('/v1') ? API_BASE.slice(0, -3) : API_BASE
  const response = await fetch(`${base}/health`)
  if (!response.ok) {
    throw new Error('API offline')
  }
  return response.json()
}
