from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.billing import (
    Plan, Subscription, SubscriptionStatus, Invoice, InvoiceStatus, InvoiceLineItem
)
from backend.app.models.customer import Customer, PaymentMethodStatus
from backend.app.models.usage import UsageEvent
from backend.app.models.ledger import Account, PostingDirection
from backend.app.core.ledger_engine import LedgerEngine, generate_id

PLATFORM_REVENUE_ACCOUNT_ID = "acc_platform_revenue"
PLATFORM_CASH_ACCOUNT_ID = "acc_platform_cash"

class BillingEngine:
    @staticmethod
    def calculate_proration(
        old_plan: Plan,
        new_plan: Plan,
        period_start: datetime,
        period_end: datetime,
        change_time: datetime
    ) -> Tuple[int, int, int]:
        """
        Calculates exact down-to-the-second proration for mid-cycle plan changes.
        Returns:
            (refund_credit_cents, new_charge_cents, net_adjustment_cents)
        """
        total_seconds = max(1, int((period_end - period_start).total_seconds()))
        remaining_seconds = max(0, min(total_seconds, int((period_end - change_time).total_seconds())))

        # Unused credit on old plan: floor(base_fee * remaining / total)
        refund_credit_cents = (old_plan.base_fee_cents * remaining_seconds) // total_seconds
        # Prorated charge on new plan: floor(base_fee * remaining / total)
        new_charge_cents = (new_plan.base_fee_cents * remaining_seconds) // total_seconds
        
        net_cents = new_charge_cents - refund_credit_cents
        return refund_credit_cents, new_charge_cents, net_cents

    @staticmethod
    async def finalize_billing_cycle(
        session: AsyncSession,
        subscription_id: str,
        virtual_now: datetime
    ) -> Tuple[Invoice, Optional[str]]:
        """
        Closes current billing cycle:
        1. Aggregates unbilled usage events up to current_period_end.
        2. Calculates base fee + usage overages.
        3. Creates finalized Invoice with detailed line items.
        4. Generates Double-Entry Journal Entry:
           - DEBIT: Customer Receivable
           - CREDIT: Platform Revenue
        5. Attempts immediate payment execution against payment method / wallet.
        """
        sub_stmt = (
            select(Subscription)
            .where(Subscription.id == subscription_id)
            .with_for_update()
        )
        subscription = (await session.execute(sub_stmt)).scalar_one_or_none()
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found.")

        cust_stmt = select(Customer).where(Customer.id == subscription.customer_id)
        customer = (await session.execute(cust_stmt)).scalar_one()

        plan_stmt = select(Plan).where(Plan.id == subscription.plan_id)
        plan = (await session.execute(plan_stmt)).scalar_one()

        # 1. Aggregate unbilled usage events
        usage_stmt = (
            select(
                UsageEvent.metric_name,
                func.coalesce(func.sum(UsageEvent.quantity), 0).label("total_quantity")
            )
            .where(UsageEvent.customer_id == customer.id)
            .where(UsageEvent.subscription_id == subscription.id)
            .where(UsageEvent.invoice_id.is_(None))
            .where(UsageEvent.timestamp <= subscription.current_period_end)
            .group_by(UsageEvent.metric_name)
        )
        usage_aggregates = (await session.execute(usage_stmt)).all()

        invoice_id = generate_id("in")
        line_items: List[InvoiceLineItem] = []
        total_subtotal_cents = 0

        # Line Item: Base Plan Subscription Fee
        if plan.base_fee_cents > 0:
            base_item = InvoiceLineItem(
                id=generate_id("ili"),
                invoice_id=invoice_id,
                description=f"{plan.name} Monthly Subscription Base Fee",
                quantity=1,
                unit_amount_cents=plan.base_fee_cents,
                amount_cents=plan.base_fee_cents,
                proration=False,
                period_start=subscription.current_period_start,
                period_end=subscription.current_period_end,
            )
            line_items.append(base_item)
            total_subtotal_cents += plan.base_fee_cents

        # Line Items: Metered Usage & Overage
        for metric_name, quantity in usage_aggregates:
            quantity = int(quantity)
            included = plan.included_tokens
            overage_qty = max(0, quantity - included)

            # Included tier line item ($0)
            line_items.append(
                InvoiceLineItem(
                    id=generate_id("ili"),
                    invoice_id=invoice_id,
                    description=f"{metric_name} usage (included allowance: {min(quantity, included):,} / {included:,})",
                    quantity=min(quantity, included),
                    unit_amount_cents=0,
                    amount_cents=0,
                    proration=False,
                    period_start=subscription.current_period_start,
                    period_end=subscription.current_period_end,
                )
            )

            # Overage line item
            if overage_qty > 0:
                # overage_rate_cents_per_million
                overage_cost_cents = (overage_qty * plan.overage_rate_cents_per_million) // 1_000_000
                if overage_cost_cents > 0:
                    line_items.append(
                        InvoiceLineItem(
                            id=generate_id("ili"),
                            invoice_id=invoice_id,
                            description=f"{metric_name} overage ({overage_qty:,} units @ ${plan.overage_rate_cents_per_million / 100:.2f}/M)",
                            quantity=overage_qty,
                            unit_amount_cents=plan.overage_rate_cents_per_million,
                            amount_cents=overage_cost_cents,
                            proration=False,
                            period_start=subscription.current_period_start,
                            period_end=subscription.current_period_end,
                        )
                    )
                    total_subtotal_cents += overage_cost_cents

        # Create Invoice
        invoice = Invoice(
            id=invoice_id,
            customer_id=customer.id,
            subscription_id=subscription.id,
            status=InvoiceStatus.OPEN,
            subtotal_cents=total_subtotal_cents,
            tax_cents=0,
            total_cents=total_subtotal_cents,
            amount_paid_cents=0,
            amount_remaining_cents=total_subtotal_cents,
            due_date=subscription.current_period_end + timedelta(days=7),
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
        )
        invoice.line_items = line_items
        session.add(invoice)
        await session.flush()

        # Link billed usage events to this invoice
        link_usage_stmt = (
            UsageEvent.__table__.update()
            .where(UsageEvent.customer_id == customer.id)
            .where(UsageEvent.subscription_id == subscription.id)
            .where(UsageEvent.invoice_id.is_(None))
            .where(UsageEvent.timestamp <= subscription.current_period_end)
            .values(invoice_id=invoice_id)
        )
        await session.execute(link_usage_stmt)

        # 4. Double-Entry Posting for Invoice Finalization (Revenue Recognition)
        # DEBIT: Customer Accounts Receivable
        # CREDIT: Platform Revenue
        journal_entry = None
        if total_subtotal_cents > 0:
            journal_entry = await LedgerEngine.create_journal_entry(
                session=session,
                description=f"Invoice finalized for {customer.name} ({invoice.id})",
                effective_at=virtual_now,
                postings=[
                    {
                        "account_id": customer.receivable_account_id,
                        "direction": PostingDirection.DEBIT,
                        "amount_cents": total_subtotal_cents,
                    },
                    {
                        "account_id": PLATFORM_REVENUE_ACCOUNT_ID,
                        "direction": PostingDirection.CREDIT,
                        "amount_cents": total_subtotal_cents,
                    },
                ],
                metadata_json={
                    "invoice_id": invoice.id,
                    "customer_id": customer.id,
                    "subscription_id": subscription.id,
                },
            )
            invoice.journal_entry_id = journal_entry.id

        # 5. Attempt Payment Settlement
        payment_result_note = await BillingEngine.attempt_invoice_payment(
            session=session,
            invoice=invoice,
            customer=customer,
            virtual_now=virtual_now
        )

        return invoice, payment_result_note

    @staticmethod
    async def attempt_invoice_payment(
        session: AsyncSession,
        invoice: Invoice,
        customer: Customer,
        virtual_now: datetime
    ) -> str:
        """
        Attempts to collect payment for an open invoice.
        If customer.payment_method_status == FAIL_ALWAYS, simulates card decline.
        Otherwise, records payment via double-entry:
        - DEBIT: Platform Cash
        - CREDIT: Customer Accounts Receivable
        """
        if invoice.amount_remaining_cents <= 0:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = virtual_now
            return "PAID_ZERO_BALANCE"

        if customer.payment_method_status == PaymentMethodStatus.FAIL_ALWAYS:
            # Payment failed
            return "PAYMENT_DECLINED_CARD_ERROR"

        # Check if customer has prepaid wallet balance to apply first
        wallet_balance = await LedgerEngine.get_account_balance(session, customer.wallet_account_id)
        amount_to_pay = invoice.amount_remaining_cents

        if wallet_balance > 0:
            wallet_applied = min(wallet_balance, amount_to_pay)
            # Pay from prepaid wallet:
            # DEBIT: Customer Prepaid Wallet (reduces liability)
            # CREDIT: Customer Accounts Receivable (clears AR)
            await LedgerEngine.create_journal_entry(
                session=session,
                description=f"Prepaid wallet payment applied for Invoice {invoice.id}",
                effective_at=virtual_now,
                postings=[
                    {
                        "account_id": customer.wallet_account_id,
                        "direction": PostingDirection.DEBIT,
                        "amount_cents": wallet_applied,
                    },
                    {
                        "account_id": customer.receivable_account_id,
                        "direction": PostingDirection.CREDIT,
                        "amount_cents": wallet_applied,
                    },
                ],
                enforce_non_negative_accounts=[customer.wallet_account_id],
                metadata_json={"invoice_id": invoice.id, "payment_type": "WALLET_DRAWDOWN"},
            )
            invoice.amount_paid_cents += wallet_applied
            invoice.amount_remaining_cents -= wallet_applied
            amount_to_pay -= wallet_applied

        if amount_to_pay > 0:
            # Direct card payment for remaining amount:
            # DEBIT: Platform Cash (increases asset)
            # CREDIT: Customer Accounts Receivable (clears AR)
            await LedgerEngine.create_journal_entry(
                session=session,
                description=f"Credit Card charge succeeded for Invoice {invoice.id}",
                effective_at=virtual_now,
                postings=[
                    {
                        "account_id": PLATFORM_CASH_ACCOUNT_ID,
                        "direction": PostingDirection.DEBIT,
                        "amount_cents": amount_to_pay,
                    },
                    {
                        "account_id": customer.receivable_account_id,
                        "direction": PostingDirection.CREDIT,
                        "amount_cents": amount_to_pay,
                    },
                ],
                metadata_json={"invoice_id": invoice.id, "payment_type": "STRIPE_CARD_CHARGE"},
            )
            invoice.amount_paid_cents += amount_to_pay
            invoice.amount_remaining_cents = 0

        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = virtual_now
        return "PAYMENT_SUCCEEDED"
