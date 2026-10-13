"""FastAPI application entrypoint: lifespan (model loading), routers, CORS,
and a global exception handler. No business logic lives here."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import analysis, audit, dispatch, health, incidents, notifications, responders, share, yolo
from app.core.config import get_settings
from app.core.mongodb import close_mongo_client, ensure_indexes, get_database
from app.inference.final_demo_inference import get_pipeline
from app.inference.yolo26_service import get_yolo_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading inference pipeline (I3D + Stage 1 + Stage 2 checkpoints)...")
    t0 = time.time()
    get_pipeline().load()
    logger.info("Inference pipeline loaded in %.2f sec", time.time() - t0)

    # YOLO26 is an additive supporting vision layer. A failure to load it
    # must never prevent the authoritative anomaly pipeline above from
    # serving -- isolated in its own try/except, with is_ready() reporting
    # the real state afterwards rather than crashing startup.
    logger.info("Loading YOLO26 supporting vision layer...")
    t1 = time.time()
    try:
        get_yolo_service().initialize()
        logger.info("YOLO26 service loaded in %.2f sec", time.time() - t1)
    except Exception:
        logger.exception("YOLO26 service failed to load; /api/v1/yolo endpoints will report not-ready.")

    # MongoDB: constructing the client never raises/blocks even if Atlas is
    # unreachable (see app/core/mongodb.py), so this never prevents startup.
    # Index creation is idempotent and non-fatal on failure -- a temporarily
    # unreachable database must not block the app from serving traffic;
    # persistent-data operations will report a truthful error instead.
    try:
        ensure_indexes(get_database())
        logger.info("MongoDB indexes ensured.")
    except Exception:
        logger.exception("Could not ensure MongoDB indexes; database may be unreachable. Continuing startup.")

    yield
    logger.info("Shutting down.")
    close_mongo_client()


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Two-stage video anomaly detection API: I3D feature extraction, a "
        "binary anomaly detector, and a 13-class action classifier run only "
        "when an anomaly is detected."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred."},
    )


app.include_router(health.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(yolo.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(responders.router, prefix="/api")
app.include_router(dispatch.router, prefix="/api")
app.include_router(incidents.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(share.router, prefix="/api")
