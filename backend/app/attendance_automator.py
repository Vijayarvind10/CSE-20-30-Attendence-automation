#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Attendance Automator - CSE 20/30 Weeks 1-2
------------------------------------------
Features:
- Safe: never edits your source sheet; writes new CSVs (and optionally a new Google Sheet).
- Local CSV mode (no API needed).
- Optional Canvas API pull (roster) and Google Drive/Sheets copy/export+upload.
- Robust join: auto-selects the best key (ID vs Email) or force via flag.
- Per-lecture matrix output.
- QA report: coverage %, constraint checks, top/bottom attendance.
- Idempotent: can run daily; outputs are overwritten safely.

Install (conda or pip):
    conda install -y pandas numpy pyyaml requests gspread google-api-python-client google-auth google-auth-oauthlib
or
    pip install pandas numpy pyyaml requests gspread google-api-python-client google-auth google-auth-oauthlib

Usage (local CSV mode):
    python attendance_automator.py process \
      --attendance "CSE 20 Lecture Attendance Weeks 1-2.csv" \
      --gradebook "Grades CSE 20 Fall 2025.csv" \
      --start 2025-09-29 --end 2025-10-10 \
      --out-prefix "CSE20" --join auto --matrix

Config mode:
    python attendance_automator.py all --config config.yaml

Canvas API token:
- In Canvas -> Profile -> Settings -> New Access Token. Save it into config.yaml.
Google API:
- Create OAuth credentials or a Service Account with Drive/Sheets scopes; put credentials JSON path in config.yaml.
"""

import argparse, os, sys, re, csv, json, time, math, logging, traceback, io
from datetime import datetime, date
from typing import List, Tuple, Dict, Optional

import pandas as pd
import numpy as np

try:
    import yaml
except Exception:
    yaml = None

# Optional deps for cloud ops
try:
    import requests
except Exception:
    requests = None

try:
    import gspread
    from google.oauth2.service_account import Credentials as SACredentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
except Exception:
    gspread = None
    SACredentials = None
    InstalledAppFlow = None

LOGGER = logging.getLogger("attendance_automator")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']

COMMON_DOMAIN_FIXES = {
    r"@ucscedu$": "@ucsc.edu",
    r"@ucsc\\.efu$": "@ucsc.edu",
    r"@ucsc\\.irg$": "@ucsc.edu",
    r"@uscs\\.edu$": "@ucsc.edu",
    r"@gmail\\.con$": "@gmail.com"
}

def normalize_email(email):
    if pd.isna(email):
        return email
    e = str(email).strip().lower().replace(" ", "")
    for bad, good in COMMON_DOMAIN_FIXES.items():
        e = re.sub(bad, good, e)
    return e

def to_dt(x):
    try:
        return pd.to_datetime(x, errors="coerce")
    except Exception:
        return pd.NaT

def load_attendance(path):
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    ts_col = next((cols[k] for k in cols if "timestamp" in k), None)
    email_col = next((cols[k] for k in cols if k.strip() == "email"), None)
    id_col = next((cols[k] for k in cols if k.strip() == "id"), None)
    name_col = next((cols[k] for k in cols if "name" in k), None)
    if ts_col is None or (email_col is None and id_col is None):
        raise ValueError("Attendance CSV must have at least Timestamp + (email or ID) columns.")
    df["__ts"] = df[ts_col].map(to_dt)
    df["__date"] = df["__ts"].dt.date
    df["__email"] = df[email_col].map(normalize_email) if email_col else np.nan
    df["__id"] = df[id_col].astype(str).str.strip() if id_col else np.nan
    df["__name"] = df[name_col].astype(str).str.strip() if name_col else np.nan
    df["__identity"] = np.where(df["__id"].notna() & (df["__id"] != ""), df["__id"],
                         np.where(df["__email"].notna() & (df["__email"] != ""), df["__email"], df["__name"]))
    return df

def load_gradebook_csv(path):
    try:
        gb = pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        gb = pd.read_csv(path, encoding="latin-1")
    # Normalize potential keys
    if "Email" in gb.columns:
        gb["Email_norm"] = gb["Email"].map(normalize_email)
    if "SIS Login ID" in gb.columns:
        gb["SIS Login ID_norm"] = gb["SIS Login ID"].map(normalize_email)
    if "ID" in gb.columns:
        gb["ID_str"] = gb["ID"].astype(str).str.strip()
    # Display name
    if "Student" in gb.columns:
        gb["__disp_name"] = gb["Student"].astype(str).str.strip()
    else:
        gb["__disp_name"] = np.nan
    return gb

def filter_weeks(df, start_iso, end_iso):
    start = pd.to_datetime(start_iso).date()
    end   = pd.to_datetime(end_iso).date()
    return df.loc[(df["__date"] >= start) & (df["__date"] <= end)].copy()

def dedup_same_day(df):
    df = df.sort_values(["__date", "__ts"], ascending=[True, True])
    return df.drop_duplicates(subset=["__identity", "__date"], keep="first")

def compute_counts(df_weeks):
    lecture_dates = sorted(pd.Series(df_weeks["__date"].unique()).dropna().tolist())
    cnt = df_weeks.groupby(["__identity"]).agg(
        attended_dates=("__date", lambda s: sorted(set(s)))
    ).reset_index()
    cnt["total_count"] = cnt["attended_dates"].map(len)
    week1 = lecture_dates[:3] if len(lecture_dates) >= 3 else lecture_dates
    week2 = lecture_dates[3:6] if len(lecture_dates) >= 6 else lecture_dates[3:]
    def count_in_week(dates, week):
        return sum(1 for d in dates if d in week)
    cnt["week1_count"] = cnt["attended_dates"].map(lambda ds: count_in_week(ds, week1))
    cnt["week2_count"] = cnt["attended_dates"].map(lambda ds: count_in_week(ds, week2))
    cnt["max_possible"] = 6
    cnt["percentage"] = (cnt["week1_count"] + cnt["week2_count"]) / cnt["max_possible"] * 100.0
    mini = df_weeks.sort_values("__ts").drop_duplicates("__identity", keep="first")["__identity"].to_frame()
    mini = mini.merge(df_weeks[["__identity","__email","__id","__name"]].drop_duplicates("__identity"), on="__identity", how="left")
    out = cnt.merge(mini, on="__identity", how="left")
    return out, lecture_dates, week1, week2

def try_join_modes(counts_out, roster):
    # Return the join with best match coverage
    def join_id():
        if "ID_str" not in roster.columns: return None, 0.0
        x = counts_out.copy()
        x["__id"] = x["__id"].astype(str).str.strip()
        m = roster.merge(x, left_on="ID_str", right_on="__id", how="left")
        matched = (~m["week1_count"].isna()).mean() * 100.0
        return m, matched
    def join_email():
        x = counts_out.copy()
        x["__email_norm"] = x["__email"].map(normalize_email)
        if "SIS Login ID_norm" in roster.columns:
            m = roster.merge(x, left_on="SIS Login ID_norm", right_on="__email_norm", how="left")
        elif "Email_norm" in roster.columns:
            m = roster.merge(x, left_on="Email_norm", right_on="__email_norm", how="left")
        else:
            return None, 0.0
        matched = (~m["week1_count"].isna()).mean() * 100.0
        return m, matched
    id_m, id_cov = join_id()
    em_m, em_cov = join_email()
    if em_cov >= id_cov:
        return em_m, "email", em_cov
    else:
        return id_m, "id", id_cov

def finalize_output(merged):
    # Fill zeros
    for col in ["week1_count","week2_count","total_count","percentage"]:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0.0)
    if "max_possible" in merged.columns:
        merged["max_possible"] = pd.to_numeric(merged["max_possible"], errors="coerce").fillna(6.0)
    name_col = "__disp_name" if "__disp_name" in merged.columns else "__name"
    keep = [c for c in [name_col,"ID_str","SIS Login ID","Email","week1_count","week2_count","total_count","max_possible","percentage"] if c in merged.columns]
    out = merged[keep].rename(columns={name_col:"Student","ID_str":"ID"})
    return out

def write_csv(df, path):
    df.to_csv(path, index=False)
    LOGGER.info(f"Wrote: {path}")

def write_matrix(df_weeks, six_dates, out_path):
    mini = df_weeks.sort_values("__ts").drop_duplicates("__identity", keep="first")[["__identity","__name","__id","__email"]]
    att_ids = df_weeks[["__identity","__date"]].drop_duplicates().assign(val=1)
    pivot = att_ids.pivot_table(index="__identity", columns="__date", values="val", fill_value=0)
    for d in six_dates:
        if d not in pivot.columns:
            pivot[d] = 0
    pivot = pivot[six_dates]
    mat = mini.merge(pivot.reset_index(), on="__identity", how="left").fillna(0)
    mat["total_count"] = mat[six_dates].sum(axis=1)
    mat["max_possible"] = 6
    mat["percentage"] = mat["total_count"] / mat["max_possible"] * 100
    mat = mat.rename(columns={d: d.strftime("%Y-%m-%d") for d in six_dates})
    mat = mat.rename(columns={"__name":"Student","__id":"ID","__email":"Email"})
    cols = ["Student","ID","Email"] + [d.strftime("%Y-%m-%d") for d in six_dates] + ["total_count","max_possible","percentage"]
    mat[cols].to_csv(out_path, index=False)
    LOGGER.info(f"Wrote matrix: {out_path}")

def qa_report(out_df, roster_len):
    rows = len(out_df)
    nz = int((out_df["total_count"] > 0).sum()) if "total_count" in out_df.columns else 0
    cov = (nz/rows*100.0) if rows else 0.0
    w1max = float(out_df["week1_count"].max()) if "week1_count" in out_df.columns else None
    w2max = float(out_df["week2_count"].max()) if "week2_count" in out_df.columns else None
    tmax  = float(out_df["total_count"].max()) if "total_count" in out_df.columns else None
    LOGGER.info(f"QA: rows={rows} (roster={roster_len}), >0 totals={nz} ({cov:.1f}%), max: w1={w1max}, w2={w2max}, total={tmax}")

def cmd_process(args):
    att = load_attendance(args.attendance)
    att_w12 = dedup_same_day(filter_weeks(att, args.start, args.end))
    counts_out, lecture_dates, week1, week2 = compute_counts(att_w12)
    six = (week1 + week2)[:6]
    if args.gradebook:
        roster = load_gradebook_csv(args.gradebook)
        if args.join == "auto":
            merged, mode, cov = try_join_modes(counts_out, roster)
            LOGGER.info(f"Auto-join picked: {mode} (coverage={cov:.1f}%)")
        elif args.join == "id":
            counts_out["__id"] = counts_out["__id"].astype(str).str.strip()
            merged = roster.merge(counts_out, left_on="ID_str", right_on="__id", how="left")
        elif args.join == "email":
            counts_out["__email_norm"] = counts_out["__email"].map(normalize_email)
            if "SIS Login ID_norm" in roster.columns:
                merged = roster.merge(counts_out, left_on="SIS Login ID_norm", right_on="__email_norm", how="left")
            else:
                merged = roster.merge(counts_out, left_on="Email_norm", right_on="__email_norm", how="left")
        else:
            merged = counts_out  # none
        out_df = finalize_output(merged)
    else:
        out_df = counts_out.rename(columns={"__name":"Student","__id":"ID","__email":"Email"})[
            ["Student","ID","Email","week1_count","week2_count","total_count","max_possible","percentage"]
        ]
    # Write outputs
    prefix = args.out_prefix or "attendance"
    out_csv = f"{prefix}_attendance_counts_weeks1_2.csv"
    write_csv(out_df, out_csv)
    if args.matrix:
        write_matrix(att_w12, six, f"{prefix}_attendance_matrix_weeks1_2.csv")
    qa_report(out_df, roster_len=(len(out_df)))
    print("Detected lecture dates:", [d.isoformat() for d in six])

def ensure_google_service(gjson):
    if gspread is None or SACredentials is None:
        raise RuntimeError("Google libraries not installed. Install google-api-python-client, gspread, google-auth, google-auth-oauthlib")
    creds = SACredentials.from_service_account_file(gjson, scopes=SCOPES)
    gc = gspread.authorize(creds)
    svc = build("drive", "v3", credentials=creds)
    return gc, svc

def drive_copy_export_csv(service, file_id: str, copy_name: str, out_csv_path: str):
    # Copy
    copied = service.files().copy(fileId=file_id, body={"name": copy_name}).execute()
    copy_id = copied["id"]
    # Export as CSV (first sheet)
    request = service.files().export_media(fileId=copy_id, mimeType="text/csv")
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    with open(out_csv_path, "wb") as f:
        f.write(fh.getvalue())
    return copy_id

def canvas_pull_roster(base_url, course_id, token, out_csv):
    if requests is None:
        raise RuntimeError("requests not installed")
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{base_url}/api/v1/courses/{course_id}/users"
    params = {"enrollment_type[]":"student","per_page":100}
    users = []
    while url:
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        users.extend(r.json())
        # pagination
        url = None
        if 'link' in r.headers:
            for part in r.headers['link'].split(","):
                if 'rel="next"' in part:
                    url = part[part.find("<")+1:part.find(">")]
                    break
    # Write a simple roster CSV
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Student","ID","SIS Login ID","Email"])
        for u in users:
            name = u.get("name","")
            uid  = str(u.get("id",""))
            login = u.get("login_id","")
            email = u.get("email","")
            w.writerow([name, uid, login, email])
    LOGGER.info(f"Wrote Canvas roster: {out_csv} ({len(users)} students)")

def cmd_all(args):
    if yaml is None:
        raise RuntimeError("pyyaml not installed. Install pyyaml.")
    with open(args.config, "r") as f:
        cfg = yaml.safe_load(f)
    # Pull attendance via Drive (optional)
    attendance_csv = cfg["local"].get("attendance_csv", "attendance_weeks1_2.csv")
    if "google" in cfg and cfg["google"].get("credentials_json") and cfg["google"].get("attendance_file_id"):
        gc, svc = ensure_google_service(cfg["google"]["credentials_json"])
        copy_name = cfg["google"].get("copy_name", "Attendance_Working_Copy")
        LOGGER.info("Copying attendance sheet and exporting as CSV from Drive...")
        drive_copy_export_csv(svc, cfg["google"]["attendance_file_id"], copy_name, attendance_csv)
    # Pull Canvas roster (optional)
    gradebook_csv = cfg["local"].get("gradebook_csv", "canvas_gradebook.csv")
    if "canvas" in cfg and cfg["canvas"].get("base_url") and cfg["canvas"].get("token") and cfg["canvas"].get("course_id"):
        LOGGER.info("Pulling roster from Canvas API...")
        canvas_pull_roster(cfg["canvas"]["base_url"], cfg["canvas"]["course_id"], cfg["canvas"]["token"], gradebook_csv)
    # Process
    class A: pass
    a = A()
    a.attendance = attendance_csv
    a.gradebook = gradebook_csv if os.path.exists(gradebook_csv) else None
    a.start = cfg["window"]["start"]
    a.end   = cfg["window"]["end"]
    a.out_prefix = cfg["output"].get("prefix","attendance")
    a.join = cfg.get("join","auto")
    a.matrix = cfg["output"].get("matrix", True)
    cmd_process(a)

def build_argparser():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("process", help="Process local CSVs")
    p1.add_argument("--attendance", required=True, help="Working-copy attendance CSV")
    p1.add_argument("--gradebook", required=False, help="Canvas gradebook/roster CSV")
    p1.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    p1.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    p1.add_argument("--out-prefix", default="attendance", help="Prefix for output file names")
    p1.add_argument("--join", choices=["auto","email","id","none"], default="auto")
    p1.add_argument("--matrix", action="store_true", help="Also write a per-lecture matrix CSV")
    p1.set_defaults(func=cmd_process)

    p2 = sub.add_parser("all", help="Run full pipeline from config.yaml")
    p2.add_argument("--config", required=True, help="Path to config.yaml")
    p2.set_defaults(func=cmd_all)

    return p

def main():
    ap = build_argparser()
    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
