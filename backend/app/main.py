from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.database import init_db
from backend.app.seed.seed_data import seed_database
from backend.app.api.v1.router import api_v1_router
from backend.app.core.ledger_engine import ZeroSumViolationError, InsufficientFundsError, AccountNotFoundError
from backend.app.core.idempotency import IdempotencyConflictError, IdempotencyPayloadMismatchError
from backend.app.core.clock_engine import ClockAdvancementError

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database and seed baseline data
    await init_db()
    await seed_database()
    yield
    # Shutdown

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Stripe-grade immutable double-entry ledger, usage billing engine, and virtual test clock simulator.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Idempotent-Replayed", "Idempotency-Key"],
)

# Exception handlers
@app.exception_handler(ZeroSumViolationError)
async def zero_sum_exception_handler(request: Request, exc: ZeroSumViolationError):
    return JSONResponse(
        status_code=400,
        content={"error": "ZeroSumViolation", "message": str(exc), "type": "financial_invariant_violation"}
    )

@app.exception_handler(InsufficientFundsError)
async def insufficient_funds_exception_handler(request: Request, exc: InsufficientFundsError):
    return JSONResponse(
        status_code=422,
        content={"error": "InsufficientFunds", "message": str(exc), "account_id": exc.account_id}
    )

@app.exception_handler(IdempotencyConflictError)
async def idempotency_conflict_handler(request: Request, exc: IdempotencyConflictError):
    return JSONResponse(
        status_code=409,
        content={"error": "IdempotencyConflict", "message": str(exc)}
    )

@app.exception_handler(IdempotencyPayloadMismatchError)
async def idempotency_mismatch_handler(request: Request, exc: IdempotencyPayloadMismatchError):
    return JSONResponse(
        status_code=422,
        content={"error": "IdempotencyPayloadMismatch", "message": str(exc)}
    )

@app.exception_handler(ClockAdvancementError)
async def clock_error_handler(request: Request, exc: ClockAdvancementError):
    return JSONResponse(
        status_code=400,
        content={"error": "ClockAdvancementError", "message": str(exc)}
    )

# Routers
app.include_router(api_v1_router, prefix=settings.API_V1_STR)

@app.get("/healthz", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "service": "chronos-billing-engine",
        "version": settings.VERSION,
    }

@app.get("/", tags=["System"])
async def root():
    return {
        "project": "Chronos Ledger & Billing Engine",
        "docs": "/docs",
        "version": settings.VERSION,
        "author": "Staff Systems Engineer Specification",
    }
