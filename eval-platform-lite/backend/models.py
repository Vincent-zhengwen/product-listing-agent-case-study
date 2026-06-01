from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


# ── Dataset ──────────────────────────────────────────────
class DatasetCreate(BaseModel):
    name: str
    description: str = ""
    version: str = "v1.0"


class DatasetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    status: Optional[str] = None


# ── TestCase ──────────────────────────────────────────────
class TestCaseCreate(BaseModel):
    source_url: str
    category: str = ""
    difficulty: str = "medium"
    source_quality: str = "medium"
    taobao_ref_url: str = ""
    douyin_ref_url: str = ""
    xiaohongshu_ref_url: str = ""
    tags: List[str] = []
    notes: str = ""


class TestCaseUpdate(BaseModel):
    source_url: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    source_quality: Optional[str] = None
    taobao_ref_url: Optional[str] = None
    douyin_ref_url: Optional[str] = None
    xiaohongshu_ref_url: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


# ── TaskRun ──────────────────────────────────────────────
class TaskRunCreate(BaseModel):
    name: str
    dataset_id: str
    platform: str = "all"          # taobao | douyin | xiaohongshu | all
    agent_version: str = "unknown"
    runs_per_case: int = 1
    filter_category: Optional[str] = None
    filter_difficulty: Optional[str] = None


# ── Agent callback ──────────────────────────────────────
class AgentStepTrace(BaseModel):
    step_id: Any
    name: str
    status: str
    duration_ms: int = 0
    model: Optional[str] = None
    tokens: Optional[int] = None
    input: Optional[Any] = None
    output: Optional[Any] = None
    error: Optional[str] = None


class AgentTrace(BaseModel):
    steps: List[AgentStepTrace] = []
    total_tokens: int = 0
    total_model_calls: int = 0


class AgentOutput(BaseModel):
    title: str = ""
    attributes: dict = {}
    selling_points: List[str] = []
    body_copy: str = ""
    main_images: List[dict] = []
    detail_image: Optional[dict] = None
    detail_images: List[dict] = []
    compliance: dict = {}


class AgentCallback(BaseModel):
    task_id: str
    status: str                    # success | partial | failed
    platform: str
    duration_ms: int = 0
    cost_rmb: float = 0.0
    output: Optional[AgentOutput] = None
    trace: Optional[AgentTrace] = None
    error: Optional[str] = None


# ── Human Annotation ──────────────────────────────────────
class HumanAnnotation(BaseModel):
    q1_publishable: Optional[bool] = None
    q2_competitor_parity: Optional[bool] = None
    q3_would_click: Optional[bool] = None
    biggest_issue: str = ""
