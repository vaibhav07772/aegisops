"""AegisOps FastAPI application."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response

from app.api.agents import router as agents_router
from app.api.anomaly import router as anomaly_router
from app.api.evaluation import router as evaluation_router
from app.api.incidents import router as incidents_router
from app.api.ingest import router as ingest_router
from app.api.query import router as query_router
from app.api.rag import router as rag_router
from app.api.security import router as security_router
from app.api.simulate import router as simulate_router
from app.config import get_settings
from app.logging_config import configure_logging, get_logger
from app.middleware import RequestContextMiddleware
from app.monitoring import metrics
from app.storage.database import init_db

configure_logging()
logger = get_logger("aegisops")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    
    # Check LangSmith Tracing status (LangChain auto-reads these env vars)
    langsmith_enabled = os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"
    if langsmith_enabled:
        project = os.environ.get("LANGCHAIN_PROJECT", "default")
        logger.info("langsmith_tracing_enabled", project=project)
    else:
        logger.info("langsmith_tracing_disabled")

    logger.info(
        "aegisops_startup",
        version=settings.app_version,
        environment=settings.environment,
    )
    yield
    logger.info("aegisops_shutdown")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI SRE & Incident Response Platform",
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
app.include_router(simulate_router)
app.include_router(ingest_router)
app.include_router(query_router)
app.include_router(anomaly_router)
app.include_router(agents_router)
app.include_router(rag_router)
app.include_router(security_router)
app.include_router(incidents_router)
app.include_router(evaluation_router)


@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <html>
      <head><title>AegisOps</title>
        <style>
          body { font-family: sans-serif; padding: 2rem; max-width: 800px; margin: auto; }
          h1 { color: #1f6feb; }
          code { background: #f6f8fa; padding: 2px 6px; border-radius: 4px; }
          .tag { display: inline-block; background: #ddf4ff; color: #0969da;
                 padding: 2px 8px; border-radius: 12px; font-size: 12px; margin: 2px; }
        </style>
      </head>
      <body>
        <h1>🛡️ AegisOps</h1>
        <p><strong>AI SRE & Incident Response Platform</strong></p>
        <p>An autonomous AI teammate that detects incidents, diagnoses root causes,
           proposes fixes, and learns from every incident — under human supervision.</p>
        <div>
          <span class="tag">FastAPI</span>
          <span class="tag">LangGraph</span>
          <span class="tag">MLflow</span>
          <span class="tag">RAG</span>
          <span class="tag">Guardrails</span>
          <span class="tag">Prometheus</span>
          <span class="tag">LangSmith</span>
        </div>
        <ul>
          <li><a href="/docs">API Docs (Swagger)</a></li>
          <li><a href="/health">Health</a></li>
          <li><a href="/metrics">Prometheus Metrics</a></li>
          <li><a href="/api/v1/simulate/scenarios">Simulate — List Scenarios</a></li>
          <li><a href="/api/v1/simulate/runs">Simulate — List Runs</a></li>
          <li><a href="/api/v1/runs">Ingested Runs</a></li>
          <li><a href="/api/v1/services">Services</a></li>
          <li><a href="/api/v1/logs?limit=20">Recent Logs</a></li>
          <li><a href="/api/v1/traces?limit=20">Recent Traces</a></li>
          <li><a href="/api/v1/anomaly/health">Anomaly Health</a></li>
          <li><a href="/api/v1/agents/health">Agents Health</a></li>
          <li><a href="/api/v1/rag/health">RAG Health</a></li>
          <li><a href="/api/v1/security/health">Security Health</a></li>
          <li><a href="/api/v1/incidents">Incidents</a></li>
          <li><a href="/api/v1/evaluation/health">Evaluation Health</a></li>
        </ul>
      </body>
    </html>
    """


@app.get("/metrics")
async def prometheus_metrics():
    payload, content_type = metrics.render_metrics()
    return Response(content=payload, media_type=content_type)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/health/live")
async def health_live():
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready():
    checks = {
        "data_dir": settings.data_dir.exists(),
        "incidents_dir": settings.incidents_dir.exists(),
        "runbooks_dir": settings.runbooks_dir.exists(),
    }
    return {
        "status": "ready" if all(checks.values()) else "not_ready",
        "checks": checks,
    }