"""
FastAPI application entry point.

Mounts all API routers, configures CORS, adds health check.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api import auth, conversations, files, library, admin, extraction


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="TK-7 Tacit Knowledge Extraction System — Hu-Mirror + Journal-Mirror",
)


# CORS — frontend origin from env (Vercel URL in production)
# We accept comma-separated list of origins to allow preview deployments
origins = [o.strip() for o in settings.FRONTEND_ORIGIN.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["meta"])
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "env": settings.ENV,
        "status": "ok",
    }


@app.get("/health", tags=["meta"])
def health():
    """Liveness probe for Railway. Does not check DB to stay fast."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["meta"])
def readiness():
    """Readiness probe: check DB + Redis connectivity."""
    from app.db.session import engine
    from app.db.redis_client import get_redis
    db_ok, redis_ok = False, False
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1" if False else __import__("sqlalchemy").text("SELECT 1"))
            db_ok = True
    except Exception:
        db_ok = False
    try:
        r = get_redis()
        r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    code = 200 if (db_ok and redis_ok) else 503
    return JSONResponse(
        status_code=code,
        content={"db": db_ok, "redis": redis_ok, "status": "ok" if code == 200 else "degraded"},
    )


# Mount routers
api_prefix = "/api/v1"
app.include_router(auth.router, prefix=api_prefix)
app.include_router(conversations.router, prefix=api_prefix)
app.include_router(files.router, prefix=api_prefix)
app.include_router(library.router, prefix=api_prefix)
app.include_router(extraction.router, prefix=api_prefix)
app.include_router(admin.router, prefix=api_prefix)
