import React, { useState } from 'react';
import { Customer, Plan, Invoice, ProrationPreview } from '../types';
import { Users, FileText, ArrowUpRight, CheckCircle, Clock, AlertCircle, Sparkles, RefreshCw } from 'lucide-react';
import { api } from '../api/client';

interface BillingPanelProps {
  customers: Customer[];
  plans: Plan[];
  invoices: Invoice[];
  onRefresh: () => void;
}

export const BillingPanel: React.FC<BillingPanelProps> = ({
  customers,
  plans,
  invoices,
  onRefresh,
}) => {
  const [selectedSubId, setSelectedSubId] = useState<string | null>(null);
  const [targetPlanId, setTargetPlanId] = useState<string>('');
  const [prorationPreview, setProrationPreview] = useState<ProrationPreview | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [isChangingPlan, setIsChangingPlan] = useState(false);
  const [expandedInvoiceId, setExpandedInvoiceId] = useState<string | null>(null);

  const formatMoney = (cents: number) => `$${(cents / 100).toFixed(2)}`;

  const handleOpenProrationModal = (subId: string, currentPlanId: string) => {
    setSelectedSubId(subId);
    // Default to next plan
    const otherPlan = plans.find((p) => p.id !== currentPlanId);
    if (otherPlan) {
      setTargetPlanId(otherPlan.id);
      loadPreview(subId, otherPlan.id);
    }
  };

  const loadPreview = async (subId: string, planId: string) => {
    setIsLoadingPreview(true);
    try {
      const preview = await api.previewProration(subId, planId);
      setProrationPreview(preview);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingPreview(false);
    }
  };

  const executePlanChange = async () => {
    if (!selectedSubId || !targetPlanId) return;
    setIsChangingPlan(true);
    try {
      await api.changePlan(selectedSubId, targetPlanId);
      setSelectedSubId(null);
      setProrationPreview(null);
      onRefresh();
    } catch (err: any) {
      alert(`Plan change error: ${err.message}`);
    } finally {
      setIsChangingPlan(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'ACTIVE':
      case 'PAID':
        return (
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">
            {status}
          </span>
        );
      case 'PAST_DUE':
      case 'OPEN':
        return (
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-semibold">
            {status}
          </span>
        );
      case 'CANCELED':
      case 'UNCOLLECTIBLE':
        return (
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 font-semibold">
            {status}
          </span>
        );
      default:
        return (
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-semibold">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Customers & Subscriptions Card */}
      <div className="bg-surface-card border border-surface-border rounded-xl p-5 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold tracking-wide text-white uppercase flex items-center gap-2">
              <Users className="w-4 h-4 text-stripe-400" />
              SaaS Customers &amp; Subscription State Machines
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Live subscription states, prepaid wallet liabilities, and mid-cycle proration engine.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {customers.map((cust) => {
            const sub = cust.active_subscription;
            return (
              <div
                key={cust.id}
                className="bg-surface-base border border-surface-border rounded-xl p-4 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-xs font-semibold text-white truncate">
                      {cust.name}
                    </span>
                    {sub && getStatusBadge(sub.status)}
                  </div>
                  <div className="text-[11px] font-mono text-slate-400 mb-3">
                    {cust.email}
                  </div>

                  {/* Plan & Balances */}
                  <div className="space-y-2 py-2.5 border-y border-surface-border text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Current Tier:</span>
                      <span className="font-semibold text-stripe-300">
                        {sub?.plan?.name || 'No Active Plan'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Prepaid Wallet Credit:</span>
                      <span className="font-mono font-semibold text-cyan-400">
                        {formatMoney(cust.wallet_balance_cents)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Outstanding AR:</span>
                      <span className="font-mono font-semibold text-amber-400">
                        {formatMoney(cust.receivable_balance_cents)}
                      </span>
                    </div>
                    {sub?.dunning_attempt_count ? (
                      <div className="flex items-center justify-between text-rose-400 font-mono text-[11px]">
                        <span>Dunning Retries:</span>
                        <span>{sub.dunning_attempt_count} / 3 Attempts</span>
                      </div>
                    ) : null}
                  </div>
                </div>

                {/* Proration Upgrade Button */}
                {sub && sub.status === 'ACTIVE' && (
                  <button
                    onClick={() => handleOpenProrationModal(sub.id, sub.plan_id)}
                    className="mt-3.5 w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-stripe-600 hover:bg-stripe-500 text-white text-xs font-medium transition-all shadow-md shadow-stripe-600/20"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    Change Tier (Preview Proration)
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Invoices Table Card */}
      <div className="bg-surface-card border border-surface-border rounded-xl p-5 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold tracking-wide text-white uppercase flex items-center gap-2">
              <FileText className="w-4 h-4 text-stripe-400" />
              Finalized Invoices &amp; Line Items
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Invoices auto-generated by the Test Clock with base fees, usage overages, and double-entry postings.
            </p>
          </div>
          <div className="text-xs font-mono text-slate-400 bg-surface-base px-2.5 py-1 rounded border border-surface-border">
            {invoices.length} Invoices
          </div>
        </div>

        {invoices.length === 0 ? (
          <div className="text-center py-8 text-xs text-slate-400 border border-dashed border-surface-border rounded-lg">
            No invoices generated yet. Advance the Virtual Clock by <strong>+30 Days</strong> to close a billing period!
          </div>
        ) : (
          <div className="space-y-3">
            {invoices.map((inv) => {
              const isExpanded = expandedInvoiceId === inv.id;
              return (
                <div
                  key={inv.id}
                  className="border border-surface-border bg-surface-base rounded-xl overflow-hidden"
                >
                  <div
                    onClick={() => setExpandedInvoiceId(isExpanded ? null : inv.id)}
                    className="p-3.5 flex flex-col md:flex-row md:items-center justify-between gap-3 cursor-pointer hover:bg-surface-elevated/40"
                  >
                    <div className="flex items-center gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-white">
                            {inv.id}
                          </span>
                          {getStatusBadge(inv.status)}
                          <span className="text-xs text-slate-300 font-medium">
                            Customer: {inv.customer_id}
                          </span>
                        </div>
                        <div className="text-[11px] font-mono text-slate-400 mt-0.5">
                          Period: {new Date(inv.period_start).toISOString().slice(0, 10)} to {new Date(inv.period_end).toISOString().slice(0, 10)}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-4 text-right">
                      <div>
                        <div className="text-sm font-mono font-bold text-white">
                          {formatMoney(inv.total_cents)}
                        </div>
                        <div className="text-[10px] font-mono text-slate-400">
                          Paid: {formatMoney(inv.amount_paid_cents)} | Remaining: {formatMoney(inv.amount_remaining_cents)}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Expanded Line Items */}
                  {isExpanded && (
                    <div className="border-t border-surface-border bg-surface-card/60 p-4">
                      <div className="text-[11px] font-mono font-semibold uppercase text-slate-400 mb-2">
                        Line Items Breakdown:
                      </div>
                      <div className="space-y-1.5">
                        {inv.line_items.map((item) => (
                          <div
                            key={item.id}
                            className="flex items-center justify-between text-xs py-1.5 px-2 rounded bg-surface-base border border-surface-border"
                          >
                            <div>
                              <span className="font-medium text-slate-200">{item.description}</span>
                              {item.proration && (
                                <span className="ml-2 text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                                  Prorated
                                </span>
                              )}
                            </div>
                            <div className="font-mono font-semibold text-white">
                              {formatMoney(item.amount_cents)}
                            </div>
                          </div>
                        ))}
                      </div>

                      {inv.journal_entry_id && (
                        <div className="mt-3 pt-2 border-t border-surface-border flex items-center justify-between text-[11px] font-mono text-slate-400">
                          <span>Linked Journal Entry:</span>
                          <span className="text-stripe-300">{inv.journal_entry_id}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Mid-Cycle Proration Modal */}
      {selectedSubId && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface-card border border-surface-border rounded-2xl max-w-lg w-full p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-200">
            <h3 className="text-base font-bold text-white mb-1 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-stripe-400" />
              Mid-Cycle Tier Upgrade (Exact Proration)
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              Calculates refund credits for unused time down to the exact second, plus prorated charge on the new plan.
            </p>

            {/* Select Target Plan */}
            <div className="mb-4">
              <label className="text-xs font-mono text-slate-300 block mb-1.5">Select New Tier:</label>
              <select
                value={targetPlanId}
                onChange={(e) => {
                  setTargetPlanId(e.target.value);
                  if (selectedSubId) loadPreview(selectedSubId, e.target.value);
                }}
                className="w-full bg-surface-base border border-surface-border rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-stripe-500"
              >
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} — ${p.base_fee_cents / 100}/mo ({p.included_tokens.toLocaleString()} tokens incl.)
                  </option>
                ))}
              </select>
            </div>

            {/* Proration Calculation Preview */}
            {isLoadingPreview ? (
              <div className="py-6 text-center text-xs text-slate-400">
                <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-stripe-400" />
                Calculating exact proration seconds...
              </div>
            ) : prorationPreview ? (
              <div className="p-4 rounded-xl bg-surface-base border border-surface-border space-y-2 mb-5 font-mono text-xs">
                <div className="flex items-center justify-between text-slate-400">
                  <span>Unused Credit ({prorationPreview.current_plan_name}):</span>
                  <span className="text-cyan-400">-{formatMoney(prorationPreview.refund_credit_cents)}</span>
                </div>
                <div className="flex items-center justify-between text-slate-400">
                  <span>Prorated Charge ({prorationPreview.new_plan_name}):</span>
                  <span className="text-stripe-300">+{formatMoney(prorationPreview.new_charge_cents)}</span>
                </div>
                <div className="pt-2 border-t border-surface-border flex items-center justify-between font-bold text-sm">
                  <span className="text-white">Net Immediate Adjustment:</span>
                  <span className={prorationPreview.net_adjustment_cents >= 0 ? 'text-amber-400' : 'text-emerald-400'}>
                    {formatMoney(prorationPreview.net_adjustment_cents)}
                  </span>
                </div>
              </div>
            ) : null}

            {/* Action Buttons */}
            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => {
                  setSelectedSubId(null);
                  setProrationPreview(null);
                }}
                className="px-4 py-2 rounded-lg bg-surface-elevated hover:bg-surface-subtle text-slate-300 text-xs font-medium"
              >
                Cancel
              </button>
              <button
                onClick={executePlanChange}
                disabled={isChangingPlan || !targetPlanId}
                className="px-4 py-2 rounded-lg bg-stripe-600 hover:bg-stripe-500 text-white text-xs font-semibold shadow-lg shadow-stripe-600/30 flex items-center gap-1.5 disabled:opacity-50"
              >
                {isChangingPlan ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <ArrowUpRight className="w-3.5 h-3.5" />}
                Confirm &amp; Post to Ledger
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
