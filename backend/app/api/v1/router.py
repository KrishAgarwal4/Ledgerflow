from fastapi import APIRouter
from backend.app.api.v1.ledger import router as ledger_router
from backend.app.api.v1.usage import router as usage_router
from backend.app.api.v1.test_clocks import router as test_clocks_router
from backend.app.api.v1.billing import router as billing_router
from backend.app.api.v1.chaos import router as chaos_router

api_v1_router = APIRouter()

api_v1_router.include_router(ledger_router)
api_v1_router.include_router(usage_router)
api_v1_router.include_router(test_clocks_router)
api_v1_router.include_router(billing_router)
api_v1_router.include_router(chaos_router)
