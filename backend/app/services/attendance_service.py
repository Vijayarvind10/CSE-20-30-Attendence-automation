from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

import pandas as pd
from fastapi import UploadFile

from app.attendance_automator import (
    dedup_same_day,
    filter_weeks,
    finalize_output,
    load_attendance,
    load_gradebook_csv,
    normalize_email,
    try_join_modes,
    write_csv,
    write_matrix,
    compute_counts,
)
from app.schemas import AttendanceProcessResponse, AttendanceSummary, ProcessedArtifact
from app.core.config import Settings


class AttendanceService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def process(
        self,
        attendance_file: UploadFile,
        start_date: str,
        end_date: str,
        out_prefix: str,
        join_mode: str,
        matrix: bool,
        gradebook_file: Optional[UploadFile] = None,
    ) -> AttendanceProcessResponse:
        attendance_path = await self._persist_upload(attendance_file)
        gradebook_path = await self._persist_upload(gradebook_file) if gradebook_file else None

        result = await asyncio.get_event_loop().run_in_executor(
            None,
            self._run_processing,
            attendance_path,
            gradebook_path,
            start_date,
            end_date,
            out_prefix,
            join_mode,
            matrix,
        )

        return result

    async def _persist_upload(self, upload: UploadFile | None) -> Path:
        if upload is None:
            raise ValueError("Upload file expected but missing")
        suffix = Path(upload.filename or "upload.csv").suffix or ".csv"
        dest = self.settings.upload_dir / f"{uuid4().hex}{suffix}"
        contents = await upload.read()
        dest.write_bytes(contents)
        upload.file.close()
        return dest

    def _run_processing(
        self,
        attendance_path: Path,
        gradebook_path: Optional[Path],
        start_date: str,
        end_date: str,
        out_prefix: str,
        join_mode: str,
        matrix: bool,
    ) -> AttendanceProcessResponse:
        attendance_df = load_attendance(attendance_path)
        filtered = dedup_same_day(filter_weeks(attendance_df, start_date, end_date))
        counts_out, lecture_dates, week1, week2 = compute_counts(filtered)
        six_dates = (week1 + week2)[:6]

        if gradebook_path is not None:
            roster = load_gradebook_csv(gradebook_path)
            if join_mode == "auto":
                merged, mode, coverage = try_join_modes(counts_out, roster)
            elif join_mode == "id":
                counts_out["__id"] = counts_out["__id"].astype(str).str.strip()
                merged = roster.merge(counts_out, left_on="ID_str", right_on="__id", how="left")
            elif join_mode == "email":
                counts_out["__email_norm"] = counts_out["__email"].map(normalize_email)
                if "SIS Login ID_norm" in roster.columns:
                    merged = roster.merge(counts_out, left_on="SIS Login ID_norm", right_on="__email_norm", how="left")
                else:
                    merged = roster.merge(counts_out, left_on="Email_norm", right_on="__email_norm", how="left")
            else:
                merged = counts_out
            output_df = finalize_output(merged)
        else:
            output_df = counts_out.rename(columns={"__name": "Student", "__id": "ID", "__email": "Email"})[
                ["Student", "ID", "Email", "week1_count", "week2_count", "total_count", "max_possible", "percentage"]
            ]

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        safe_prefix = out_prefix or "attendance"
        counts_filename = f"{safe_prefix}_{timestamp}_attendance_counts.csv"
        counts_path = self.settings.output_dir / counts_filename
        write_csv(output_df, counts_path)

        matrix_artifact: Optional[ProcessedArtifact] = None
        if matrix:
            matrix_filename = f"{safe_prefix}_{timestamp}_attendance_matrix.csv"
            matrix_path = self.settings.output_dir / matrix_filename
            write_matrix(filtered, six_dates, matrix_path)
            matrix_artifact = ProcessedArtifact(
                filename=matrix_filename,
                relative_path=str(matrix_path.relative_to(Path.cwd())),
            )

        counts_artifact = ProcessedArtifact(
            filename=counts_filename,
            relative_path=str(counts_path.relative_to(Path.cwd())),
        )

        attendance_series = (
            output_df["total_count"].fillna(0) if "total_count" in output_df.columns else pd.Series([0] * len(output_df))
        )
        students_with_attendance = int((attendance_series > 0).sum())
        coverage_pct = float((students_with_attendance / len(output_df) * 100.0) if len(output_df) else 0.0)

        summary = AttendanceSummary(
            students_total=len(output_df),
            students_with_attendance=students_with_attendance,
            coverage_pct=coverage_pct,
            lecture_dates=lecture_dates,
        )

        preview = self._build_preview(output_df)

        return AttendanceProcessResponse(
            message="Attendance processed successfully",
            summary=summary,
            counts_preview=preview,
            counts_artifact=counts_artifact,
            matrix_artifact=matrix_artifact,
        )

    def _build_preview(self, df: pd.DataFrame, limit: int = 20) -> List[Dict[str, object]]:
        preview_df = df.head(limit).copy()
        for col in ["percentage"]:
            if col in preview_df.columns:
                preview_df[col] = preview_df[col].round(2)
        return preview_df.fillna("").to_dict(orient="records")
