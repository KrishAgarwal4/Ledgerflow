export type AccountType = 'ASSET' | 'LIABILITY' | 'EQUITY' | 'REVENUE' | 'EXPENSE';
export type PostingDirection = 'DEBIT' | 'CREDIT';

export interface Account {
  id: string;
  name: string;
  type: AccountType;
  currency: string;
  description?: string;
  balance_cents: number;
  created_at: string;
}

export interface LedgerPosting {
  id: string;
  journal_entry_id: string;
  account_id: string;
  direction: PostingDirection;
  amount_cents: number;
  created_at: string;
}

export interface JournalEntry {
  id: string;
  idempotency_key?: string;
  description: string;
  effective_at: string;
  metadata_json?: Record<string, any>;
  created_at: string;
  postings: LedgerPosting[];
}

export interface GlobalLedgerVerification {
  total_debits_cents: number;
  total_credits_cents: number;
  delta_cents: number;
  is_balanced: boolean;
  total_journal_entries: number;
  total_postings: number;
  proof_formula: string;
}

export interface Plan {
  id: string;
  name: string;
  billing_interval: string;
  base_fee_cents: number;
  included_tokens: number;
  overage_rate_cents_per_million: number;
  currency: string;
}

export interface Subscription {
  id: string;
  customer_id: string;
  plan_id: string;
  status: 'ACTIVE' | 'PAST_DUE' | 'CANCELED' | 'INCOMPLETE';
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  dunning_attempt_count: number;
  next_retry_at?: string;
  created_at: string;
  plan?: Plan;
}

export interface Customer {
  id: string;
  name: string;
  email: string;
  currency: string;
  wallet_account_id: string;
  receivable_account_id: string;
  wallet_balance_cents: number;
  receivable_balance_cents: number;
  payment_method_status: 'VALID' | 'FAIL_ALWAYS';
  active_subscription?: Subscription;
  created_at: string;
}

export interface InvoiceLineItem {
  id: string;
  description: string;
  quantity: number;
  unit_amount_cents: number;
  amount_cents: number;
  proration: boolean;
  period_start: string;
  period_end: string;
}

export interface Invoice {
  id: string;
  customer_id: string;
  subscription_id?: string;
  status: 'DRAFT' | 'OPEN' | 'PAID' | 'UNCOLLECTIBLE' | 'VOID';
  subtotal_cents: number;
  tax_cents: number;
  total_cents: number;
  amount_paid_cents: number;
  amount_remaining_cents: number;
  due_date: string;
  paid_at?: string;
  period_start: string;
  period_end: string;
  journal_entry_id?: string;
  created_at: string;
  line_items: InvoiceLineItem[];
}

export interface ClockMilestone {
  id: string;
  clock_id: string;
  timestamp: string;
  event_type: string;
  description: string;
  details_json?: Record<string, any>;
  created_at: string;
}

export interface TestClock {
  id: string;
  name: string;
  current_virtual_time: string;
  status: 'READY' | 'ADVANCING';
  milestones: ClockMilestone[];
}

export interface DuplicateStormResponse {
  concurrency_count: number;
  idempotency_key: string;
  unique_committed: number;
  replays_blocked: number;
  time_taken_ms: number;
  message: string;
}

export interface OverdraftResultItem {
  task_index: number;
  status: string;
  error: string;
}

export interface OverdraftRaceResponse {
  concurrency_count: number;
  initial_balance_cents: number;
  charges_attempted: number;
  charges_succeeded: number;
  charges_rejected: number;
  final_balance_cents: number;
  is_balance_valid: boolean;
  time_taken_ms: number;
  results: OverdraftResultItem[];
}

export interface ProrationPreview {
  current_plan_name: string;
  new_plan_name: string;
  refund_credit_cents: number;
  new_charge_cents: number;
  net_adjustment_cents: number;
  period_start: string;
  period_end: string;
  change_time: string;
}
