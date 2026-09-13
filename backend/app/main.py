from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.agent.worker import agent_loop
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    if settings.AGENT_LOOP_ENABLED:
        logger.info("AGENT_LOOP_ENABLED=True — démarrage du worker agent en tâche de fond.")
        task = asyncio.create_task(agent_loop())
    else:
        logger.info("AGENT_LOOP_ENABLED=False — worker agent désactivé.")
    yield
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://app.raased.ma",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)
if settings.API_V1_PREFIX != "/api":
    app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    return {"status": "ok"}