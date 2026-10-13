"""Health check route -- distinguishes "the API is up" from "models are
loaded and ready to serve inference"."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.mongodb import ping
from app.inference.final_demo_inference import get_pipeline

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check() -> dict:
    pipeline = get_pipeline()
    # ping() never raises -- it catches every PyMongoError internally and
    # returns False, so a Mongo outage reports "disconnected" here rather
    # than crashing this endpoint. See app/core/mongodb.py.
    try:
        mongodb_status = "connected" if ping() else "disconnected"
    except Exception:
        mongodb_status = "disconnected"
    return {
        "status": "ok",
        "inference_ready": pipeline.is_loaded,
        "mongodb": mongodb_status,
    }
