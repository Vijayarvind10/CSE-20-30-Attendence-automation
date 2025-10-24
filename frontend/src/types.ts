export interface AttendanceSummary {
  students_total: number
  students_with_attendance: number
  coverage_pct: number
  lecture_dates: string[]
  generated_at?: string
}

export interface ProcessedArtifact {
  filename: string
  relative_path: string
}

export interface AttendanceProcessResponse {
  message: string
  summary: AttendanceSummary
  counts_preview: Record<string, string | number>[]
  counts_artifact: ProcessedArtifact
  matrix_artifact?: ProcessedArtifact | null
}

export interface HistoryItem {
  id: string
  course: string
  requested_by: string
  run_at: string
  status: 'success' | 'error' | 'pending'
  notes?: string | null
}

export interface HistoryResponse {
  items: HistoryItem[]
}

export interface ProcessAttendancePayload {
  attendanceFile: File
  gradebookFile?: File | null
  startDate: string
  endDate: string
  outPrefix: string
  joinMode: string
  matrix: boolean
}
