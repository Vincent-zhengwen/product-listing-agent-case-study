from __future__ import annotations

import os
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent
EVAL_ROOT = BACKEND_ROOT.parent
PROJECT_ROOT = EVAL_ROOT
FIXTURES_ROOT = EVAL_ROOT / "fixtures"
DEMO_IMAGES_ROOT = FIXTURES_ROOT / "images"

AGENT_DB = Path(
    os.getenv("EVAL_CENTER_AGENT_DB_PATH", str(FIXTURES_ROOT / "agent_demo.sqlite"))
).expanduser()


def load_agent_env(*, override: bool = False) -> bool:
    """No-op in the public portfolio package.

    The private project loaded local Agent credentials here. The portfolio
    version keeps configuration explicit and does not read private env files.
    """
    return False


def resolve_agent_image_path_from_url(url: str) -> Path | None:
    """Map demo image URLs back to fixture images when present."""
    if not url or "/images/" not in url:
        return None
    fname = url.rsplit("/images/", 1)[-1].split("?", 1)[0]
    candidate = DEMO_IMAGES_ROOT / fname
    if candidate.exists():
        return candidate
    return None
