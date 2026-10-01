from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database import get_db
from backend.app.models.billing import Plan, Subscription, SubscriptionStatus, Invoice, InvoiceStatus
from backend.app.models.customer import Customer
from backend.app.models.ledger import PostingDirection
from backend.app.schemas.billing import (
    CustomerResponse, PlanResponse, SubscriptionResponse, InvoiceResponse,
    ChangePlanRequest, ProrationPreviewResponse
)
from backend.app.core.ledger_engine import LedgerEngine, generate_id
from backend.app.core.billing_engine import BillingEngine, PLATFORM_REVENUE_ACCOUNT_ID
from backend.app.core.clock_engine import ClockEngine

router = APIRouter(prefix="", tags=["Billing & Customers"])

@router.get("/customers", response_model=List[CustomerResponse])
async def list_customers(session: AsyncSession = Depends(get_db)):
    """List customers with their real-time wallet and accounts receivable balances."""
    cust_stmt = select(Customer).order_by(Customer.name.asc())
    customers = (await session.execute(cust_stmt)).scalars().all()

    results = []
    for c in customers:
        wallet_bal = await LedgerEngine.get_account_balance(session, c.wallet_account_id)
        ar_bal = await LedgerEngine.get_account_balance(session, c.receivable_account_id)

        # Get active subscription
        sub_stmt = (
            select(Subscription)
            .where(Subscription.customer_id == c.id)
            .order_by(Subscription.created_at.desc())
        )
        sub = (await session.execute(sub_stmt)).scalars().first()
        sub_resp = None
        if sub:
            plan = (await session.execute(select(Plan).where(Plan.id == sub.plan_id))).scalar_one_or_none()
            sub_resp = SubscriptionResponse(
                id=sub.id,
                customer_id=sub.customer_id,
                plan_id=sub.plan_id,
                status=sub.status,
                current_period_start=sub.current_period_start,
                current_period_end=sub.current_period_end,
                cancel_at_period_end=sub.cancel_at_period_end,
                dunning_attempt_count=sub.dunning_attempt_count,
                next_retry_at=sub.next_retry_at,
                created_at=sub.created_at,
                plan=PlanResponse.from_orm(plan) if plan else None,
            )

        results.append(
            CustomerResponse(
                id=c.id,
                name=c.name,
                email=c.email,
                currency=c.currency,
                wallet_account_id=c.wallet_account_id,
                receivable_account_id=c.receivable_account_id,
                wallet_balance_cents=wallet_bal,
                receivable_balance_cents=ar_bal,
                payment_method_status=c.payment_method_status,
                active_subscription=sub_resp,
                created_at=c.created_at,
            )
        )
    return results

@router.get("/plans", response_model=List[PlanResponse])
async def list_plans(session: AsyncSession = Depends(get_db)):
    """List available AI SaaS subscription plans."""
    stmt = select(Plan).order_by(Plan.base_fee_cents.asc())
    plans = (await session.execute(stmt)).scalars().all()
    return plans

@router.get("/invoices", response_model=List[InvoiceResponse])
async def list_invoices(
    customer_id: Optional[str] = None,
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_db)
):
    """List invoices with line items and double-entry journal linkage."""
    stmt = select(Invoice).order_by(Invoice.created_at.desc()).limit(limit)
    if customer_id:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    invoices = (await session.execute(stmt)).scalars().all()
    return invoices

@router.post("/subscriptions/{subscription_id}/preview-proration", response_model=ProrationPreviewResponse)
async def preview_proration(
    subscription_id: str,
    payload: ChangePlanRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Simulates mid-cycle tier change down to the exact second.
    Computes unused credit for current plan and prorated charge for new plan.
    """
    sub_stmt = select(Subscription).where(Subscription.id == subscription_id)
    subscription = (await session.execute(sub_stmt)).scalar_one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    old_plan = (await session.execute(select(Plan).where(Plan.id == subscription.plan_id))).scalar_one()
    new_plan = (await session.execute(select(Plan).where(Plan.id == payload.new_plan_id))).scalar_one_or_none()
    if not new_plan:
        raise HTTPException(status_code=404, detail="Target plan not found")

    clock = await ClockEngine.get_or_create_clock(session, "clock_main")
    virtual_now = clock.current_virtual_time

    refund_credit, new_charge, net = BillingEngine.calculate_proration(
        old_plan=old_plan,
        new_plan=new_plan,
        period_start=subscription.current_period_start,
        period_end=subscription.current_period_end,
        change_time=virtual_now
    )

    return ProrationPreviewResponse(
        current_plan_name=old_plan.name,
        new_plan_name=new_plan.name,
        refund_credit_cents=refund_credit,
        new_charge_cents=new_charge,
        net_adjustment_cents=net,
        period_start=subscription.current_period_start,
        period_end=subscription.current_period_end,
        change_time=virtual_now,
    )

@router.post("/subscriptions/{subscription_id}/change-plan", response_model=SubscriptionResponse)
async def change_plan(
    subscription_id: str,
    payload: ChangePlanRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Executes a mid-cycle plan upgrade or downgrade immediately:
    1. Computes exact proration down to the second.
    2. Writes balanced double-entry adjustment to ledger.
    3. Updates subscription to new tier.
    """
    sub_stmt = select(Subscription).where(Subscription.id == subscription_id).with_for_update()
    subscription = (await session.execute(sub_stmt)).scalar_one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    cust = (await session.execute(select(Customer).where(Customer.id == subscription.customer_id))).scalar_one()
    old_plan = (await session.execute(select(Plan).where(Plan.id == subscription.plan_id))).scalar_one()
    new_plan = (await session.execute(select(Plan).where(Plan.id == payload.new_plan_id))).scalar_one_or_none()
    if not new_plan:
        raise HTTPException(status_code=404, detail="Target plan not found")

    clock = await ClockEngine.get_or_create_clock(session, "clock_main")
    virtual_now = clock.current_virtual_time

    refund_credit, new_charge, net_adjustment = BillingEngine.calculate_proration(
        old_plan=old_plan,
        new_plan=new_plan,
        period_start=subscription.current_period_start,
        period_end=subscription.current_period_end,
        change_time=virtual_now
    )

    # Double-entry posting for proration adjustment
    if net_adjustment > 0:
        # Net charge:
        # DEBIT: Customer AR
        # CREDIT: Platform Revenue
        await LedgerEngine.create_journal_entry(
            session=session,
            description=f"Mid-cycle upgrade proration adjustment: {old_plan.name} -> {new_plan.name}",
            effective_at=virtual_now,
            postings=[
                {"account_id": cust.receivable_account_id, "direction": PostingDirection.DEBIT, "amount_cents": net_adjustment},
                {"account_id": PLATFORM_REVENUE_ACCOUNT_ID, "direction": PostingDirection.CREDIT, "amount_cents": net_adjustment},
            ],
            metadata_json={"subscription_id": subscription.id, "type": "PRORATION_CHARGE"}
        )
    elif net_adjustment < 0:
        # Net credit:
        # DEBIT: Platform Revenue (reduces revenue)
        # CREDIT: Customer Wallet (adds prepaid credit)
        credit_amt = abs(net_adjustment)
        await LedgerEngine.create_journal_entry(
            session=session,
            description=f"Mid-cycle downgrade proration credit: {old_plan.name} -> {new_plan.name}",
            effective_at=virtual_now,
            postings=[
                {"account_id": PLATFORM_REVENUE_ACCOUNT_ID, "direction": PostingDirection.DEBIT, "amount_cents": credit_amt},
                {"account_id": cust.wallet_account_id, "direction": PostingDirection.CREDIT, "amount_cents": credit_amt},
            ],
            metadata_json={"subscription_id": subscription.id, "type": "PRORATION_REFUND_CREDIT"}
        )

    subscription.plan_id = new_plan.id
    await session.commit()
    await session.refresh(subscription)

    return SubscriptionResponse(
        id=subscription.id,
        customer_id=subscription.customer_id,
        plan_id=subscription.plan_id,
        status=subscription.status,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        dunning_attempt_count=subscription.dunning_attempt_count,
        next_retry_at=subscription.next_retry_at,
        created_at=subscription.created_at,
        plan=PlanResponse.from_orm(new_plan),
    )
