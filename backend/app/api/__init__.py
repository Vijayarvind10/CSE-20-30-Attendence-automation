from fastapi import APIRouter

from app.api.v1 import routes as v1_routes

api_router = APIRouter()
api_router.include_router(v1_routes.router, prefix="/v1")
