#!/usr/bin/env python3
"""
Chronos Concurrency & Throughput Benchmark
Measures requests/sec and latency percentiles (p50, p95, p99) under parallel spend load.
"""
import asyncio
import time
import statistics
import uuid
from backend.app.database import AsyncSessionLocal
from backend.app.core.idempotency import IdempotencyManager
from backend.app.core.ledger_engine import LedgerEngine, PLATFORM_REVENUE_ACCOUNT_ID, PostingDirection
from backend.app.models.clock import TestClock
from backend.app.core.clock_engine import ClockEngine

async def run_benchmark(concurrency: int = 50, iterations: int = 200):
    print("\n" + "=" * 60)
    print(f" CHRONOS CONCURRENCY BENCHMARK ({concurrency} WORKERS, {iterations} REQUESTS)")
    print("=" * 60)

    latencies = []
    start_total = time.perf_counter()

    semaphore = asyncio.Semaphore(concurrency)

    async def worker(idx: int):
        async with semaphore:
            req_start = time.perf_counter()
            key = f"evt_bench_{uuid.uuid4().hex[:12]}"
            async with AsyncSessionLocal() as session:
                clock = await ClockEngine.get_or_create_clock(session, "clock_main")
                now = clock.current_virtual_time

                # Balanced journal entry ($1.00 charge)
                await LedgerEngine.create_journal_entry(
                    session=session,
                    description=f"Benchmark Transaction #{idx}",
                    effective_at=now,
                    postings=[
                        {"account_id": "acc_platform_cash", "direction": PostingDirection.DEBIT, "amount_cents": 100},
                        {"account_id": PLATFORM_REVENUE_ACCOUNT_ID, "direction": PostingDirection.CREDIT, "amount_cents": 100},
                    ],
                    idempotency_key=key,
                )
                await session.commit()
            latencies.append((time.perf_counter() - req_start) * 1000)

    tasks = [asyncio.create_task(worker(i)) for i in range(iterations)]
    await asyncio.gather(*tasks)

    total_time = time.perf_counter() - start_total
    rps = iterations / total_time

    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]

    print(f" Total Transactions Processed: {iterations}")
    print(f" Total Wall Time:             {total_time:.3f} s")
    print(f" Throughput:                   {rps:.1f} req/s")
    print(f" Latency p50 (Median):         {p50:.2f} ms")
    print(f" Latency p95:                  {p95:.2f} ms")
    print(f" Latency p99:                  {p99:.2f} ms")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    asyncio.run(run_benchmark(concurrency=20, iterations=100))
