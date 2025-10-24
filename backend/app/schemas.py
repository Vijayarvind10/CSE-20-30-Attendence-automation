from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class AttendanceSummary(BaseModel):
    students_total: int = 0
    students_with_attendance: int = 0
    coverage_pct: float = 0.0
    lecture_dates: List[date] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ProcessedArtifact(BaseModel):
    filename: str
    relative_path: str


class AttendanceProcessResponse(BaseModel):
    message: str
    summary: AttendanceSummary
    counts_preview: List[Dict[str, Any]] = Field(default_factory=list)
    counts_artifact: ProcessedArtifact
    matrix_artifact: Optional[ProcessedArtifact] = None


class HistoryItem(BaseModel):
    id: str
    course: str
    requested_by: str
    run_at: datetime
    status: Literal["success", "error", "pending"]
    notes: Optional[str] = None


class HistoryResponse(BaseModel):
    items: List[HistoryItem]
