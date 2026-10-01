from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database import get_db, Base, engine
from backend.app.models.clock import TestClock, ClockMilestone
from backend.app.schemas.clock import ClockResponse, ClockAdvanceRequest, MilestoneResponse
from backend.app.core.clock_engine import ClockEngine, ClockAdvancementError
from backend.app.seed.seed_data import seed_database

router = APIRouter(prefix="/test-clocks", tags=["Test Clocks"])

@router.get("", response_model=ClockResponse)
async def get_test_clock(session: AsyncSession = Depends(get_db)):
    """Retrieve the primary virtual simulation clock and its recent milestones."""
    clock = await ClockEngine.get_or_create_clock(session, "clock_main")
    
    # Load recent milestones
    ms_query = (
        select(ClockMilestone)
        .where(ClockMilestone.clock_id == clock.id)
        .order_by(ClockMilestone.timestamp.desc(), ClockMilestone.created_at.desc())
        .limit(50)
    )
    clock.milestones = (await session.execute(ms_query)).scalars().all()
    return clock

@router.post("/{clock_id}/advance", response_model=ClockResponse)
async def advance_test_clock(
    clock_id: str,
    payload: ClockAdvanceRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Deterministically advances the virtual clock.
    Sweeps through every chronological milestone (period rollovers, dunning retries, tier adjustments)
    between current_time and target_time.
    """
    clock = await ClockEngine.get_or_create_clock(session, clock_id)
    
    if payload.target_time:
        target_time = payload.target_time
        if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=timezone.utc)
    elif payload.advance_seconds is not None:
        target_time = clock.current_virtual_time + timedelta(seconds=payload.advance_seconds)
    else:
        raise HTTPException(
            status_code=400,
            detail="Either 'target_time' or 'advance_seconds' must be provided."
        )

    try:
        newly_executed = await ClockEngine.advance_clock(
            session=session,
            clock_id=clock_id,
            target_time=target_time
        )
    except ClockAdvancementError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Advancement failed: {str(e)}")

    # Reload clock state and milestones
    ms_query = (
        select(ClockMilestone)
        .where(ClockMilestone.clock_id == clock.id)
        .order_by(ClockMilestone.timestamp.desc(), ClockMilestone.created_at.desc())
        .limit(50)
    )
    clock.milestones = (await session.execute(ms_query)).scalars().all()
    return clock

@router.get("/{clock_id}/milestones", response_model=List[MilestoneResponse])
async def list_milestones(
    clock_id: str,
    limit: int = Query(100, le=500),
    session: AsyncSession = Depends(get_db)
):
    """Audit log of discrete events simulated as TestClock advanced through time."""
    ms_query = (
        select(ClockMilestone)
        .where(ClockMilestone.clock_id == clock_id)
        .order_by(ClockMilestone.timestamp.desc(), ClockMilestone.created_at.desc())
        .limit(limit)
    )
    milestones = (await session.execute(ms_query)).scalars().all()
    return milestones

@router.post("/reset", response_model=ClockResponse)
async def reset_simulation_environment(session: AsyncSession = Depends(get_db)):
    """
    Wipes the database and re-seeds clean initial state.
    Enables users to replay simulations and demos from scratch.
    """
    # Drop all tables and re-create
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Re-seed
    await seed_database()

    # Return refreshed clock
    clock = await ClockEngine.get_or_create_clock(session, "clock_main")
    clock.milestones = []
    return clock
