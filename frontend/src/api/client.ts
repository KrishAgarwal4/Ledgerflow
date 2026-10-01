import {
  Account, JournalEntry, GlobalLedgerVerification, Customer,
  Plan, Invoice, TestClock, ClockMilestone, DuplicateStormResponse,
  OverdraftRaceResponse, ProrationPreview
} from '../types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/v1';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorBody.message || errorBody.detail || errorBody.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Test Clocks
  async getClock(): Promise<TestClock> {
    const res = await fetch(`${API_BASE}/test-clocks`);
    return handleResponse<TestClock>(res);
  },

  async advanceClock(advanceSeconds?: number, targetTime?: string): Promise<TestClock> {
    const res = await fetch(`${API_BASE}/test-clocks/clock_main/advance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        advance_seconds: advanceSeconds,
        target_time: targetTime,
      }),
    });
    return handleResponse<TestClock>(res);
  },

  async resetEnvironment(): Promise<TestClock> {
    const res = await fetch(`${API_BASE}/test-clocks/reset`, { method: 'POST' });
    return handleResponse<TestClock>(res);
  },

  // Ledger
  async getAccounts(): Promise<Account[]> {
    const res = await fetch(`${API_BASE}/ledger/accounts`);
    return handleResponse<Account[]>(res);
  },

  async getJournalEntries(limit = 50): Promise<JournalEntry[]> {
    const res = await fetch(`${API_BASE}/ledger/journal-entries?limit=${limit}`);
    return handleResponse<JournalEntry[]>(res);
  },

  async verifyLedger(): Promise<GlobalLedgerVerification> {
    const res = await fetch(`${API_BASE}/ledger/verify`);
    return handleResponse<GlobalLedgerVerification>(res);
  },

  // Customers & Subscriptions
  async getCustomers(): Promise<Customer[]> {
    const res = await fetch(`${API_BASE}/customers`);
    return handleResponse<Customer[]>(res);
  },

  async getPlans(): Promise<Plan[]> {
    const res = await fetch(`${API_BASE}/plans`);
    return handleResponse<Plan[]>(res);
  },

  async getInvoices(): Promise<Invoice[]> {
    const res = await fetch(`${API_BASE}/invoices`);
    return handleResponse<Invoice[]>(res);
  },

  async previewProration(subscriptionId: string, newPlanId: string): Promise<ProrationPreview> {
    const res = await fetch(`${API_BASE}/subscriptions/${subscriptionId}/preview-proration`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_plan_id: newPlanId }),
    });
    return handleResponse<ProrationPreview>(res);
  },

  async changePlan(subscriptionId: string, newPlanId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/subscriptions/${subscriptionId}/change-plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_plan_id: newPlanId }),
    });
    return handleResponse(res);
  },

  // Usage Metering
  async emitMeterEvent(payload: {
    event_id: string;
    customer_id: string;
    metric_name: string;
    quantity: number;
    timestamp: string;
  }): Promise<{ is_replayed: boolean; [key: string]: any }> {
    const res = await fetch(`${API_BASE}/meter-events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const isReplayed = res.headers.get('x-idempotent-replayed') === 'true';
    const data = await handleResponse<any>(res);
    return { ...data, is_replayed: isReplayed };
  },

  // Chaos Stress Tests
  async runMeterStorm(concurrency = 100, customerId = 'cus_nexus_ai', quantity = 50000): Promise<DuplicateStormResponse> {
    const res = await fetch(`${API_BASE}/chaos/meter-storm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        concurrency_count: concurrency,
        customer_id: customerId,
        metric_name: 'llm_tokens',
        quantity: quantity,
      }),
    });
    return handleResponse<DuplicateStormResponse>(res);
  },

  async runOverdraftRace(concurrency = 20, customerId = 'cus_quantum_labs'): Promise<OverdraftRaceResponse> {
    const res = await fetch(`${API_BASE}/chaos/overdraft-race`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        concurrency_count: concurrency,
        customer_id: customerId,
        charge_amount_cents: 1000,
        initial_wallet_balance_cents: 5000,
      }),
    });
    return handleResponse<OverdraftRaceResponse>(res);
  },
};
