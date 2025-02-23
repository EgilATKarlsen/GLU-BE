from fastapi import APIRouter

from app.route.integrations import router as integrations_router
from app.route.user import router as user_router
from app.route.message import router as message_router

api_router = APIRouter()

api_router.include_router(integrations_router)
api_router.include_router(user_router)
api_router.include_router(message_router)
