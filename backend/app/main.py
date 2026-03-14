from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models.database import init_db, close_db
from app.api.upload import router as upload_router
from app.api.analysis import router as analysis_router
from app.api.conversation import router as conversation_router
from app.api.ws import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="Virtual User Lab",
    description="PRD 自动化压力测试平台 v2.0",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(upload_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(conversation_router, prefix="/api/v1")
app.include_router(ws_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "virtual-user-lab", "version": "2.0.0"}
