from fastapi import APIRouter
from app.api.routes.ai import router as ai_router
from app.api.routes.health import router as health_router
from app.api.routes.tickets import router as tickets_router
from app.api.routes.faq import router as faq_router
from app.api.routes.workflows import router as workflows_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(ai_router)
api_router.include_router(tickets_router)
api_router.include_router(faq_router)
api_router.include_router(workflows_router)