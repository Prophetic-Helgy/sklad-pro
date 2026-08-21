"""HTTP-API «Склад ПРО»."""
from fastapi import APIRouter

from . import admin, auth, company, documents, migrate, references, registry, reports, stock

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(references.router)
api_router.include_router(documents.router)
api_router.include_router(stock.router)
api_router.include_router(registry.router)
api_router.include_router(reports.router)
api_router.include_router(company.router)
api_router.include_router(admin.router)
api_router.include_router(migrate.router)
