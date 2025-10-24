# Attendance Automator Web

Production-grade scaffold for the UCSC Attendance Automator Web Platform. It exposes the existing `attendance_automator.py` processing logic through a FastAPI service and a React + Tailwind web client ready for deployment.

## Project layout

```
.
├── backend
│   ├── app
│   │   ├── api/            # FastAPI routers and dependencies
│   │   ├── core/           # Settings & shared config
│   │   ├── services/       # Attendance processing service
│   │   └── attendance_automator.py  # Original processing engine
│   ├── requirements.txt    # Backend dependencies
│   └── .env.example        # Sample environment variables
├── frontend                # React + Vite + Tailwind UI
│   ├── src/api             # REST client helpers
│   ├── src/types.ts        # Shared response types
│   └── .env.example        # Point the SPA to the API base URL
└── storage                 # Local uploads + generated CSV artifacts
```

## Backend (FastAPI)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # optional overrides
uvicorn app.main:app --reload --port 8000
```

### Render deployment (one-click)

1. Click **New → Blueprint** inside Render and point it at this repository, or run `render services create --from render.yaml`.
2. The included `render.yaml` + `backend/Dockerfile` build the FastAPI service and expose it on port `10000`.
3. In the Render dashboard add these environment variables (or edit `render.yaml` before connecting it):
   - `ALLOWED_ORIGINS=["http://localhost:5173","https://vijayarvind10.github.io"]`
   - `VITE_API_BASE` (the same URL you will give the frontend, e.g. `https://attendance-automator.onrender.com/api/v1`).
4. Deploy the service; note the public URL — you will plug it into the frontend build so the hosted UI can reach the API.

Key endpoints (prefixed by `/api/v1`):

| Method | Endpoint               | Purpose                              |
| ------ | ---------------------- | ------------------------------------ |
| GET    | `/health`              | Readiness check                      |
| POST   | `/attendance/process`  | Upload files + run automator logic   |
| GET    | `/history`             | Stubbed audit trail (ready to wire)  |

File uploads are persisted under `storage/uploads/` and processed CSVs are written to `storage/outputs/`. Paths are returned to the UI via the API response for future download wiring.

## Frontend (React + Tailwind)

```bash
cd frontend
cp .env.example .env.local  # set VITE_API_BASE if needed
npm install
npm run dev
```

Notable UI sections:

- Guided upload + configuration form for the two CSVs, date window, join mode, and matrix toggle.
- Rich preview card highlighting coverage stats and sample rows returned by the API.
- Audit history sidebar fed by `/api/v1/history`.

Production build: `npm run build` (already validated in this branch).

### GitHub Pages build variables

The Pages workflow (`.github/workflows/deploy.yml`) reads `VITE_API_BASE` from the repository **Variables**. Set it under **Settings → Secrets and variables → Actions → Variables** so that every Pages deployment targets your hosted API instead of `http://localhost:8000/api/v1`.

## Storage & security

- Secrets live in `.env` (not committed). Canvas/Google credentials should ultimately be stored in the database or a vault; this scaffold leaves those hooks open.
- Uploaded files are written to `storage/uploads` and can be cleaned after a successful run via a future background task.

## Next steps

1. Wire Google OAuth + persisted sessions so instructors sign in with their UCSC accounts.
2. Implement real Canvas + Google Sheets integrations in dedicated service modules.
3. Replace the stub `/history` response with records stored in SQLite/PostgreSQL.
4. Add download endpoints (e.g., `/artifacts/{id}`) so the frontend can offer direct CSV downloads.
