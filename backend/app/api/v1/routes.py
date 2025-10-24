from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.config import Settings, get_settings
from app.schemas import AttendanceProcessResponse, HistoryItem, HistoryResponse
from app.services.attendance_service import AttendanceService

router = APIRouter()


def get_attendance_service(settings: Settings = Depends(get_settings)) -> AttendanceService:
    return AttendanceService(settings)


@router.get("/health")
async def health_check(settings: Settings = Depends(get_settings)) -> dict:
    return {"app": settings.app_name, "status": "ok"}


@router.post("/attendance/process", response_model=AttendanceProcessResponse)
async def process_attendance(
    attendance_file: UploadFile = File(..., description="Zoom/Google attendance export"),
    gradebook_file: UploadFile | None = File(
        default=None, description="Optional Canvas gradebook/roster CSV for joining"
    ),
    start_date: str = Form(..., description="Start date in YYYY-MM-DD"),
    end_date: str = Form(..., description="End date in YYYY-MM-DD"),
    out_prefix: str = Form("attendance"),
    join_mode: str = Form("auto"),
    matrix: bool = Form(True),
    service: AttendanceService = Depends(get_attendance_service),
) -> AttendanceProcessResponse:
    return await service.process(
        attendance_file=attendance_file,
        gradebook_file=gradebook_file,
        start_date=start_date,
        end_date=end_date,
        out_prefix=out_prefix,
        join_mode=join_mode,
        matrix=matrix,
    )


@router.get("/history", response_model=HistoryResponse)
async def history_stub() -> HistoryResponse:
    sample_items: List[HistoryItem] = [
        HistoryItem(
            id="demo-1",
            course="CSE 20 - Fall 2025",
            requested_by="larissa@ucsc.edu",
            run_at=datetime.utcnow(),
            status="success",
            notes="Uploaded to Canvas",
        )
    ]
    return HistoryResponse(items=sample_items)
