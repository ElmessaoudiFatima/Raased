from fastapi import APIRouter

from app.api.v1 import agent, health, auth, admin, manager

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(agent.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(manager.router)