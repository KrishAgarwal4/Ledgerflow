"""Initial Ledgerflow schema with double-entry ledger, test clocks, and billing

Revision ID: 0001_initial
Revises: 
Create Date: 2026-10-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.types import JSON

revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Accounts
    op.create_table(
        'accounts',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('type', sa.Enum('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE', name='account_type'), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('description', sa.String(length=256), nullable=True),
        sa.Column('is_active', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_accounts_id', 'accounts', ['id'])
    op.create_index('ix_accounts_type', 'accounts', ['type'])

    # 2. Journal Entries
    op.create_table(
        'journal_entries',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('idempotency_key', sa.String(length=128), nullable=True),
        sa.Column('description', sa.String(length=256), nullable=False),
        sa.Column('effective_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metadata_json', JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key')
    )
    op.create_index('ix_journal_entries_id', 'journal_entries', ['id'])

    # 3. Ledger Postings (Immutable, positive amount, double-entry)
    op.create_table(
        'ledger_postings',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('journal_entry_id', sa.String(length=64), nullable=False),
        sa.Column('account_id', sa.String(length=64), nullable=False),
        sa.Column('direction', sa.Enum('DEBIT', 'CREDIT', name='posting_direction'), nullable=False),
        sa.Column('amount_cents', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('amount_cents > 0', name='chk_positive_posting_amount'),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id']),
        sa.ForeignKeyConstraint(['journal_entry_id'], ['journal_entries.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ledger_postings_account_id', 'ledger_postings', ['account_id'])
    op.create_index('ix_ledger_postings_journal_entry_id', 'ledger_postings', ['journal_entry_id'])
    op.create_index('idx_postings_acc_dir', 'ledger_postings', ['account_id', 'direction'])

    # 4. Customers
    op.create_table(
        'customers',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('email', sa.String(length=128), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('wallet_account_id', sa.String(length=64), nullable=False),
        sa.Column('receivable_account_id', sa.String(length=64), nullable=False),
        sa.Column('payment_method_status', sa.Enum('VALID', 'FAIL_ALWAYS', name='payment_method_status'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['receivable_account_id'], ['accounts.id']),
        sa.ForeignKeyConstraint(['wallet_account_id'], ['accounts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )

    # 5. Plans
    op.create_table(
        'plans',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('billing_interval', sa.String(length=32), nullable=False),
        sa.Column('base_fee_cents', sa.BigInteger(), nullable=False),
        sa.Column('included_tokens', sa.BigInteger(), nullable=False),
        sa.Column('overage_rate_cents_per_million', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 6. Subscriptions
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('customer_id', sa.String(length=64), nullable=False),
        sa.Column('plan_id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.Enum('ACTIVE', 'PAST_DUE', 'CANCELED', 'INCOMPLETE', name='subscription_status'), nullable=False),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False),
        sa.Column('dunning_attempt_count', sa.Integer(), nullable=False),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # 7. Invoices
    op.create_table(
        'invoices',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('customer_id', sa.String(length=64), nullable=False),
        sa.Column('subscription_id', sa.String(length=64), nullable=True),
        sa.Column('status', sa.Enum('DRAFT', 'OPEN', 'PAID', 'UNCOLLECTIBLE', 'VOID', name='invoice_status'), nullable=False),
        sa.Column('subtotal_cents', sa.BigInteger(), nullable=False),
        sa.Column('tax_cents', sa.BigInteger(), nullable=False),
        sa.Column('total_cents', sa.BigInteger(), nullable=False),
        sa.Column('amount_paid_cents', sa.BigInteger(), nullable=False),
        sa.Column('amount_remaining_cents', sa.BigInteger(), nullable=False),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('journal_entry_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['journal_entry_id'], ['journal_entries.id']),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # 8. Invoice Line Items
    op.create_table(
        'invoice_line_items',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('invoice_id', sa.String(length=64), nullable=False),
        sa.Column('description', sa.String(length=256), nullable=False),
        sa.Column('quantity', sa.BigInteger(), nullable=False),
        sa.Column('unit_amount_cents', sa.BigInteger(), nullable=False),
        sa.Column('amount_cents', sa.BigInteger(), nullable=False),
        sa.Column('proration', sa.Boolean(), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 9. Usage Events
    op.create_table(
        'usage_events',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('customer_id', sa.String(length=64), nullable=False),
        sa.Column('subscription_id', sa.String(length=64), nullable=True),
        sa.Column('metric_name', sa.String(length=64), nullable=False),
        sa.Column('quantity', sa.BigInteger(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('idempotency_key', sa.String(length=128), nullable=False),
        sa.Column('invoice_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id']),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key')
    )
    op.create_index('idx_usage_customer_metric_billed', 'usage_events', ['customer_id', 'metric_name', 'invoice_id'])

    # 10. Test Clocks & Milestones
    op.create_table(
        'test_clocks',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('current_virtual_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.Enum('READY', 'ADVANCING', name='clock_status'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'clock_milestones',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('clock_id', sa.String(length=64), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('description', sa.String(length=256), nullable=False),
        sa.Column('details_json', JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clock_id'], ['test_clocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 11. Idempotency Records
    op.create_table(
        'idempotency_records',
        sa.Column('key', sa.String(length=128), nullable=False),
        sa.Column('path', sa.String(length=256), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('response_body', JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('key')
    )

def downgrade() -> None:
    op.drop_table('idempotency_records')
    op.drop_table('clock_milestones')
    op.drop_table('test_clocks')
    op.drop_table('usage_events')
    op.drop_table('invoice_line_items')
    op.drop_table('invoices')
    op.drop_table('subscriptions')
    op.drop_table('plans')
    op.drop_table('customers')
    op.drop_table('ledger_postings')
    op.drop_table('journal_entries')
    op.drop_table('accounts')
