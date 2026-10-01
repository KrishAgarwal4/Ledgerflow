from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.billing import Subscription, SubscriptionStatus, Invoice, InvoiceStatus
from backend.app.models.customer import Customer, PaymentMethodStatus
from backend.app.core.billing_engine import BillingEngine
from backend.app.models.ledger import PostingDirection
from backend.app.core.ledger_engine import LedgerEngine

# Stripe-standard dunning backoff intervals
DUNNING_SCHEDULE_DAYS = [1, 3, 7] # 1st retry in +1 day, 2nd in +3 days, 3rd in +7 days

class DunningEngine:
    @staticmethod
    async def process_failed_payment(
        session: AsyncSession,
        subscription: Subscription,
        invoice: Invoice,
        virtual_now: datetime
    ) -> Dict[str, Any]:
        """
        Transitions subscription into PAST_DUE and schedules first dunning retry.
        """
        subscription.status = SubscriptionStatus.PAST_DUE
        subscription.dunning_attempt_count = 0
        subscription.next_retry_at = virtual_now + timedelta(days=DUNNING_SCHEDULE_DAYS[0])
        return {
            "action": "DUNNING_SCHEDULED",
            "attempt": 1,
            "next_retry_at": subscription.next_retry_at.isoformat(),
            "status": subscription.status.value,
        }

    @staticmethod
    async def execute_dunning_retry(
        session: AsyncSession,
        subscription_id: str,
        virtual_now: datetime
    ) -> Dict[str, Any]:
        """
        Executes a scheduled dunning payment retry.
        If customer's payment method is still failing:
        - Advances attempt count
        - Either schedules next retry or cancels subscription after final attempt.
        If payment succeeds:
        - Restores subscription to ACTIVE.
        """
        sub_stmt = select(Subscription).where(Subscription.id == subscription_id).with_for_update()
        subscription = (await session.execute(sub_stmt)).scalar_one_or_none()
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found.")

        cust_stmt = select(Customer).where(Customer.id == subscription.customer_id)
        customer = (await session.execute(cust_stmt)).scalar_one()

        inv_stmt = (
            select(Invoice)
            .where(Invoice.subscription_id == subscription.id)
            .where(Invoice.status == InvoiceStatus.OPEN)
            .order_by(Invoice.created_at.desc())
        )
        invoice = (await session.execute(inv_stmt)).scalars().first()
        if not invoice:
            return {"action": "NO_OPEN_INVOICE", "subscription_status": subscription.status.value}

        payment_result = await BillingEngine.attempt_invoice_payment(
            session=session,
            invoice=invoice,
            customer=customer,
            virtual_now=virtual_now
        )

        current_attempt = subscription.dunning_attempt_count + 1

        if payment_result in ("PAYMENT_SUCCEEDED", "PAID_ZERO_BALANCE"):
            # Payment recovered!
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.dunning_attempt_count = 0
            subscription.next_retry_at = None
            return {
                "action": "PAYMENT_RECOVERED",
                "attempt": current_attempt,
                "invoice_id": invoice.id,
                "subscription_status": subscription.status.value,
            }

        # Payment failed again
        subscription.dunning_attempt_count = current_attempt

        if current_attempt < len(DUNNING_SCHEDULE_DAYS):
            next_delay_days = DUNNING_SCHEDULE_DAYS[current_attempt]
            subscription.next_retry_at = virtual_now + timedelta(days=next_delay_days)
            return {
                "action": "DUNNING_RETRY_FAILED",
                "attempt": current_attempt,
                "max_attempts": len(DUNNING_SCHEDULE_DAYS),
                "next_retry_at": subscription.next_retry_at.isoformat(),
                "subscription_status": subscription.status.value,
            }
        else:
            # Exceeded maximum dunning retries -> Cancel subscription, mark invoice uncollectible
            subscription.status = SubscriptionStatus.CANCELED
            subscription.next_retry_at = None
            invoice.status = InvoiceStatus.UNCOLLECTIBLE

            # Record write-off in ledger for bad debt / uncollectible AR:
            # DEBIT: Expense (Bad Debt)
            # CREDIT: Customer Receivable
            BAD_DEBT_ACCOUNT_ID = "acc_bad_debt_expense"
            if invoice.amount_remaining_cents > 0:
                await LedgerEngine.create_journal_entry(
                    session=session,
                    description=f"Write-off uncollectible AR for Invoice {invoice.id} (Subscription Canceled)",
                    effective_at=virtual_now,
                    postings=[
                        {
                            "account_id": BAD_DEBT_ACCOUNT_ID,
                            "direction": PostingDirection.DEBIT,
                            "amount_cents": invoice.amount_remaining_cents,
                        },
                        {
                            "account_id": customer.receivable_account_id,
                            "direction": PostingDirection.CREDIT,
                            "amount_cents": invoice.amount_remaining_cents,
                        },
                    ],
                    metadata_json={
                        "invoice_id": invoice.id,
                        "subscription_id": subscription.id,
                        "write_off_reason": "MAX_DUNNING_RETRIES_EXCEEDED",
                    },
                )

            return {
                "action": "SUBSCRIPTION_CANCELED_FINAL",
                "attempt": current_attempt,
                "invoice_status": invoice.status.value,
                "subscription_status": subscription.status.value,
            }
