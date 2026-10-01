#!/usr/bin/env python3
"""
Chronos Developer CLI Tool
Allows developers, evaluators, and interviewers to interact with the Ledgerflow
double-entry ledger and test clock engine directly from the command line.
"""
import sys
import asyncio
import argparse
from datetime import timedelta
from sqlalchemy import select
from backend.app.database import AsyncSessionLocal, init_db
from backend.app.seed.seed_data import seed_database
from backend.app.models.ledger import Account
from backend.app.core.ledger_engine import LedgerEngine
from backend.app.core.clock_engine import ClockEngine
from backend.app.schemas.chaos import DuplicateStormRequest, OverdraftRaceRequest
from backend.app.api.v1.chaos import meter_storm_test, overdraft_race_test

async def cmd_status():
    async with AsyncSessionLocal() as session:
        clock = await ClockEngine.get_or_create_clock(session, "clock_main")
        proof = await LedgerEngine.verify_global_ledger(session)
        
        print("\n" + "=" * 60)
        print(" CHRONOS — IMMUTABLE LEDGER & TEST CLOCK STATUS")
        print("=" * 60)
        print(f" Virtual Clock Time:   {clock.current_virtual_time.isoformat()} UTC")
        print(f" Clock Engine Status:  {clock.status.value}")
        print(f" Global Zero-Sum:      {'✓ BALANCED (Delta: 0¢)' if proof['is_balanced'] else '✗ UNBALANCED'}")
        print(f" Total Ledger Debits:  ${proof['total_debits_cents'] / 100:,.2f}")
        print(f" Total Ledger Credits: ${proof['total_credits_cents'] / 100:,.2f}")
        print(f" Journal Entries:      {proof['total_journal_entries']}")
        print(f" Immutable Postings:   {proof['total_postings']}")
        print("=" * 60 + "\n")

async def cmd_ledger_balance():
    async with AsyncSessionLocal() as session:
        stmt = select(Account).order_by(Account.type.asc(), Account.name.asc())
        accounts = (await session.execute(stmt)).scalars().all()
        
        print("\n" + "-" * 75)
        print(f"{'ACCOUNT ID':<22} | {'TYPE':<10} | {'NET BALANCE':<14} | {'NAME'}")
        print("-" * 75)
        for acc in accounts:
            bal = await LedgerEngine.get_account_balance(session, acc.id)
            money_str = f"${bal / 100:,.2f}"
            print(f"{acc.id:<22} | {acc.type.value:<10} | {money_str:<14} | {acc.name}")
        print("-" * 75 + "\n")

async def cmd_clock_advance(days: int, hours: int):
    delta_seconds = (days * 86400) + (hours * 3600)
    if delta_seconds <= 0:
        print("Error: Advance duration must be positive.")
        return

    async with AsyncSessionLocal() as session:
        clock = await ClockEngine.get_or_create_clock(session, "clock_main")
        start = clock.current_virtual_time
        target = start + timedelta(seconds=delta_seconds)
        
        print(f"\nAdvancing Virtual Clock by {days}d {hours}h...")
        print(f"From: {start.isoformat()} UTC")
        print(f"To:   {target.isoformat()} UTC")
        
        milestones = await ClockEngine.advance_clock(session, "clock_main", target)
        print(f"\nExecuted {len(milestones)} simulation milestones:")
        for ms in milestones:
            print(f"  [{ms.timestamp.isoformat()}] {ms.event_type:<25} -> {ms.description}")
        print("\nAdvancement complete.\n")

async def cmd_stress_storm(count: int):
    print(f"\nLaunching {count} concurrent duplicate meter event storm...")
    req = DuplicateStormRequest(concurrency_count=count, customer_id="cus_nexus_ai", metric_name="llm_tokens", quantity=50000)
    resp = await meter_storm_test(req)
    print("\n" + "=" * 55)
    print(" IDEMPOTENCY DEDUPLICATION RESULTS")
    print("=" * 55)
    print(f" Concurrent Requests Fired: {resp.concurrency_count}")
    print(f" Unique Records Committed:   {resp.unique_committed} (HTTP 201)")
    print(f" Replays Deduplicated:       {resp.replays_blocked} (X-Idempotent-Replayed)")
    print(f" Total Execution Time:       {resp.time_taken_ms} ms")
    print(f" Message: {resp.message}")
    print("=" * 55 + "\n")

async def cmd_stress_race(count: int):
    print(f"\nSimulating parallel overdraft race condition with {count} concurrent tasks...")
    req = OverdraftRaceRequest(concurrency_count=count, customer_id="cus_quantum_labs", charge_amount_cents=1000, initial_wallet_balance_cents=5000)
    resp = await overdraft_race_test(req)
    print("\n" + "=" * 55)
    print(" ROW-LEVEL LOCKING OVERDRAFT RACE RESULTS")
    print("=" * 55)
    print(f" Initial Prepaid Balance:   ${resp.initial_balance_cents / 100:.2f}")
    print(f" Parallel Charges Fired:    {resp.charges_attempted} x $10.00")
    print(f" Charges Committed (Lock):  {resp.charges_succeeded} (Green)")
    print(f" Charges Rejected (422):    {resp.charges_rejected} (Red)")
    print(f" Final Wallet Balance:      ${resp.final_balance_cents / 100:.2f} (Strictly Non-Negative)")
    print(f" Balance Valid:             {resp.is_balance_valid}")
    print(f" Total Execution Time:      {resp.time_taken_ms} ms")
    print("=" * 55 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Chronos Developer CLI Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # status
    subparsers.add_parser("status", help="Display system status and zero-sum balance proof")

    # ledger balance
    ledger_parser = subparsers.add_parser("ledger", help="Ledger inspection commands")
    ledger_parser.add_argument("subaction", choices=["balance", "verify"], help="Action to execute")

    # clock advance
    clock_parser = subparsers.add_parser("clock", help="Virtual clock commands")
    clock_sub = clock_parser.add_subparsers(dest="clock_action", help="Clock actions")
    adv_parser = clock_sub.add_parser("advance", help="Advance virtual time")
    adv_parser.add_argument("--days", type=int, default=0, help="Days to advance")
    adv_parser.add_argument("--hours", type=int, default=0, help="Hours to advance")

    # stress tests
    stress_parser = subparsers.add_parser("stress", help="Chaos and concurrency stress tests")
    stress_sub = stress_parser.add_subparsers(dest="stress_action", help="Stress actions")
    storm_parser = stress_sub.add_parser("duplicate-storm", help="100-request duplicate storm")
    storm_parser.add_argument("--count", type=int, default=100, help="Number of concurrent requests")
    race_parser = stress_sub.add_parser("overdraft-race", help="20-thread parallel overdraft race")
    race_parser.add_argument("--count", type=int, default=20, help="Number of concurrent charges")

    args = parser.parse_args()

    if args.command == "status":
        asyncio.run(cmd_status())
    elif args.command == "ledger":
        if args.subaction in ("balance", "verify"):
            asyncio.run(cmd_ledger_balance())
    elif args.command == "clock" and args.clock_action == "advance":
        asyncio.run(cmd_clock_advance(args.days, args.hours))
    elif args.command == "stress" and args.stress_action == "duplicate-storm":
        asyncio.run(cmd_stress_storm(args.count))
    elif args.command == "stress" and args.stress_action == "overdraft-race":
        asyncio.run(cmd_stress_race(args.count))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
