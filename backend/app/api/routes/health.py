"""Health check route -- distinguishes "the API is up" from "models are
loaded and ready to serve inference"."""

from __future__ import annotations

from fastapi import APIRouter

from app.inference.final_demo_inference import get_pipeline

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check() -> dict:
    pipeline = get_pipeline()
    return {
        "status": "ok",
        "inference_ready": pipeline.is_loaded,
    }
