from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import datasets, mock_agent, reports, task_runs, test_cases


app = FastAPI(title="Trend Seller Eval Platform", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health():
    return {"ok": True}


app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
app.include_router(test_cases.router, prefix="/api/datasets", tags=["test_cases"])
app.include_router(task_runs.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(mock_agent.router, prefix="/api/mock", tags=["mock_agent"])
