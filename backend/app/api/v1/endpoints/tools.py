"""Admin utilities kept from v1/v2: run an ingestion plugin, score one pair, list plugins."""
from typing import Dict, Any
import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core import config
from app.core.database import get_db
from app.core.deps import require_admin
from app.core.plugin_loader import PluginLoader
from app.models import Consultant, Job
from app.services import matching
from app.services.cv_parser import parse_profile_text
from app.services.uploads import read_upload

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/plugins", summary="Installed ingestion and ranking plugins")
def plugins():
    pl = PluginLoader()
    pl.ensure_loaded()
    return {"ingestion_plugins": list(pl.ingestion_plugins), "ranking_plugins": list(pl.ranking_plugins)}


@router.post("/ingest", summary="Run an ingestion plugin on a file (no database writes)")
async def ingest(file: UploadFile = File(...), plugin_name: str = Form(config.DEFAULT_PDF_PLUGIN)):
    pl = PluginLoader()
    if plugin_name not in pl.ingestion_plugins:
        raise HTTPException(status_code=400, detail=f"Unknown plugin. Available: {list(pl.ingestion_plugins)}")
    data, name, _ = await read_upload(file)
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(name)[1]) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        result = pl.get_ingestion_plugin(plugin_name).extract_text(path)
    finally:
        os.unlink(path)
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])
    return {"filename": name, "plugin_used": plugin_name, "data": result,
            "parsed": parse_profile_text(result.get("text", ""))}


@router.post("/rank", summary="Score one freelancer against one job, with breakdown")
def rank(payload: Dict[str, Any] = Body(..., examples=[{"job_id": 1, "consultant_id": 1}]),
         db: Session = Depends(get_db)):
    job = db.get(Job, payload.get("job_id") or 0)
    c = db.get(Consultant, payload.get("consultant_id") or 0)
    if not job or not c:
        raise HTTPException(status_code=404, detail="Job or freelancer not found")
    plugin = payload.get("plugin_name") or config.DEFAULT_RANKING_PLUGIN
    if plugin not in PluginLoader().ranking_plugins:
        raise HTTPException(status_code=404, detail="Ranking plugin not found")
    details = matching.score_pair(job, c, plugin)
    return {"score": details["score"], "details": details, "threshold": config.MATCH_THRESHOLD}
