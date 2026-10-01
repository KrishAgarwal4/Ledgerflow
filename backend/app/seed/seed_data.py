from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database import AsyncSessionLocal, init_db
from backend.app.models.ledger import Account, AccountType, PostingDirection
from backend.app.models.customer import Customer, PaymentMethodStatus
from backend.app.models.billing import Plan, Subscription, SubscriptionStatus
from backend.app.models.clock import TestClock, ClockStatus
from backend.app.core.ledger_engine import LedgerEngine

async def seed_database() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        # Check if already seeded
        existing_acc = await session.execute(select(Account).where(Account.id == "acc_platform_cash"))
        if existing_acc.scalar_one_or_none():
            return

        # 1. Platform Ledger Accounts
        platform_accounts = [
            Account(id="acc_platform_cash", name="Stripe Operating Cash", type=AccountType.ASSET, currency="usd", description="Cash held in operational bank accounts"),
            Account(id="acc_platform_revenue", name="Platform SaaS & Metered Revenue", type=AccountType.REVENUE, currency="usd", description="Recognized revenue from subscriptions and usage"),
            Account(id="acc_bad_debt_expense", name="Bad Debt & Default Expense", type=AccountType.EXPENSE, currency="usd", description="Uncollectible receivables written off"),
            Account(id="acc_disputed_funds", name="Disputed Funds & Escrow", type=AccountType.LIABILITY, currency="usd", description="Funds held during disputes"),
        ]
        session.add_all(platform_accounts)

        # 2. Pricing Plans
        plans = [
            Plan(id="plan_starter", name="AI Developer Tier", billing_interval="month", base_fee_cents=4900, included_tokens=1_000_000, overage_rate_cents_per_million=1500, currency="usd"),
            Plan(id="plan_scale", name="AI Scale Tier", billing_interval="month", base_fee_cents=19900, included_tokens=10_000_000, overage_rate_cents_per_million=1000, currency="usd"),
            Plan(id="plan_enterprise", name="AI Enterprise Tier", billing_interval="month", base_fee_cents=99900, included_tokens=100_000_000, overage_rate_cents_per_million=800, currency="usd"),
        ]
        session.add_all(plans)
        await session.flush()

        # 3. Customer 1: Nexus Intelligence (Healthy, scaling company with prepaid credits)
        acc_wallet_nexus = Account(id="acc_wallet_nexus", name="Nexus AI Prepaid Credit Wallet", type=AccountType.LIABILITY, currency="usd", description="Customer prepaid deposit liability")
        acc_ar_nexus = Account(id="acc_ar_nexus", name="Nexus AI Accounts Receivable", type=AccountType.ASSET, currency="usd", description="Outstanding customer invoiced receivables")
        session.add_all([acc_wallet_nexus, acc_ar_nexus])

        customer_nexus = Customer(
            id="cus_nexus_ai",
            name="Nexus Intelligence Inc",
            email="billing@nexus.ai",
            currency="usd",
            wallet_account_id="acc_wallet_nexus",
            receivable_account_id="acc_ar_nexus",
            payment_method_status=PaymentMethodStatus.VALID,
        )
        session.add(customer_nexus)

        # 4. Customer 2: Quantum Labs ($50 prepaid credit balance, used for parallel overdraft stress testing)
        acc_wallet_quantum = Account(id="acc_wallet_quantum", name="Quantum Labs Prepaid Credit Wallet", type=AccountType.LIABILITY, currency="usd", description="Customer prepaid deposit liability")
        acc_ar_quantum = Account(id="acc_ar_quantum", name="Quantum Labs Accounts Receivable", type=AccountType.ASSET, currency="usd", description="Outstanding customer invoiced receivables")
        session.add_all([acc_wallet_quantum, acc_ar_quantum])

        customer_quantum = Customer(
            id="cus_quantum_labs",
            name="Quantum Labs LLC",
            email="finance@quantumlabs.ai",
            currency="usd",
            wallet_account_id="acc_wallet_quantum",
            receivable_account_id="acc_ar_quantum",
            payment_method_status=PaymentMethodStatus.VALID,
        )
        session.add(customer_quantum)

        # 5. Customer 3: Apex Synthetics ($0 wallet, FAIL_ALWAYS for Dunning & Retry Simulation)
        acc_wallet_apex = Account(id="acc_wallet_apex", name="Apex Synthetics Wallet", type=AccountType.LIABILITY, currency="usd", description="Customer prepaid deposit liability")
        acc_ar_apex = Account(id="acc_ar_apex", name="Apex Synthetics Accounts Receivable", type=AccountType.ASSET, currency="usd", description="Outstanding customer invoiced receivables")
        session.add_all([acc_wallet_apex, acc_ar_apex])

        customer_apex = Customer(
            id="cus_apex_ai",
            name="Apex Synthetics Ltd",
            email="accounts@apexsynthetics.ai",
            currency="usd",
            wallet_account_id="acc_wallet_apex",
            receivable_account_id="acc_ar_apex",
            payment_method_status=PaymentMethodStatus.FAIL_ALWAYS, # Failing card for Dunning tests
        )
        session.add(customer_apex)
        await session.flush()

        # 6. Canonical Test Clock
        canonical_clock_time = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
        test_clock = TestClock(
            id="clock_main",
            name="Primary Billing Test Clock",
            current_virtual_time=canonical_clock_time,
            status=ClockStatus.READY,
        )
        session.add(test_clock)

        # 7. Subscriptions
        cycle_end = canonical_clock_time + timedelta(days=30)
        sub_nexus = Subscription(
            id="sub_nexus_scale",
            customer_id="cus_nexus_ai",
            plan_id="plan_scale",
            status=SubscriptionStatus.ACTIVE,
            current_period_start=canonical_clock_time,
            current_period_end=cycle_end,
            cancel_at_period_end=False,
            dunning_attempt_count=0,
        )
        sub_quantum = Subscription(
            id="sub_quantum_starter",
            customer_id="cus_quantum_labs",
            plan_id="plan_starter",
            status=SubscriptionStatus.ACTIVE,
            current_period_start=canonical_clock_time,
            current_period_end=cycle_end,
            cancel_at_period_end=False,
            dunning_attempt_count=0,
        )
        sub_apex = Subscription(
            id="sub_apex_starter",
            customer_id="cus_apex_ai",
            plan_id="plan_starter",
            status=SubscriptionStatus.ACTIVE,
            current_period_start=canonical_clock_time,
            current_period_end=cycle_end,
            cancel_at_period_end=False,
            dunning_attempt_count=0,
        )
        session.add_all([sub_nexus, sub_quantum, sub_apex])
        await session.flush()

        # 8. Initial Balanced Journal Entries
        # Nexus AI: $250.00 prepaid
        await LedgerEngine.create_journal_entry(
            session=session,
            description="Nexus AI prepaid credit wallet funding ($250.00)",
            effective_at=canonical_clock_time,
            postings=[
                {"account_id": "acc_platform_cash", "direction": PostingDirection.DEBIT, "amount_cents": 25000},
                {"account_id": "acc_wallet_nexus", "direction": PostingDirection.CREDIT, "amount_cents": 25000},
            ],
            metadata_json={"customer_id": "cus_nexus_ai"}
        )

        # Quantum Labs: $50.00 prepaid (Used for overdraft race demo)
        await LedgerEngine.create_journal_entry(
            session=session,
            description="Quantum Labs prepaid credit top-up ($50.00)",
            effective_at=canonical_clock_time,
            postings=[
                {"account_id": "acc_platform_cash", "direction": PostingDirection.DEBIT, "amount_cents": 5000},
                {"account_id": "acc_wallet_quantum", "direction": PostingDirection.CREDIT, "amount_cents": 5000},
            ],
            metadata_json={"customer_id": "cus_quantum_labs"}
        )

        await session.commit()

if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_database())
